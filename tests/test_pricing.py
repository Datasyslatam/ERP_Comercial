"""Listas de precios con tramos, promociones, anulación de cotizaciones y edición de borradores."""
from datetime import timedelta

from conftest import TODAY
from helpers import D, stock_in

from app.core.db import SessionLocal
from app.modules.masters.models import Party


def _quote(env, user="vendedor", qty=5, unit_price=None, discount=None, customer=None):
    line = {"item_id": env["items"]["A"], "quantity": str(qty)}
    if unit_price is not None:
        line["unit_price"] = str(unit_price)
    if discount is not None:
        line["discount_pct"] = str(discount)
    return env.api(user).post("/sales/quotes", {
        "site_id": env["site_id"], "customer_id": customer or env["customer_id"], "quote_date": str(TODAY),
        "valid_until": str(TODAY + timedelta(days=10)), "currency": "COP", "lines": [line]})


def _other_customer(env) -> int:
    with SessionLocal() as db:
        c = Party(company_id=env["company_id"], code="CLI2", legal_name="Otro cliente S.A.S.", id_type="NIT",
                  tax_id="900777888", check_digit="1", is_customer=True)
        db.add(c)
        db.commit()
        return c.id


def _price_lists(env):
    admin = env.api("admin1")
    default = admin.post("/sales/price-lists", {"code": "GENERAL", "name": "General", "currency": "COP",
                                                "valid_from": str(TODAY), "is_default": True}, expect=201).json()
    admin.put(f"/sales/price-lists/{default['id']}/items",
              {"items": [{"item_id": env["items"]["A"], "min_qty": "1", "unit_price": "140"}]})
    vip = admin.post("/sales/price-lists", {"code": "VIP", "name": "Mayoristas", "currency": "COP",
                                            "valid_from": str(TODAY)}, expect=201).json()
    admin.put(f"/sales/price-lists/{vip['id']}/items", {"items": [
        {"item_id": env["items"]["A"], "min_qty": "1", "unit_price": "130"},
        {"item_id": env["items"]["A"], "min_qty": "10", "unit_price": "120"}]})
    admin.put(f"/sales/price-lists/{vip['id']}/customers", {"customer_ids": [env["customer_id"]]})
    return default, vip


def test_price_resolution_customer_list_tiers_default_and_item_price(env):
    q = _quote(env)
    assert D(q["lines"][0]["unit_price"]) == 150 and q["lines"][0]["price_source"] == "list_price"
    default, vip = _price_lists(env)
    q = _quote(env, qty=5)
    assert D(q["lines"][0]["unit_price"]) == 130 and q["lines"][0]["price_source"] == "price_list"
    assert D(_quote(env, qty=12)["lines"][0]["unit_price"]) == 120  # tramo por volumen
    other = _other_customer(env)
    assert D(_quote(env, customer=other)["lines"][0]["unit_price"]) == 140  # lista predeterminada
    manual = _quote(env, unit_price=99)
    assert D(manual["lines"][0]["unit_price"]) == 99 and manual["lines"][0]["price_source"] == "manual"
    detail = env.api("vendedor").get(f"/sales/price-lists/{vip['id']}")
    assert detail["customers"][0]["id"] == env["customer_id"] and detail["items_count"] == 2
    # Lista vencida o inactiva: se cae a la predeterminada
    env.api("admin1").patch(f"/sales/price-lists/{vip['id']}", {"is_active": False})
    assert D(_quote(env)["lines"][0]["unit_price"]) == 140


def test_single_default_list_per_currency(env):
    default, _ = _price_lists(env)
    admin = env.api("admin1")
    new_default = admin.post("/sales/price-lists", {"code": "G2", "name": "General 2027", "currency": "COP",
                                                    "valid_from": str(TODAY), "is_default": True}, expect=201).json()
    lists = {pl["code"]: pl for pl in admin.get("/sales/price-lists")}
    assert lists["G2"]["is_default"] and not lists["GENERAL"]["is_default"] and new_default["is_default"]
    admin.post("/sales/price-lists", {"code": "G2", "name": "dup", "currency": "COP", "valid_from": str(TODAY)}, expect=409)
    env.api("vendedor").post("/sales/price-lists", {"code": "X", "name": "Sin permiso", "currency": "COP",
                                                    "valid_from": str(TODAY)}, expect=403)


def test_promotions_best_discount_scope_and_manual_override(env):
    admin = env.api("admin1")
    base = {"valid_from": str(TODAY), "valid_to": str(TODAY + timedelta(days=30))}
    admin.post("/sales/promotions", {**base, "code": "CAT5", "name": "Mercancía 5 %", "discount_pct": "5",
                                     "category_id": env["category_id"]}, expect=201)
    admin.post("/sales/promotions", {**base, "code": "A8", "name": "Artículo A por volumen", "discount_pct": "8",
                                     "item_id": env["items"]["A"], "min_qty": "10"}, expect=201)
    other = _other_customer(env)
    admin.post("/sales/promotions", {**base, "code": "VIP20", "name": "Solo otro cliente", "discount_pct": "20",
                                     "customer_id": other}, expect=201)
    old = admin.post("/sales/promotions", {"code": "OLD", "name": "Vencida", "discount_pct": "50",
                                           "valid_from": str(TODAY - timedelta(days=30)),
                                           "valid_to": str(TODAY - timedelta(days=1))}, expect=201).json()
    assert old["state"] == "expired"

    q5 = _quote(env, qty=5)["lines"][0]
    assert D(q5["discount_pct"]) == 5 and q5["promotion_id"]
    q12 = _quote(env, qty=12)["lines"][0]
    assert D(q12["discount_pct"]) == 8  # gana el mayor descuento aplicable
    assert D(_quote(env, qty=5, customer=other)["lines"][0]["discount_pct"]) == 20
    manual = _quote(env, qty=12, discount=0)["lines"][0]
    assert D(manual["discount_pct"]) == 0 and manual["promotion_id"] is None
    admin.post("/sales/promotions", {**base, "code": "BAD", "name": "Doble alcance", "discount_pct": "3",
                                     "item_id": env["items"]["A"], "category_id": env["category_id"]}, expect=422)
    preview = env.api("vendedor").post("/sales/pricing", {"customer_id": env["customer_id"], "currency": "COP",
                                                          "lines": [{"item_id": env["items"]["A"], "quantity": "12"}]})
    assert D(preview["lines"][0]["discount_pct"]) == 8 and preview["lines"][0]["promotion"] == "Artículo A por volumen"


def test_quote_conversion_keeps_quoted_conditions(env):
    stock_in(env, qty=20)
    _price_lists(env)
    q = _quote(env, qty=12)
    so = env.api("vendedor").post(f"/sales/quotes/{q['id']}/convert", {"warehouse_id": env["warehouse_id"]},
                                  expect=201).json()
    # Aunque la lista cambie después, el pedido respeta lo cotizado
    assert D(so["lines"][0]["unit_price"]) == 120 and so["lines"][0]["price_source"] == "quote"
    assert so["total"] == q["total"]


def test_cancel_and_edit_draft_quote(env):
    vend = env.api("vendedor")
    q = _quote(env, qty=2, unit_price=100)
    edited = vend.put(f"/sales/quotes/{q['id']}", {
        "site_id": env["site_id"], "customer_id": env["customer_id"], "quote_date": str(TODAY),
        "valid_until": str(TODAY + timedelta(days=20)), "currency": "COP", "contact_name": "Nuevo contacto",
        "lines": [{"item_id": env["items"]["A"], "quantity": "3", "unit_price": "100"},
                  {"item_id": env["items"]["LOT"], "quantity": "1", "unit_price": "80"}]})
    assert len(edited["lines"]) == 2 and D(edited["subtotal"]) == 380 and edited["contact_name"] == "Nuevo contacto"
    assert [ln["line_no"] for ln in edited["lines"]] == [1, 2]
    vend.post(f"/sales/quotes/{q['id']}/send")
    r = vend._call("PUT", f"/sales/quotes/{q['id']}", 409, json={
        "site_id": env["site_id"], "customer_id": env["customer_id"], "quote_date": str(TODAY),
        "valid_until": str(TODAY + timedelta(days=20)), "currency": "COP",
        "lines": [{"item_id": env["items"]["A"], "quantity": "1"}]})
    assert "anula" in r.json()["error"]["message"]
    cancelled = vend.post(f"/sales/quotes/{q['id']}/cancel", {"reason": "Se emite una versión corregida"})
    assert cancelled["status"] == "cancelled" and cancelled["lost_reason"] == "Se emite una versión corregida"
    vend.post(f"/sales/quotes/{q['id']}/cancel", {"reason": "Segunda anulación"}, expect=409)
    vend.post(f"/sales/quotes/{q['id']}/convert", {"warehouse_id": env["warehouse_id"]}, expect=409)


def test_edit_draft_sales_order_and_purchase_order(env):
    stock_in(env, qty=20)
    admin = env.api("admin1")
    so = admin.post("/sales/orders", {
        "site_id": env["site_id"], "customer_id": env["customer_id"], "warehouse_id": env["warehouse_id"],
        "order_date": str(TODAY), "currency": "COP", "lines": [{"item_id": env["items"]["A"], "quantity": "2"}]})
    body = {"site_id": env["site_id"], "customer_id": env["customer_id"], "warehouse_id": env["warehouse_id"],
            "order_date": str(TODAY), "currency": "COP", "delivery_address": "Bodega del cliente, Cra 9",
            "lines": [{"item_id": env["items"]["A"], "quantity": "4", "unit_price": "150"}]}
    edited = admin.put(f"/sales/orders/{so['id']}", body)
    assert D(edited["lines"][0]["quantity"]) == 4 and D(edited["subtotal"]) == 600
    assert edited["delivery_address"] == "Bodega del cliente, Cra 9" and edited["number"] == so["number"]
    admin.post(f"/sales/orders/{so['id']}/confirm")
    admin._call("PUT", f"/sales/orders/{so['id']}", 409, json=body)

    po_body = {"site_id": env["site_id"], "supplier_id": env["supplier_id"], "warehouse_id": env["warehouse_id"],
               "order_date": str(TODAY), "currency": "COP",
               "lines": [{"item_id": env["items"]["A"], "quantity": "5", "unit_price": "90"}]}
    po = admin.post("/purchasing/orders", po_body)
    po_body["lines"] = [{"item_id": env["items"]["A"], "quantity": "8", "unit_price": "85"}]
    po_edit = admin.put(f"/purchasing/orders/{po['id']}", po_body)
    assert D(po_edit["subtotal"]) == 680 and po_edit["number"] == po["number"]
    admin.post(f"/purchasing/orders/{po['id']}/submit")
    admin._call("PUT", f"/purchasing/orders/{po['id']}", 409, json=po_body)
    env.api("vendedor")._call("PUT", f"/purchasing/orders/{po['id']}", 403, json=po_body)
