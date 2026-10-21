"""Integraciones entre módulos: reabastecimiento → solicitud de compra y evaluación consolidada de proveedores."""
from datetime import timedelta

from conftest import TODAY
from helpers import approved_po, receive


def test_requisition_from_replenishment(env):
    admin = env.api("admin1")
    approved_po(env, qty=10, price=120)  # fija el último precio de compra; aún sin recibir
    suggestions = {r["item_id"]: r for r in admin.get("/inventory/replenishment")}
    item_a = env["items"]["A"]
    assert item_a in suggestions and float(suggestions[item_a]["suggested_order"]) == 50
    req = admin.post("/purchasing/requisitions/from-replenishment", {"site_id": env["site_id"]}, expect=201).json()
    line = next(ln for ln in req["lines"] if ln["item_id"] == item_a)
    assert float(line["quantity"]) == 50 and float(line["estimated_unit_price"]) == 120
    assert req["status"] == "draft" and "Reabastecimiento" in req["justification"]

    custom = admin.post("/purchasing/requisitions/from-replenishment",
                        {"site_id": env["site_id"], "needed_by": str(TODAY + timedelta(days=7)),
                         "quantities": {str(item_a): "20"}}, expect=201).json()
    assert [(ln["item_id"], float(ln["quantity"])) for ln in custom["lines"]] == [(item_a, 20)]
    admin.post("/purchasing/requisitions/from-replenishment",
               {"site_id": env["site_id"], "quantities": {str(env["items"]["QC"]): "5"}}, expect=422)
    admin.post("/purchasing/requisitions/from-replenishment",
               {"site_id": env["site_id"], "quantities": {str(item_a): "0"}}, expect=422)
    env.api("vendedor").post("/purchasing/requisitions/from-replenishment", {"site_id": env["site_id"]}, expect=403)


def test_supplier_ranking(env):
    po = approved_po(env, qty=5, price=100)
    receive(env, po, 5)
    rows = env.api("admin1").get(f"/purchasing/suppliers/evaluation?start={TODAY - timedelta(days=30)}&end={TODAY}")
    assert len(rows) == 1
    row = rows[0]
    assert row["supplier_id"] == env["supplier_id"] and row["receipts"] == 1 and row["supplier_name"]
    assert row["score"] is not None
    later = f"start={TODAY + timedelta(days=1)}&end={TODAY + timedelta(days=2)}"
    assert env.api("admin1").get(f"/purchasing/suppliers/evaluation?{later}") == []
