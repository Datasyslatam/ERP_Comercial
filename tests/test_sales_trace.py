"""Cotizaciones, cierre de pedidos con saldo y trazabilidad documental entre módulos."""
from datetime import timedelta

from conftest import TODAY
from helpers import approved_po, confirmed_so, receive, shipped_dispatch, stock_in


def _quote(env, user="vendedor", valid_days=15, qty=4, price=200):
    return env.api(user).post("/sales/quotes", {
        "site_id": env["site_id"], "customer_id": env["customer_id"], "quote_date": str(TODAY),
        "valid_until": str(TODAY + timedelta(days=valid_days)), "currency": "COP", "contact_name": "Compras cliente",
        "lines": [{"item_id": env["items"]["A"], "quantity": str(qty), "unit_price": str(price), "discount_pct": "10"}]})


def test_quote_to_order_keeps_conditions(env):
    stock_in(env, qty=20)
    q = _quote(env)
    assert q["number"].startswith("CT-") and q["status"] == "draft"
    assert q["subtotal"] == "720.00" and q["total"] == "856.80"  # 4 x 200 - 10 % + IVA 19 %
    vend = env.api("vendedor")
    assert vend.post(f"/sales/quotes/{q['id']}/send")["status"] == "sent"
    so = vend.post(f"/sales/quotes/{q['id']}/convert", {"warehouse_id": env["warehouse_id"]}, expect=201).json()
    assert so["status"] == "draft" and so["total"] == q["total"]
    assert so["lines"][0]["discount_pct"] == "10.000000" and q["number"] in so["notes"]
    q2 = vend.get(f"/sales/quotes/{q['id']}")
    assert q2["status"] == "accepted" and q2["sales_order_id"] == so["id"]
    vend.post(f"/sales/quotes/{q['id']}/convert", {"warehouse_id": env["warehouse_id"]}, expect=409)


def test_expired_and_lost_quotes(env):
    vend = env.api("vendedor")
    q = _quote(env, valid_days=0)
    from app.core.db import SessionLocal
    from app.modules.sales.models import SalesQuote

    with SessionLocal() as db:
        db.get(SalesQuote, q["id"]).quote_date = TODAY - timedelta(days=10)
        db.get(SalesQuote, q["id"]).valid_until = TODAY - timedelta(days=1)
        db.commit()
    assert vend.get(f"/sales/quotes/{q['id']}")["status"] == "expired"
    assert [x["id"] for x in vend.get("/sales/quotes?status=expired")["items"]] == [q["id"]]
    r = vend.post(f"/sales/quotes/{q['id']}/convert", {"warehouse_id": env["warehouse_id"]}, expect=422)
    assert "venció" in r.json()["error"]["message"]
    q2 = _quote(env)
    lost = vend.post(f"/sales/quotes/{q2['id']}/reject", {"reason": "Precio de la competencia"})
    assert lost["status"] == "rejected" and lost["lost_reason"] == "Precio de la competencia"
    vend.post("/sales/quotes", {"site_id": env["site_id"], "customer_id": env["customer_id"], "quote_date": str(TODAY),
                                "valid_until": str(TODAY - timedelta(days=1)), "currency": "COP",
                                "lines": [{"item_id": env["items"]["A"], "quantity": "1"}]}, expect=422)
    env.api("comprador").get("/sales/quotes", expect=403)


def test_close_order_releases_pending_reservation(env):
    stock_in(env, qty=10)
    so = confirmed_so(env, qty=6)
    admin = env.api("admin1")
    d = admin.post("/logistics/dispatches", {"sales_order_id": so["id"], "carrier_id": env["carrier_id"]})
    r = admin.post(f"/sales/orders/{so['id']}/close", {"reason": "Cliente desiste del saldo"}, expect=422)
    assert "en preparación" in r.json()["error"]["message"]
    admin.post(f"/logistics/dispatches/{d['id']}/cancel", {"reason": "Se despacha solo una parte"})
    so_detail = admin.get(f"/sales/orders/{so['id']}")
    assert so_detail["lines"][0]["qty_reserved"] == "6.000000"
    closed = admin.post(f"/sales/orders/{so['id']}/close", {"reason": "Cliente desiste del pedido"})
    assert closed["status"] == "closed" and float(closed["lines"][0]["qty_reserved"]) == 0
    stock = admin.get(f"/inventory/stock?item_id={env['items']['A']}")
    assert sum(float(s["qty_reserved"]) for s in stock) == 0
    admin.post(f"/sales/orders/{so['id']}/close", {"reason": "Segundo cierre"}, expect=409)


def test_trace_sales_chain(env):
    stock_in(env, qty=10)
    q = _quote(env, qty=3, price=150)
    vend = env.api("vendedor")
    so = vend.post(f"/sales/quotes/{q['id']}/convert", {"warehouse_id": env["warehouse_id"]}, expect=201).json()
    admin = env.api("admin1")
    admin.post(f"/sales/orders/{so['id']}/confirm")
    d = shipped_dispatch(env, so)
    inv = admin.post("/einvoicing/invoices/from-dispatch", {"dispatch_id": d["id"]})
    admin.post(f"/einvoicing/invoices/{inv['id']}/issue")
    t = admin.get(f"/trace/sales_order/{so['id']}")
    types = [n["type"] for n in t["nodes"]]
    assert {"sales_quote", "sales_order", "dispatch", "sales_invoice", "journal_entry"} <= set(types)
    assert types.index("sales_quote") < types.index("sales_order") < types.index("dispatch")
    start = next(n for n in t["nodes"] if n["is_start"])
    assert start["number"] == so["number"] and start["route"] == f"/ventas/pedidos/{so['id']}"
    assert any(e["from"].startswith("dispatch") or e["to"].startswith("dispatch") for e in t["edges"])
    # Desde la factura se llega a la cotización de origen
    assert "sales_quote" in {n["type"] for n in admin.get(f"/trace/sales_invoice/{inv['id']}")["nodes"]}
    # El vendedor no ve comprobantes contables: aparecen sin datos ni enlace
    vt = vend.get(f"/trace/sales_order/{so['id']}")
    je = [n for n in vt["nodes"] if n["type"] == "journal_entry"]
    assert je and all(not n["allowed"] and n["number"] is None and n["route"] is None for n in je)
    found = admin.get(f"/trace/search?q={so['number']}")
    assert any(r["type"] == "sales_order" and r["id"] == so["id"] for r in found)


def test_trace_purchasing_chain(env):
    po = approved_po(env, qty=5, price=100)
    gr = receive(env, po, 5)
    admin = env.api("admin1")
    t = admin.get(f"/trace/goods_receipt/{gr['id']}")
    types = {n["type"] for n in t["nodes"]}
    assert {"purchase_order", "goods_receipt", "journal_entry"} <= types
    admin.get("/trace/no_existe/1", expect=404)
    admin.get(f"/trace/purchase_order/{po['id'] + 999}", expect=404)
    env.api("vendedor").get(f"/trace/purchase_order/{po['id']}", expect=403)
