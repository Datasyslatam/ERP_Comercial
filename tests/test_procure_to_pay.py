"""Ciclo completo de abastecimiento con trazabilidad de extremo a extremo hasta la contabilidad y el pago."""
from datetime import timedelta
from decimal import Decimal

from helpers import TODAY, D, all_entries_balanced, approved_po, entries_for, receive, scalar


def test_full_procure_to_pay_flow(env):
    comprador, aprobador, admin2 = env.api("comprador"), env.api("aprobador"), env.api("admin2")
    item = env["items"]["A"]

    # 1. Solicitud → aprobación por otro usuario
    req = comprador.post("/purchasing/requisitions", {"site_id": env["site_id"], "justification": "Reposición",
                                                      "lines": [{"item_id": item, "quantity": "20",
                                                                 "estimated_unit_price": "100"}]})
    comprador.post(f"/purchasing/requisitions/{req['id']}/submit")
    aprobador.post(f"/purchasing/requisitions/{req['id']}/decision", {"approve": True})

    # 2. Cotizaciones y comparación
    rfq = comprador.post("/purchasing/rfqs", {"requisition_id": req["id"]})
    rl = req["lines"][0]["id"]
    with __import__("app.core.db", fromlist=["SessionLocal"]).SessionLocal() as db:
        from app.modules.masters.models import Party
        from app.modules.masters.validation import nit_check_digit

        p2 = Party(company_id=env["company_id"], code="PRO2", legal_name="Proveedor 2", id_type="NIT",
                   tax_id="901000111", check_digit=nit_check_digit("901000111"), is_supplier=True)
        db.add(p2)
        db.commit()
        sup2 = p2.id
    q1 = comprador.post(f"/purchasing/rfqs/{rfq['id']}/quotes", {
        "supplier_id": env["supplier_id"], "quote_date": str(TODAY), "currency": "COP", "delivery_days": 5,
        "lines": [{"requisition_line_id": rl, "quantity": "20", "unit_price": "95", "tax_id": env["iva19"]}]})
    comprador.post(f"/purchasing/rfqs/{rfq['id']}/quotes", {
        "supplier_id": sup2, "quote_date": str(TODAY), "currency": "COP", "delivery_days": 2,
        "lines": [{"requisition_line_id": rl, "quantity": "20", "unit_price": "99", "tax_id": env["iva19"]}]})
    cmp_ = comprador.get(f"/purchasing/rfqs/{rfq['id']}/comparison")
    assert cmp_["recommended_quote_id"] == q1["id"]
    assert D(cmp_["lines"][0]["best"]["unit_price"]) == D(95)

    # 3. Adjudicación → OC → aprobación (límite + SoD)
    po = comprador.post(f"/purchasing/rfqs/{rfq['id']}/award", {"quote_id": q1["id"], "warehouse_id": env["warehouse_id"]})
    assert D(po["subtotal"]) == D(1900) and D(po["tax_total"]) == D(361)
    comprador.post(f"/purchasing/orders/{po['id']}/submit")
    decided = aprobador.post(f"/purchasing/orders/{po['id']}/decision", {"approve": True})
    assert decided["status"] == "approved" and decided["budget_check"]["budget"] is None

    # 4. Recepción parcial → inventario + asiento (inventario vs recepciones por facturar)
    gr = receive(env, po, 12, user="almacen")
    stock = admin2.get(f"/inventory/stock?item_id={item}")
    assert sum(D(r["qty_on_hand"]) for r in stock) == D(12)
    je = entries_for("goods_receipt", gr["id"])
    assert len(je) == 1 and je[0].total_debit == D(1140)
    assert admin2.get(f"/purchasing/orders/{po['id']}")["status"] == "partially_received"

    # Sobre-recepción rechazada (tolerancia 0 %)
    r = env.api("almacen").post(f"/purchasing/orders/{po['id']}/receipts", {"receipt_date": str(TODAY), "lines": [
        {"po_line_id": po["lines"][0]["id"], "quantity": "9"}]}, expect=422)
    assert "pendientes" in r.json()["error"]["message"]
    receive(env, po, 8, user="almacen")
    assert admin2.get(f"/purchasing/orders/{po['id']}")["status"] == "received"

    # 5. Factura del proveedor con cruce a tres vías y retención en la fuente (somos agentes de retención)
    contador = env.api("contador")
    rlines = admin2.get(f"/purchasing/orders/{po['id']}")["receipts"]
    inv = contador.post("/purchasing/invoices", {
        "supplier_id": env["supplier_id"], "supplier_invoice_number": "FE-1001", "invoice_date": str(TODAY),
        "currency": "COP", "lines": [{"receipt_line_id": g["lines"][0]["id"], "description": "Artículo A",
                                      "quantity": g["lines"][0]["quantity"], "unit_price": "95"} for g in rlines]})
    assert D(inv["subtotal"]) == D(1900) and D(inv["tax_total"]) == D(361)
    assert D(inv["withholding_total"]) == D("47.50")  # 2,5 % retención compras
    assert D(inv["payable_total"]) == D("2213.50")

    # Factura duplicada del mismo proveedor → rechazada
    r = contador.post("/purchasing/invoices", {
        "supplier_id": env["supplier_id"], "supplier_invoice_number": "FE-1001", "invoice_date": str(TODAY),
        "currency": "COP", "lines": [{"expense_account_id": 1, "description": "x", "quantity": "1", "unit_price": "1"}]},
        expect=409)
    # Facturar más de lo recibido → rechazado
    r = contador.post("/purchasing/invoices", {
        "supplier_id": env["supplier_id"], "supplier_invoice_number": "FE-1002", "invoice_date": str(TODAY),
        "currency": "COP", "lines": [{"receipt_line_id": rlines[0]["lines"][0]["id"], "description": "x",
                                      "quantity": "1", "unit_price": "95"}]}, expect=422)
    assert "recibido" in r.json()["error"]["message"]

    # 6. Contabilización idempotente: dos llamadas, un solo asiento y una partida por pagar
    contador.post(f"/purchasing/invoices/{inv['id']}/post")
    contador.post(f"/purchasing/invoices/{inv['id']}/post")
    assert len(entries_for("supplier_invoice", inv["id"])) == 1
    payables = contador.get(f"/accounting/open-items?kind=payable&party_id={env['supplier_id']}")
    assert payables["total"] == 1 and D(payables["items"][0]["open_amount"]) == D("2213.50")
    # El saldo de "recepciones por facturar" queda en cero tras el cruce
    grni = scalar("""select coalesce(sum(l.debit - l.credit), 0) from journal_lines l join accounts a on a.id = l.account_id
                     where a.code = '233595' and l.company_id = :c""", c=env["company_id"])
    assert grni == 0

    # 7. Pago al proveedor (idempotente por clave)
    tesoreria = env.api("admin1")
    body = {"kind": "disbursement", "party_id": env["supplier_id"], "payment_date": str(TODAY),
            "bank_account_id": env["bank_account_id"], "method": "transfer", "currency": "COP", "amount": "2213.50",
            "idempotency_key": "pago-FE-1001", "allocations": [{"open_item_id": payables["items"][0]["id"],
                                                                "amount": "2213.50"}]}
    p1 = tesoreria.post("/accounting/payments", body)
    p2 = tesoreria.post("/accounting/payments", body)
    assert p1["id"] == p2["id"]
    assert contador.get(f"/accounting/open-items?kind=payable&party_id={env['supplier_id']}")["total"] == 0
    assert all_entries_balanced(env["company_id"])

    # 8. Trazabilidad: OC → recepciones → factura → asientos
    trace = admin2.get(f"/purchasing/orders/{po['id']}")
    assert len(trace["receipts"]) == 2 and trace["invoices"][0]["journal_entry_id"]
    assert trace["requisition_id"] == req["id"]


def test_price_tolerance_and_supplier_evaluation(env):
    po = approved_po(env, qty=5, price=100, expected=TODAY + timedelta(days=1))
    gr = receive(env, po, 5)
    c = env.api("contador")
    r = c.post("/purchasing/invoices", {
        "supplier_id": env["supplier_id"], "supplier_invoice_number": "X-1", "invoice_date": str(TODAY),
        "currency": "COP", "lines": [{"receipt_line_id": gr["lines"][0]["id"], "description": "A", "quantity": "5",
                                      "unit_price": "110"}]}, expect=422)
    assert "tolerancia" in r.json()["error"]["message"]
    ev = c.get(f"/purchasing/suppliers/{env['supplier_id']}/evaluation?start={TODAY - timedelta(days=1)}&end={TODAY}",
               expect=403)  # el contador no tiene permiso de evaluación
    ev = env.api("comprador").get(
        f"/purchasing/suppliers/{env['supplier_id']}/evaluation?start={TODAY - timedelta(days=1)}&end={TODAY}")
    assert ev["receipts"] == 1 and Decimal(str(ev["on_time_pct"])) == 100


def test_cannot_receive_unapproved_order(env):
    a = env.api("admin1")
    po = a.post("/purchasing/orders", {"site_id": env["site_id"], "supplier_id": env["supplier_id"],
                                      "warehouse_id": env["warehouse_id"], "order_date": str(TODAY), "currency": "COP",
                                      "lines": [{"item_id": env["items"]["A"], "quantity": "1", "unit_price": "1"}]})
    r = a.post(f"/purchasing/orders/{po['id']}/receipts", {"receipt_date": str(TODAY), "lines": [
        {"po_line_id": po["lines"][0]["id"], "quantity": "1"}]}, expect=422)
    assert "aprobadas" in r.json()["error"]["message"]


def test_budget_block_policy(env):
    admin = env.api("admin1")
    admin.post("/accounting/budgets", {"year": TODAY.year, "month": TODAY.month, "category": "purchases",
                                       "amount": "500"})
    admin.patch("/company/settings", {"settings": {"purchase_budget_control": "block"}})
    a = env.api("admin1")
    po = a.post("/purchasing/orders", {"site_id": env["site_id"], "supplier_id": env["supplier_id"],
                                      "warehouse_id": env["warehouse_id"], "order_date": str(TODAY), "currency": "COP",
                                      "lines": [{"item_id": env["items"]["A"], "quantity": "10", "unit_price": "100"}]})
    a.post(f"/purchasing/orders/{po['id']}/submit")
    r = env.api("admin2").post(f"/purchasing/orders/{po['id']}/decision", {"approve": True}, expect=422)
    assert "presupuesto" in r.json()["error"]["message"]
