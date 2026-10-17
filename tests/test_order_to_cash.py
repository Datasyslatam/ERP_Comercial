"""Pedido → reserva → despacho → costo de ventas → factura electrónica (sandbox) → cartera → recaudo."""
from datetime import timedelta

from helpers import (
    TODAY,
    D,
    all_entries_balanced,
    confirmed_so,
    entries_for,
    run_outbox,
    scalar,
    shipped_dispatch,
    stock_in,
)


def _invoice(env, dispatch, user="admin1"):
    a = env.api(user)
    inv = a.post("/einvoicing/invoices/from-dispatch", {"dispatch_id": dispatch["id"]})
    return a.post(f"/einvoicing/invoices/{inv['id']}/issue")


def test_full_order_to_cash(env):
    stock_in(env, "A", qty=10, price=100)
    vendedor, despacho, fact = env.api("vendedor"), env.api("despacho"), env.api("admin1")
    so = vendedor.post("/sales/orders", {
        "site_id": env["site_id"], "customer_id": env["customer_id"], "warehouse_id": env["warehouse_id"],
        "order_date": str(TODAY), "promised_date": str(TODAY + timedelta(days=2)), "currency": "COP",
        "lines": [{"item_id": env["items"]["A"], "quantity": "6", "unit_price": "200", "discount_pct": "10"}]})
    assert D(so["subtotal"]) == D(1080) and D(so["tax_total"]) == D("205.20")
    vendedor.post(f"/sales/orders/{so['id']}/confirm", expect=403)  # el vendedor no aprueba
    fact.post(f"/sales/orders/{so['id']}/confirm")
    avail = fact.get(f"/inventory/availability/{env['items']['A']}")
    assert D(avail["available"]) == D(4)

    d = despacho.post("/logistics/dispatches", {"sales_order_id": so["id"], "carrier_id": env["carrier_id"]})
    despacho.post(f"/logistics/dispatches/{d['id']}/start-picking")
    # No se puede preparar más de lo solicitado (= reservado)
    despacho.post(f"/logistics/dispatches/{d['id']}/picking",
                  {"picks": [{"dispatch_line_id": d["lines"][0]["id"], "qty_picked": "7"}]}, expect=422)
    despacho.post(f"/logistics/dispatches/{d['id']}/picking",
                  {"picks": [{"dispatch_line_id": d["lines"][0]["id"], "qty_picked": "6"}]})
    despacho.post(f"/logistics/dispatches/{d['id']}/pack", {"packages_count": 2, "gross_weight_kg": "12.5"})
    shipped = despacho.post(f"/logistics/dispatches/{d['id']}/ship", {"freight_cost": "50", "vehicle_plate": "XYZ987"})
    assert shipped["status"] == "shipped"
    cogs = entries_for("dispatch", d["id"])
    assert len(cogs) == 1 and cogs[0].total_debit == D(600)
    despacho.post(f"/logistics/dispatches/{d['id']}/deliver", {"received_by": "Juan Receptor"})

    # Factura electrónica: numeración autorizada, contabilización, cartera y envío asíncrono al adaptador sandbox
    inv = _invoice(env, d)
    assert inv["full_number"] == "SETP990000000" and inv["edoc_status"] == "pending"
    assert D(inv["total"]) == D("1285.20")
    assert run_outbox() == 1
    inv = fact.get(f"/einvoicing/invoices/{inv['id']}")
    assert inv["edoc_status"] == "accepted" and inv["edoc_environment"] == "sandbox"
    assert inv["legal_validity"] is False and "PRUEBAS" in inv["fiscal_notice"]
    assert len(inv["fiscal_uid"]) == 96  # CUFE SHA-384
    doc = env.client.get(f"/api/v1/einvoicing/invoices/{inv['id']}/document", headers=fact.headers)
    assert doc.status_code == 200 and b"<cbc:ProfileExecutionID>2</cbc:ProfileExecutionID>" in doc.content
    assert inv["fiscal_uid"].encode() in doc.content

    # Emitir dos veces no duplica número, asiento ni cartera
    fact.post(f"/einvoicing/invoices/{inv['id']}/issue")
    assert len(entries_for("sales_invoice", inv["id"])) == 1
    ar = fact.get(f"/accounting/open-items?kind=receivable&party_id={env['customer_id']}")
    assert ar["total"] == 1 and D(ar["items"][0]["open_amount"]) == D("1285.20")
    # No se puede facturar de nuevo lo ya facturado
    fact.post("/einvoicing/invoices/from-dispatch", {"dispatch_id": d["id"]}, expect=422)

    # Recaudo con retención practicada por el cliente (agente de retención): cartera saldada
    rtec = scalar("select id from taxes where code = 'RTEC25' and company_id = :c", c=env["company_id"])
    pay = fact.post("/accounting/payments", {
        "kind": "receipt", "party_id": env["customer_id"], "payment_date": str(TODAY),
        "bank_account_id": env["bank_account_id"], "method": "transfer", "currency": "COP", "amount": "1258.20",
        "idempotency_key": "recibo-0001", "withholdings": [{"tax_id": rtec, "base": "1080", "amount": "27"}],
        "allocations": [{"open_item_id": ar["items"][0]["id"], "amount": "1285.20"}]})
    assert D(pay["withholding_amount"]) == D(27)
    assert fact.get(f"/accounting/open-items?kind=receivable&party_id={env['customer_id']}")["total"] == 0
    rec = fact.get(f"/einvoicing/reconciliation?start={TODAY}&end={TODAY}")
    assert rec["ok"], rec
    assert all_entries_balanced(env["company_id"])
    # Consistencia inventario: saldos = libro de movimientos
    assert fact.get("/inventory/consistency")["consistent"]


def test_reservation_prevents_overselling(env):
    stock_in(env, "A", qty=5, price=100)
    a = env.api("admin1")
    confirmed_so(env, "A", qty=4)
    so2 = a.post("/sales/orders", {"site_id": env["site_id"], "customer_id": env["customer_id"],
                                   "warehouse_id": env["warehouse_id"], "order_date": str(TODAY), "currency": "COP",
                                   "lines": [{"item_id": env["items"]["A"], "quantity": "2"}]})
    r = a.post(f"/sales/orders/{so2['id']}/confirm", expect=422)
    assert "insuficiente" in r.json()["error"]["message"]
    # Cancelar el primer pedido libera la reserva
    first = a.get("/sales/orders?status=confirmed")["items"][0]
    a.post(f"/sales/orders/{first['id']}/cancel", {"reason": "Cliente desiste"})
    a.post(f"/sales/orders/{so2['id']}/confirm")


def test_dispatch_cannot_exceed_reserved(env):
    stock_in(env, "A", qty=10, price=10)
    so = confirmed_so(env, "A", qty=3)
    a = env.api("admin1")
    r = a.post("/logistics/dispatches", {"sales_order_id": so["id"], "lines": [
        {"so_line_id": so["lines"][0]["id"], "quantity": "4"}]}, expect=422)
    assert "reservado" in r.json()["error"]["message"]
    d = a.post("/logistics/dispatches", {"sales_order_id": so["id"], "lines": [
        {"so_line_id": so["lines"][0]["id"], "quantity": "2"}]})
    # Un segundo despacho abierto solo puede tomar lo que queda reservado (1)
    a.post("/logistics/dispatches", {"sales_order_id": so["id"], "lines": [
        {"so_line_id": so["lines"][0]["id"], "quantity": "2"}]}, expect=422)
    assert d["lines"][0]["qty_requested"]


def test_fefo_reservation_by_expiry(env):
    stock_in(env, "LOT", qty=5, price=10, lot="L-LATE", expiry=TODAY + timedelta(days=200))
    stock_in(env, "LOT", qty=5, price=10, lot="L-SOON", expiry=TODAY + timedelta(days=20))
    stock_in(env, "LOT", qty=5, price=10, lot="L-EXPIRED", expiry=TODAY - timedelta(days=1))
    so = confirmed_so(env, "LOT", qty=7)
    res = env.api("admin1").get(f"/inventory/reservations?item_id={env['items']['LOT']}")["items"]
    lots = {r["lot_id"]: D(r["quantity"]) for r in res}
    names = {x["id"]: x["lot_number"] for x in env.api("admin1").get(f"/inventory/lots?item_id={env['items']['LOT']}")["items"]}
    by_name = {names[k]: v for k, v in lots.items()}
    assert by_name == {"L-SOON": D(5), "L-LATE": D(2)}  # el lote vencido no se reserva
    shipped_dispatch(env, so)


def test_credit_note_and_customer_return(env):
    stock_in(env, "A", qty=10, price=100)
    so = confirmed_so(env, "A", qty=5, price=200)
    d = shipped_dispatch(env, so)
    inv = _invoice(env, d)
    run_outbox()
    a = env.api("admin1")
    ret = a.post(f"/logistics/dispatches/{d['id']}/returns", {
        "location_id": env["locations"]["storage"], "return_date": str(TODAY), "reason": "Producto no solicitado",
        "lines": [{"dispatch_line_id": d["lines"][0]["id"], "quantity": "2"}]})
    assert ret["status"] == "received"
    assert len(entries_for("customer_return", ret["id"])) == 1
    note = a.post(f"/einvoicing/invoices/{inv['id']}/notes", {
        "doc_type": "credit_note", "correction_code": "1", "reason": "Devolución parcial de 2 unidades",
        "lines": [{"invoice_line_id": inv["lines"][0]["id"], "quantity": "2"}]})
    note = a.post(f"/einvoicing/invoices/{note['id']}/issue")
    assert note["full_number"] == "NC1"
    run_outbox()
    note = a.get(f"/einvoicing/invoices/{note['id']}")
    assert note["edoc_status"] == "accepted", note["edoc_message"]
    ar = a.get(f"/accounting/open-items?kind=receivable&party_id={env['customer_id']}")["items"][0]
    assert D(ar["open_amount"]) == D(inv["total"]) - D(note["total"])
    # Una nota que excede el saldo de la línea se rechaza
    a.post(f"/einvoicing/invoices/{inv['id']}/notes", {
        "doc_type": "credit_note", "correction_code": "1", "reason": "Excede",
        "lines": [{"invoice_line_id": inv["lines"][0]["id"], "quantity": "4"}]}, expect=422)
    assert a.get("/inventory/consistency")["consistent"]


def test_einvoice_rejected_then_resent(env):
    stock_in(env, "A", qty=5, price=10)
    from app.core.db import SessionLocal
    from app.modules.masters.models import Party

    with SessionLocal() as db:
        db.get(Party, env["customer_id"]).email = None  # dato obligatorio faltante
        db.commit()
    so = confirmed_so(env, "A", qty=1)
    inv = _invoice(env, shipped_dispatch(env, so))
    run_outbox()
    a = env.api("admin1")
    inv = a.get(f"/einvoicing/invoices/{inv['id']}")
    assert inv["edoc_status"] == "rejected" and "correo" in inv["edoc_message"]
    with SessionLocal() as db:
        db.get(Party, env["customer_id"]).email = "corregido@pruebas.datasys.co"
        db.commit()
    a.post(f"/einvoicing/invoices/{inv['id']}/resend")
    run_outbox()
    inv = a.get(f"/einvoicing/invoices/{inv['id']}")
    assert inv["edoc_status"] == "accepted" and inv["full_number"] == "SETP990000000"
    assert [s["result_status"] for s in inv["submissions"]] == ["rejected", "accepted"]


def test_credit_limit_blocks_confirmation(env):
    stock_in(env, "A", qty=5, price=10)
    a = env.api("admin1")
    a.patch(f"/parties/{env['customer_id']}", {"credit_limit": "100"})
    so = a.post("/sales/orders", {"site_id": env["site_id"], "customer_id": env["customer_id"],
                                  "warehouse_id": env["warehouse_id"], "order_date": str(TODAY), "currency": "COP",
                                  "lines": [{"item_id": env["items"]["A"], "quantity": "1", "unit_price": "500"}]})
    r = a.post(f"/sales/orders/{so['id']}/confirm", expect=422)
    assert "cupo" in r.json()["error"]["message"]
