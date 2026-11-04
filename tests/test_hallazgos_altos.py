"""Regresión de los hallazgos críticos y altos del manual funcional (H-01, H-14, H-26, H-28, H-38, H-39, H-41...)."""
import pytest
from conftest import build_company
from helpers import TODAY, D, approved_po, confirmed_so, entries_for, receive, shipped_dispatch, stock_in
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.permissions import ROLES
from app.modules.accounting.models import Account
from app.modules.inventory.models import Location, StockBalance


def _doc(api, doc_type, item_id, qty, *, lot=None, frm=None, to=None, cost=None, expect=None):
    line = {"item_id": item_id, "quantity": str(qty), "from_location_id": frm, "to_location_id": to, "lot_id": lot}
    if cost is not None:
        line["unit_cost"] = str(cost)
    return api.post("/inventory/documents", {"doc_type": doc_type, "doc_date": str(TODAY),
                                             "reason": "Prueba de regresión", "lines": [line]}, expect=expect)


# ---------------------------------------------------------------- roles predefinidos
@pytest.mark.parametrize("user,paths", [
    ("comprador", ["/sites", "/warehouses", "/locations", "/payment-terms", "/parties", "/items"]),
    ("aprobador", ["/parties", "/items", "/sites", "/warehouses"]),
    ("almacen", ["/parties", "/sites", "/items", "/cost-centers"]),
    ("calidad", ["/items", "/parties"]),
    ("vendedor", ["/sites", "/warehouses", "/payment-terms", "/parties", "/items"]),
    ("despacho", ["/parties", "/items", "/locations", "/routes", "/sites"]),
    ("contador", ["/parties", "/items", "/purchasing/receipts", "/purchasing/orders", "/sites", "/cost-centers"]),
])
def test_roles_see_the_catalogs_their_forms_need(env, user, paths):
    api = env.api(user)
    for path in paths:
        api.get(path)


def test_buyer_creates_purchase_order_with_predefined_role(env):
    po = env.api("comprador").post("/purchasing/orders", {
        "site_id": env["site_id"], "supplier_id": env["supplier_id"], "warehouse_id": env["warehouse_id"],
        "order_date": str(TODAY), "currency": "COP",
        "lines": [{"item_id": env["items"]["A"], "quantity": "1", "unit_price": "10"}]})
    assert po["status"] == "draft"


def test_treasury_and_operations_roles_include_reference_reads():
    tesorero = set(ROLES["tesorero"][1])
    assert {"masters.parties.read", "masters.taxes.read"} <= tesorero
    operaciones = set(ROLES["operaciones"][1])
    assert {"admin.company.read", "masters.items.read", "inventory.config.read"} <= operaciones
    assert "masters.items.read" in set(ROLES["facturador"][1])


def test_read_permissions_do_not_grant_new_write_powers(env):
    env.api("comprador").post("/sites", {"code": "X", "name": "No autorizada"}, expect=403)
    env.api("aprobador").post("/parties", {"code": "X"}, expect=403)
    env.api("calidad").patch("/company/fiscal", {"is_withholding_agent": False, "is_special_taxpayer": False}, expect=403)


# ---------------------------------------------------------------- H-14
def test_integrity_errors_explain_the_problem(env):
    a = env.api("admin1")
    r = a.post("/warehouses", {"code": "BOD01", "name": "Repetida", "site_id": env["site_id"]}, expect=409)
    assert r.json()["error"]["message"] == "Ya existe una bodega con ese código"
    r = a.post("/payment-terms", {"code": "NEG", "name": "Negativa", "days": -1}, expect=409)
    assert r.json()["error"]["message"] == "Los días de la condición de pago no pueden ser negativos"


# ---------------------------------------------------------------- H-01
def test_next_year_can_be_opened_and_then_used(env):
    a, b = env.api("contador"), env.api("admin1")
    year = TODAY.year + 3
    accounts = {x["code"]: x["id"] for x in a.get("/accounts?limit=500")["items"]}
    body = {"entry_date": f"{year}-01-15", "description": "Prueba del año nuevo", "lines": [
        {"account_id": accounts["519530"], "debit": "10"}, {"account_id": accounts["111005"], "credit": "10"}]}
    r = a.post("/accounting/entries", body, expect=422)
    assert f"No existe periodo contable para {year}-01" in r.json()["error"]["message"]
    assert a.get(f"/accounting/periods?year={year}") == []
    a.post("/accounting/periods/open-year", {"year": year, "month": 1})
    assert len(a.get(f"/accounting/periods?year={year}")) == 12
    entry = a.post("/accounting/entries", body)
    assert b.post(f"/accounting/entries/{entry['id']}/post")["status"] == "posted"


# ---------------------------------------------------------------- H-62
def test_manual_draft_rejects_unusable_accounts_and_can_be_discarded(env):
    a = env.api("contador")
    accounts = {x["code"]: x["id"] for x in a.get("/accounts?limit=500")["items"]}
    bank = accounts["111005"]
    title = {"entry_date": str(TODAY), "description": "Cuenta de título", "lines": [
        {"account_id": accounts["1"], "debit": "10"}, {"account_id": bank, "credit": "10"}]}
    assert "no es de movimiento" in a.post("/accounting/entries", title, expect=422).json()["error"]["message"]
    with SessionLocal() as db:
        assert db.get(Account, accounts["130505"]).requires_party
    need_party = {"entry_date": str(TODAY), "description": "Cuenta con tercero", "lines": [
        {"account_id": accounts["130505"], "debit": "10"}, {"account_id": bank, "credit": "10"}]}
    assert "exige tercero" in a.post("/accounting/entries", need_party, expect=422).json()["error"]["message"]
    need_party["lines"][0]["party_id"] = env["customer_id"]
    draft = a.post("/accounting/entries", need_party)
    assert draft["status"] == "draft" and draft["lines"][0]["party_id"] == env["customer_id"]
    assert a._call("DELETE", f"/accounting/entries/{draft['id']}").status_code == 204
    assert all(e["id"] != draft["id"] for e in a.get("/accounting/entries?limit=100")["items"])


# ---------------------------------------------------------------- H-38
def test_quarantine_stock_only_leaves_through_inspection(env):
    po = approved_po(env, "QC", qty=10, price=40)
    receive(env, po, 10, lot="QC-001")
    a, b = env.api("almacen"), env.api("admin1")
    lot = b.get(f"/inventory/lots?item_id={env['items']['QC']}")["items"][0]["id"]
    doc = _doc(a, "transfer", env["items"]["QC"], 4, lot=lot, frm=env["locations"]["quality"], to=env["locations"]["storage"])
    r = a.post(f"/inventory/documents/{doc['id']}/post", expect=422)
    assert "pendientes de inspección" in r.json()["error"]["message"]


def test_quality_location_without_pending_inspection_can_move(env):
    a, b = env.api("admin1"), env.api("admin2")
    adj = _doc(a, "adjustment", env["items"]["A"], 3, to=env["locations"]["quality"], cost=10)
    b.post(f"/inventory/documents/{adj['id']}/approve")
    b.post(f"/inventory/documents/{adj['id']}/post")
    doc = _doc(a, "transfer", env["items"]["A"], 3, frm=env["locations"]["quality"], to=env["locations"]["storage"])
    assert a.post(f"/inventory/documents/{doc['id']}/post")["status"] == "posted"


# ---------------------------------------------------------------- H-39
def test_lot_items_require_their_own_lot_in_documents(env):
    stock_in(env, "LOT", qty=5, price=20, lot="L-1", expiry=TODAY.replace(year=TODAY.year + 1))
    stock_in(env, "A", qty=5, price=20)
    a = env.api("admin1")
    storage, dispatch = env["locations"]["storage"], env["locations"]["dispatch"]
    r = _doc(a, "transfer", env["items"]["LOT"], 2, frm=storage, to=dispatch, expect=422)
    assert "maneja lotes" in r.json()["error"]["message"]
    lot = a.get(f"/inventory/lots?item_id={env['items']['LOT']}")["items"][0]["id"]
    r = _doc(a, "transfer", env["items"]["A"], 2, lot=lot, frm=storage, to=dispatch, expect=422)
    assert "no corresponde" in r.json()["error"]["message"]
    doc = _doc(a, "transfer", env["items"]["LOT"], 2, lot=lot, frm=storage, to=dispatch)
    assert a.post(f"/inventory/documents/{doc['id']}/post")["status"] == "posted"


# ---------------------------------------------------------------- H-41
def test_count_opener_stays_blind_and_other_approver_sees_system_quantity(env):
    stock_in(env, "A", qty=5, price=20)
    opener, approver = env.api("almacen"), env.api("admin1")
    cnt = opener.post("/inventory/counts", {"warehouse_id": env["warehouse_id"], "count_date": str(TODAY)})
    assert all("system_qty" not in ln for ln in opener.get(f"/inventory/counts/{cnt['id']}?blind=false")["lines"])
    assert all("system_qty" in ln for ln in approver.get(f"/inventory/counts/{cnt['id']}?blind=false")["lines"])
    assert all("system_qty" not in ln for ln in approver.get(f"/inventory/counts/{cnt['id']}")["lines"])


# ---------------------------------------------------------------- H-54
def test_damaged_return_goes_to_scrap_and_costs_the_nonconformity(env):
    stock_in(env, "A", qty=10, price=100)
    d = shipped_dispatch(env, confirmed_so(env, "A", qty=4, price=200))
    a = env.api("admin1")
    before = D(a.get(f"/inventory/availability/{env['items']['A']}")["available"])
    ret = a.post(f"/logistics/dispatches/{d['id']}/returns", {
        "location_id": env["locations"]["storage"], "return_date": str(TODAY), "reason": "Llegó golpeado",
        "lines": [{"dispatch_line_id": d["lines"][0]["id"], "quantity": "2", "condition": "damaged"}]})
    assert ret["status"] == "received" and len(entries_for("customer_return", ret["id"])) == 1
    assert D(a.get(f"/inventory/availability/{env['items']['A']}")["available"]) == before
    with SessionLocal() as db:
        scrap = db.scalar(select(StockBalance).where(StockBalance.item_id == env["items"]["A"],
                                                     StockBalance.location_id == env["locations"]["scrap"]))
        assert scrap.qty_on_hand == 2
    nc = a.get("/quality/nonconformities?status=open")["items"][0]
    assert D(nc["cost_impact"]) == D(200)
    assert a.get("/inventory/consistency")["consistent"]


def test_resellable_return_stays_in_the_chosen_location(env):
    stock_in(env, "A", qty=10, price=100)
    d = shipped_dispatch(env, confirmed_so(env, "A", qty=4, price=200))
    a = env.api("admin1")
    before = D(a.get(f"/inventory/availability/{env['items']['A']}")["available"])
    a.post(f"/logistics/dispatches/{d['id']}/returns", {
        "location_id": env["locations"]["storage"], "return_date": str(TODAY), "reason": "No lo pidió",
        "lines": [{"dispatch_line_id": d["lines"][0]["id"], "quantity": "1"}]})
    assert D(a.get(f"/inventory/availability/{env['items']['A']}")["available"]) == before + 1


# ---------------------------------------------------------------- H-28
def test_service_invoice_without_receipt_posts_payable(env):
    a = env.api("contador")
    accounts = {x["code"]: x["id"] for x in a.get("/accounts?limit=500")["items"]}
    inv = a.post("/purchasing/invoices", {
        "supplier_id": env["supplier_id"], "supplier_invoice_number": "SRV-1", "invoice_date": str(TODAY), "currency": "COP",
        "lines": [{"description": "Servicio de mantenimiento", "expense_account_id": accounts["519530"], "quantity": "1",
                   "unit_price": "1000", "tax_id": env["iva19"]}]})
    assert inv["match_status"] == "no_receipt"
    posted = env.api("admin1").post(f"/purchasing/invoices/{inv['id']}/post")
    assert posted["status"] == "posted"
    items = a.get(f"/accounting/open-items?kind=payable&party_id={env['supplier_id']}")["items"]
    assert any(i["document_number"] in (posted["number"], "SRV-1") for i in items), items


# ---------------------------------------------------------------- H-03 y H-65
def test_company_fiscal_flags_and_party_withholdings(env):
    a = env.api("admin1")
    out = a.patch("/company/fiscal", {"is_withholding_agent": False, "is_special_taxpayer": True})
    assert out == {"is_withholding_agent": False, "is_special_taxpayer": True}
    company = a.get("/company")
    assert company["is_withholding_agent"] is False and company["is_special_taxpayer"] is True
    contador = env.api("contador")
    taxes = {t["code"]: t["id"] for t in contador.get("/taxes?limit=200")["items"]}
    assert contador.get(f"/parties/{env['supplier_id']}/withholdings")["tax_ids"] == [taxes["RTEC25"]]
    contador.put(f"/parties/{env['supplier_id']}/withholdings", {"tax_ids": [taxes["RTES4"]]})
    assert contador.get(f"/parties/{env['supplier_id']}/withholdings")["tax_ids"] == [taxes["RTES4"]]
    env.api("comprador").put(f"/parties/{env['supplier_id']}/withholdings", {"tax_ids": []}, expect=403)


# ---------------------------------------------------------------- H-61
def test_advance_cross_list_names_documents_and_can_be_voided(env):
    from test_receivables import _advance, _pay
    a = env.api("admin1")
    stock_in(env, "A", qty=10, price=100)
    d = shipped_dispatch(env, confirmed_so(env, "A", qty=2, price=200))
    inv = a.post("/einvoicing/invoices/from-dispatch", {"dispatch_id": d["id"]})
    inv = a.post(f"/einvoicing/invoices/{inv['id']}/issue")
    _pay(env, 100, [])
    adv = _advance(env)
    item = next(i for i in a.get(f"/accounting/open-items?kind=receivable&party_id={env['customer_id']}")["items"]
                if i["document_type"] != "advance")
    a.post(f"/accounting/advances/{adv['id']}/apply", {"allocations": [{"open_item_id": item["id"], "amount": "100"}]})
    row = a.get(f"/accounting/advance-applications?party_id={env['customer_id']}")["items"][0]
    assert row["advance_document"] == adv["document_number"] and row["document"] == item["document_number"]
    a.post(f"/accounting/advance-applications/{row['id']}/void", {"reason": "Cruce equivocado"})
    assert a.get(f"/accounting/advance-applications?party_id={env['customer_id']}")["items"][0]["status"] == "voided"


# ---------------------------------------------------------------- H-72
def test_manufacturing_company_starts_with_process_location(env):
    with SessionLocal() as db:
        c = build_company(db, code="MANU", sector="manufacturing", country="VE")
        types = set(db.scalars(select(Location.location_type).where(Location.company_id == c.id)))
        db.commit()
    assert "production" in types
    with SessionLocal() as db:
        assert "production" not in set(db.scalars(select(Location.location_type).where(Location.company_id == env["company_id"])))
