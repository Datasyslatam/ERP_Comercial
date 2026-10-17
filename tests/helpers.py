"""Flujos reutilizables para pruebas de integración (siempre a través de la API HTTP)."""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text

from app.core.db import SessionLocal

TODAY = date.today()


def D(x) -> Decimal:
    return Decimal(str(x))


def approved_po(env, item_key="A", qty=10, price=100, creator="admin1", approver="admin2", expected=None):
    a, b = env.api(creator), env.api(approver)
    po = a.post("/purchasing/orders", {
        "site_id": env["site_id"], "supplier_id": env["supplier_id"], "warehouse_id": env["warehouse_id"],
        "order_date": str(TODAY), "expected_date": str(expected or TODAY + timedelta(days=5)), "currency": "COP",
        "lines": [{"item_id": env["items"][item_key], "quantity": str(qty), "unit_price": str(price),
                   "tax_id": env["iva19"]}]})
    a.post(f"/purchasing/orders/{po['id']}/submit")
    b.post(f"/purchasing/orders/{po['id']}/decision", {"approve": True})
    return po


def receive(env, po, qty, user="admin1", lot=None, expiry=None):
    line = {"po_line_id": po["lines"][0]["id"], "quantity": str(qty)}
    if lot:
        line["lot_number"] = lot
    if expiry:
        line["expiry_date"] = str(expiry)
    return env.api(user).post(f"/purchasing/orders/{po['id']}/receipts",
                              {"receipt_date": str(TODAY), "lines": [line]})


def stock_in(env, item_key="A", qty=10, price=100, lot=None, expiry=None):
    po = approved_po(env, item_key, qty, price)
    return po, receive(env, po, qty, lot=lot, expiry=expiry)


def confirmed_so(env, item_key="A", qty=5, price=150, user="admin1", promised=None):
    a = env.api(user)
    so = a.post("/sales/orders", {
        "site_id": env["site_id"], "customer_id": env["customer_id"], "warehouse_id": env["warehouse_id"],
        "order_date": str(TODAY), "promised_date": str(promised or TODAY + timedelta(days=3)), "currency": "COP",
        "lines": [{"item_id": env["items"][item_key], "quantity": str(qty), "unit_price": str(price)}]})
    a.post(f"/sales/orders/{so['id']}/confirm")
    return so


def shipped_dispatch(env, so, user="admin1", freight=0):
    a = env.api(user)
    d = a.post("/logistics/dispatches", {"sales_order_id": so["id"], "carrier_id": env["carrier_id"]})
    a.post(f"/logistics/dispatches/{d['id']}/start-picking")
    a.post(f"/logistics/dispatches/{d['id']}/picking",
           {"picks": [{"dispatch_line_id": ln["id"], "qty_picked": ln["qty_requested"]} for ln in d["lines"]]})
    a.post(f"/logistics/dispatches/{d['id']}/pack", {"packages_count": 1, "gross_weight_kg": "10"})
    return a.post(f"/logistics/dispatches/{d['id']}/ship", {"freight_cost": str(freight), "vehicle_plate": "ABC123"})


def run_outbox():
    from app.core.outbox import process_batch

    return process_batch(SessionLocal)


def scalar(sql, **params):
    with SessionLocal() as db:
        return db.execute(text(sql), params).scalar()


def entries_for(source_type, source_id):
    from app.modules.accounting.models import JournalEntry

    with SessionLocal() as db:
        return db.scalars(select(JournalEntry).where(JournalEntry.source_type == source_type,
                                                     JournalEntry.source_id == source_id)).all()


def all_entries_balanced(company_id) -> bool:
    return scalar("""select count(*) from (select e.id from journal_entries e join journal_lines l on l.entry_id = e.id
        where e.company_id = :c group by e.id having sum(l.debit) <> sum(l.credit)) x""", c=company_id) == 0


def count(model, **filters):
    with SessionLocal() as db:
        stmt = select(func.count()).select_from(model)
        for k, v in filters.items():
            stmt = stmt.where(getattr(model, k) == v)
        return db.scalar(stmt)
