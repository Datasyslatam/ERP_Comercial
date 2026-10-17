"""Inventario: no negativos, inmutabilidad del libro, ajustes con aprobación, conteo físico y kardex."""
import pytest
from helpers import TODAY, D, entries_for, stock_in
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.db import SessionLocal


def test_negative_stock_is_impossible(env):
    stock_in(env, "A", qty=3, price=50)
    a, b = env.api("admin1"), env.api("admin2")
    doc = a.post("/inventory/documents", {"doc_type": "consumption", "doc_date": str(TODAY),
                                          "reason": "Consumo interno de prueba", "cost_center_id": None,
                                          "lines": [{"item_id": env["items"]["A"], "quantity": "5",
                                                     "from_location_id": env["locations"]["storage"]}]}, expect=422)
    assert "centro de costo" in doc.json()["error"]["message"]
    doc = a.post("/inventory/documents", {"doc_type": "adjustment", "doc_date": str(TODAY), "reason": "Merma",
                                          "lines": [{"item_id": env["items"]["A"], "quantity": "-5",
                                                     "from_location_id": env["locations"]["storage"]}]})
    b.post(f"/inventory/documents/{doc['id']}/approve")
    r = b.post(f"/inventory/documents/{doc['id']}/post", expect=422)
    assert "insuficiente" in r.json()["error"]["message"]
    # Defensa en la base de datos: la restricción CHECK impide saldos negativos aun saltando el servicio
    with SessionLocal() as db, pytest.raises(IntegrityError):
        db.execute(text("update stock_balances set qty_on_hand = -1"))
        db.commit()


def test_stock_moves_are_append_only(env):
    stock_in(env, "A", qty=1, price=1)
    with SessionLocal() as db, pytest.raises(DBAPIError):
        db.execute(text("update stock_moves set quantity = 99"))
        db.commit()
    with SessionLocal() as db, pytest.raises(DBAPIError):
        db.execute(text("delete from stock_moves"))
        db.commit()


def test_adjustment_requires_approval_by_another_user(env):
    stock_in(env, "A", qty=10, price=20)
    a, b = env.api("admin1"), env.api("admin2")
    doc = a.post("/inventory/documents", {"doc_type": "adjustment", "doc_date": str(TODAY),
                                          "reason": "Sobrante encontrado", "lines": [
                                              {"item_id": env["items"]["A"], "quantity": "2",
                                               "to_location_id": env["locations"]["storage"]}]})
    a.post(f"/inventory/documents/{doc['id']}/post", expect=422)  # sin aprobar
    a.post(f"/inventory/documents/{doc['id']}/approve", expect=403)  # SoD
    b.post(f"/inventory/documents/{doc['id']}/approve")
    posted = b.post(f"/inventory/documents/{doc['id']}/post")
    assert posted["status"] == "posted"
    je = entries_for("inventory_document", doc["id"])
    assert len(je) == 1 and je[0].total_debit == D(40)  # 2 × costo promedio 20


def test_transfer_and_weighted_average_cost(env):
    stock_in(env, "A", qty=10, price=100)
    stock_in(env, "A", qty=10, price=200)
    a = env.api("admin1")
    assert D(a.get(f"/inventory/availability/{env['items']['A']}")["avg_cost"]) == D(150)
    doc = a.post("/inventory/documents", {"doc_type": "transfer", "doc_date": str(TODAY), "reason": "Reubicación",
                                          "lines": [{"item_id": env["items"]["A"], "quantity": "4",
                                                     "from_location_id": env["locations"]["storage"],
                                                     "to_location_id": env["locations"]["dispatch"]}]})
    a.post(f"/inventory/documents/{doc['id']}/post")
    by_loc = {r["location_id"]: D(r["qty_on_hand"]) for r in a.get(f"/inventory/stock?item_id={env['items']['A']}")}
    assert by_loc == {env["locations"]["storage"]: D(16), env["locations"]["dispatch"]: D(4)}
    k = a.get(f"/inventory/kardex/{env['items']['A']}?start={TODAY}&end={TODAY}")
    assert D(k["closing_qty"]) == D(20) and D(k["closing_value"]) == D(3000)
    assert len(k["moves"]) == 2  # la transferencia interna no altera el saldo de la empresa


def test_blind_physical_count_with_differences(env):
    stock_in(env, "A", qty=10, price=10)
    a, b = env.api("admin1"), env.api("almacen")
    cnt = b.post("/inventory/counts", {"warehouse_id": env["warehouse_id"], "count_date": str(TODAY)})
    view = b.get(f"/inventory/counts/{cnt['id']}")
    assert "system_qty" not in view["lines"][0]  # conteo ciego para el contador
    b.post(f"/inventory/counts/{cnt['id']}/entries", {"entries": [
        {"item_id": env["items"]["A"], "location_id": env["locations"]["storage"], "counted_qty": "8"}]})
    b.post(f"/inventory/counts/{cnt['id']}/close", expect=403)  # quien cuenta no aprueba
    closed = a.post(f"/inventory/counts/{cnt['id']}/close")
    assert closed["status"] == "posted"
    assert D(a.get(f"/inventory/availability/{env['items']['A']}")["available"]) == 8
    assert len(entries_for("physical_count", cnt["id"])) == 1
    assert a.get("/inventory/consistency")["consistent"]


def test_lot_and_expiry_required(env):
    from helpers import approved_po

    po = approved_po(env, "LOT", qty=1, price=1)
    r = env.api("admin1").post(f"/purchasing/orders/{po['id']}/receipts", {"receipt_date": str(TODAY), "lines": [
        {"po_line_id": po["lines"][0]["id"], "quantity": "1", "lot_number": "L1"}]}, expect=422)
    assert "vencimiento" in r.json()["error"]["message"]
