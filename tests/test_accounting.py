"""Contabilidad: partida doble, inmutabilidad, periodos, reversos, reportes, cierre y conciliación bancaria."""
from datetime import date, timedelta

import pytest
from helpers import TODAY, D, confirmed_so, scalar, shipped_dispatch, stock_in
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.db import SessionLocal


def _acc(env, code):
    return scalar("select id from accounts where company_id = :c and code = :k", c=env["company_id"], k=code)


def _manual(env, user="admin1", amount="1000", d=None):
    return env.api(user).post("/accounting/entries", {
        "entry_date": str(d or TODAY), "description": "Aporte de capital de prueba",
        "lines": [{"account_id": _acc(env, "111005"), "debit": amount},
                  {"account_id": _acc(env, "310505"), "credit": amount}]})


def test_unbalanced_entry_rejected_by_api_and_database(env):
    r = env.api("admin1").post("/accounting/entries", {
        "entry_date": str(TODAY), "description": "Desbalanceado",
        "lines": [{"account_id": _acc(env, "111005"), "debit": "10"},
                  {"account_id": _acc(env, "310505"), "credit": "9"}]}, expect=422)
    assert "balanceado" in r.text
    draft = _manual(env)
    env.api("admin2").post(f"/accounting/entries/{draft['id']}/post")
    entry_id = scalar("select id from journal_entries where status = 'posted'")
    with SessionLocal() as db, pytest.raises(DBAPIError):  # trigger diferido de balance
        db.execute(text("""insert into journal_lines (company_id, entry_id, line_no, account_id, debit, credit)
                           values (:c, :e, 99, :a, 5, 0)"""), {"c": env["company_id"], "e": entry_id,
                                                             "a": _acc(env, "111005")})
        db.commit()


def test_posted_entries_are_immutable_and_reversed(env):
    draft = _manual(env)
    _manual(env, user="admin1")
    env.api("admin1").post(f"/accounting/entries/{draft['id']}/post", expect=403)  # SoD: quien crea no contabiliza
    posted = env.api("admin2").post(f"/accounting/entries/{draft['id']}/post")
    with SessionLocal() as db, pytest.raises(DBAPIError):
        db.execute(text("update journal_lines set debit = 1 where entry_id = :e"), {"e": posted["id"]})
        db.commit()
    with SessionLocal() as db, pytest.raises(DBAPIError):
        db.execute(text("delete from journal_entries where id = :e"), {"e": posted["id"]})
        db.commit()
    rev = env.api("contador").post(f"/accounting/entries/{posted['id']}/reverse",
                                   {"reversal_date": str(TODAY), "reason": "Error de digitación"})
    assert rev["reversal_of_id"] == posted["id"]
    env.api("contador").post(f"/accounting/entries/{posted['id']}/reverse",
                             {"reversal_date": str(TODAY), "reason": "Otra vez"}, expect=409)
    tb = env.api("contador").get(f"/accounting/reports/trial-balance?start={TODAY.replace(day=1)}&end={TODAY}")
    cash = next(r for r in tb["rows"] if r["code"] == "111005")
    assert D(cash["closing"]) == 0 and tb["balanced"]


def test_closed_period_blocks_postings(env):
    c1, c2 = env.api("contador"), env.api("admin2")
    prev = (TODAY.replace(day=1) - timedelta(days=1))
    c1.post("/accounting/periods/close", {"year": prev.year, "month": prev.month})
    r = _manual_req = c1.post("/accounting/entries", {
        "entry_date": str(prev), "description": "Asiento en periodo cerrado",
        "lines": [{"account_id": _acc(env, "111005"), "debit": "5"},
                  {"account_id": _acc(env, "310505"), "credit": "5"}]}, expect=422)
    assert "cerrado" in r.json()["error"]["message"]
    # La base de datos también lo impide
    pid = scalar("select id from fiscal_periods where company_id = :c and year = :y and month = :m",
                 c=env["company_id"], y=prev.year, m=prev.month)
    with SessionLocal() as db, pytest.raises(DBAPIError):
        db.execute(text("""insert into journal_entries (company_id, number, entry_date, period_id, journal_type,
            description, status, idempotency_key, total_debit, total_credit)
            values (:c, 'X', :d, :p, 'general', 'x', 'posted', 'x', 0, 0)"""),
                   {"c": env["company_id"], "d": prev, "p": pid})
        db.commit()
    # Reapertura: justificada y por un usuario distinto a quien cerró
    c1.post("/accounting/periods/reopen", {"year": prev.year, "month": prev.month, "reason": "Ajuste"}, expect=422)
    c1.post("/accounting/periods/reopen", {"year": prev.year, "month": prev.month,
                                           "reason": "Ajuste por factura recibida tarde"}, expect=422)
    c2.post("/accounting/periods/reopen", {"year": prev.year, "month": prev.month,
                                           "reason": "Ajuste por factura recibida tarde"})
    assert _manual_req is not None


def test_financial_statements_tie_out(env):
    stock_in(env, "A", qty=10, price=100)
    so = confirmed_so(env, "A", qty=4, price=250)
    d = shipped_dispatch(env, so)
    a = env.api("admin1")
    inv = a.post("/einvoicing/invoices/from-dispatch", {"dispatch_id": d["id"]})
    a.post(f"/einvoicing/invoices/{inv['id']}/issue")
    c = env.api("contador")
    start = TODAY.replace(day=1)
    pl = c.get(f"/accounting/reports/income-statement?start={start}&end={TODAY}")
    assert D(pl["revenue"]) == D(1000) and D(pl["cost_of_sales"]) == D(400) and D(pl["gross_profit"]) == D(600)
    bs = c.get(f"/accounting/reports/balance-sheet?as_of={TODAY}")
    assert bs["balanced"] and D(bs["current_result"]) == D(600)
    tb = c.get(f"/accounting/reports/trial-balance?start={start}&end={TODAY}")
    assert tb["balanced"]
    aging = c.get("/accounting/aging?kind=receivable")
    assert D(aging["total"]) == D(1190) and D(aging["totals"]["current"]) == D(1190)
    ledger = c.get(f"/accounting/reports/general-ledger/{_acc(env, '413505')}?start={start}&end={TODAY}")
    assert ledger["lines"][0]["source_type"] == "sales_invoice"  # trazabilidad al documento origen
    csv = env.client.get(f"/api/v1/accounting/reports/trial-balance.csv?start={start}&end={TODAY}", headers=c.headers)
    assert csv.status_code == 200 and "413505" in csv.text


def test_year_close(env):
    from app.core.db import SessionLocal as S
    from app.modules.org.service import ensure_periods

    last_year = TODAY.year - 1
    with S() as db:
        ensure_periods(db, env["company_id"], last_year)
        db.commit()
    a = env.api("admin1")
    draft = a.post("/accounting/entries", {
        "entry_date": str(date(last_year, 6, 30)), "description": "Venta de servicios año anterior",
        "lines": [{"account_id": _acc(env, "111005"), "debit": "500"},
                  {"account_id": _acc(env, "413505"), "credit": "500"}]})
    env.api("admin2").post(f"/accounting/entries/{draft['id']}/post")
    close = env.api("contador").post("/accounting/year-close", {"year": last_year, "month": 12})
    retained = next(ln for ln in close["lines"] if ln["account_id"] == _acc(env, "370505"))
    assert D(retained["credit"]) == D(500)
    pl = env.api("contador").get(f"/accounting/reports/income-statement?start={last_year}-01-01&end={last_year}-12-31")
    assert D(pl["net_income"]) == D(500)  # el asiento de cierre no distorsiona el estado de resultados


def test_bank_reconciliation(env):
    draft = _manual(env, amount="700")
    env.api("admin2").post(f"/accounting/entries/{draft['id']}/post")
    t = env.api("admin1")
    st = t.post("/accounting/bank-statements", {
        "bank_account_id": env["bank_account_id"], "statement_date": str(TODAY), "opening_balance": "0",
        "closing_balance": "690", "lines": [{"txn_date": str(TODAY), "description": "Consignación", "amount": "700"},
                                            {"txn_date": str(TODAY), "description": "Comisión", "amount": "-10"}]})
    t.post("/accounting/bank-statements", {
        "bank_account_id": env["bank_account_id"], "statement_date": str(TODAY), "opening_balance": "0",
        "closing_balance": "1", "lines": [{"txn_date": str(TODAY), "description": "x", "amount": "5"}]}, expect=422)
    m = t.post(f"/accounting/bank-statements/{st['id']}/auto-match")
    assert m == {"matched": 1, "unmatched": 1}
    rep = t.get(f"/accounting/bank-statements/{st['id']}/reconciliation")
    assert D(rep["book_balance"]) == D(700) and D(rep["difference"]) == D(10)
    assert rep["unmatched_statement_lines"][0]["description"] == "Comisión"
