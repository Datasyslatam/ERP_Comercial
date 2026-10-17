"""Inspección de recepción: cuarentena, liberación, rechazo con devolución, no conformidad y CAPA."""
from helpers import TODAY, D, approved_po, confirmed_so, entries_for, receive


def _plan(env):
    return env.api("calidad").post("/quality/plans", {
        "code": "PL-REC", "name": "Inspección de recepción", "stage": "receiving", "item_id": env["items"]["QC"],
        "characteristics": [
            {"name": "Diámetro", "kind": "numeric", "lower_limit": "9.8", "upper_limit": "10.2", "unit": "mm",
             "is_critical": True},
            {"name": "Empaque íntegro", "kind": "boolean"}]})


def test_receipt_goes_to_quarantine_and_is_not_reservable(env):
    _plan(env)
    po = approved_po(env, "QC", qty=10, price=40)
    gr = receive(env, po, 10, lot="QC-001")
    assert gr["lines"][0]["inspection_status"] == "pending"
    a = env.api("admin1")
    lot = a.get(f"/inventory/lots?item_id={env['items']['QC']}")["items"][0]
    assert lot["status"] == "quarantine"
    assert D(a.get(f"/inventory/availability/{env['items']['QC']}")["available"]) == 0
    r = a.post("/sales/orders", {"site_id": env["site_id"], "customer_id": env["customer_id"],
                                 "warehouse_id": env["warehouse_id"], "order_date": str(TODAY), "currency": "COP",
                                 "lines": [{"item_id": env["items"]["QC"], "quantity": "1", "unit_price": "1"}]})
    a.post(f"/sales/orders/{r['id']}/confirm", expect=422)
    # Sin inspección aceptada no se puede facturar al proveedor lo recibido
    c = env.api("contador")
    c.post("/purchasing/invoices", {"supplier_id": env["supplier_id"], "supplier_invoice_number": "Q-1",
                                    "invoice_date": str(TODAY), "currency": "COP",
                                    "lines": [{"receipt_line_id": gr["lines"][0]["id"], "description": "QC",
                                               "quantity": "1", "unit_price": "40"}]}, expect=422)


def test_partial_acceptance_releases_and_returns(env):
    plan = _plan(env)
    chars = {c["name"]: c["id"] for c in plan["characteristics"]}
    po = approved_po(env, "QC", qty=10, price=40)
    receive(env, po, 10, lot="QC-002")
    insp_user = env.api("calidad")
    insp = insp_user.get("/quality/inspections?status=pending")["items"][0]
    # Característica crítica fuera de tolerancia impide aceptar sin concesión
    bad = [{"characteristic_id": chars["Diámetro"], "numeric_value": "10.5"},
           {"characteristic_id": chars["Empaque íntegro"], "bool_value": True}]
    insp_user.post(f"/quality/inspections/{insp['id']}/result",
                   {"qty_accepted": "7", "qty_rejected": "3", "results": bad}, expect=422)
    ok = [{"characteristic_id": chars["Diámetro"], "numeric_value": "10.0"},
          {"characteristic_id": chars["Empaque íntegro"], "bool_value": False}]
    res = insp_user.post(f"/quality/inspections/{insp['id']}/result",
                         {"qty_accepted": "7", "qty_rejected": "3", "results": ok, "nc_category": "empaque"})
    assert res["status"] == "partial"
    a = env.api("admin1")
    assert D(a.get(f"/inventory/availability/{env['items']['QC']}")["available"]) == 7
    # Devolución al proveedor: reversa contra recepciones por facturar y genera NC automática
    assert len(entries_for("inspection", insp["id"])) == 1
    nc = a.get("/quality/nonconformities")["items"][0]
    assert nc["source"] == "inspection" and D(nc["quantity_affected"]) == 3 and D(nc["cost_impact"]) == D(120)
    po_after = a.get(f"/purchasing/orders/{po['id']}")
    assert D(po_after["lines"][0]["qty_rejected"]) == 3 and po_after["status"] == "partially_received"
    # El lote aceptado parcialmente queda liberado y reservable
    confirmed_so(env, "QC", qty=7, price=60)
    assert a.get("/inventory/consistency")["consistent"]

    # Flujo CAPA: no se definen acciones sin causa raíz; no se cierra con acciones abiertas
    q = env.api("calidad")
    q.post(f"/quality/nonconformities/{nc['id']}/advance", {"to_status": "analysis"})
    q.post(f"/quality/nonconformities/{nc['id']}/advance", {"to_status": "action"}, expect=422)
    q.post(f"/quality/nonconformities/{nc['id']}/advance",
           {"to_status": "action", "root_cause": "Proveedor cambió el material de empaque", "root_cause_method": "5why"})
    act = q.post(f"/quality/nonconformities/{nc['id']}/actions",
                 {"action_type": "corrective", "description": "Exigir ficha técnica del empaque",
                  "due_date": str(TODAY)})
    q.post(f"/quality/nonconformities/{nc['id']}/advance", {"to_status": "verification"}, expect=422)
    q.post(f"/quality/actions/{act['id']}/status", {"status": "done"})
    q.post(f"/quality/nonconformities/{nc['id']}/advance", {"to_status": "verification"})
    closed = q.post(f"/quality/nonconformities/{nc['id']}/advance", {"to_status": "closed"})
    assert closed["status"] == "closed" and closed["closed_at"]
    hist = q.get(f"/quality/history?supplier_id={env['supplier_id']}")
    assert len(hist["inspections"]) == 1 and len(hist["nonconformities"]) == 1


def test_full_rejection_blocks_lot(env):
    _plan(env)
    po = approved_po(env, "QC", qty=4, price=40)
    receive(env, po, 4, lot="QC-003")
    q = env.api("calidad")
    insp = q.get("/quality/inspections?status=pending")["items"][0]
    chars = q.get(f"/quality/inspections/{insp['id']}")["plan"]["characteristics"]
    q.post(f"/quality/inspections/{insp['id']}/result", {"qty_accepted": "0", "qty_rejected": "4", "results": [
        {"characteristic_id": chars[0]["id"], "numeric_value": "11"},
        {"characteristic_id": chars[1]["id"], "bool_value": True}]})
    lot = q.get(f"/inventory/lots?item_id={env['items']['QC']}")["items"][0]
    assert lot["status"] == "blocked"
    stock = env.api("admin1").get(f"/inventory/stock?item_id={env['items']['QC']}")
    assert stock == []  # todo devuelto al proveedor
