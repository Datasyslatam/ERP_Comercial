"""Indicadores: sin datos no se inventan cifras; con datos se calculan desde las transacciones; metas y alertas."""
from datetime import timedelta

from helpers import TODAY, D, approved_po, confirmed_so, receive, shipped_dispatch, stock_in

REQUIRED = {"code", "name", "description", "formula", "source", "unit", "frequency", "target", "warning_threshold",
            "critical_threshold", "owner_id", "last_updated", "confidence", "status", "period"}


def test_empty_company_shows_no_data_not_zeros(env):
    dash = env.api("gerente").get("/kpi/dashboard")
    kpis = {k["code"]: k for k in dash["kpis"]}
    assert len(kpis) >= 45
    for k in kpis.values():
        assert REQUIRED <= set(k), k["code"]
    for code in ("revenue", "gross_margin", "supplier_otd", "otif", "inventory_value", "receipts_conformity",
                 "purchase_cycle_days", "wo_plan_compliance", "nc_resolution_days", "inventory_accuracy",
                 "ar_balance", "ap_balance", "cash_balance"):
        assert kpis[code]["value"] is None and kpis[code]["status"] == "no_data", code
        assert kpis[code]["notes"], code


def test_kpis_computed_from_transactions(env):
    po = approved_po(env, qty=10, price=100, expected=TODAY + timedelta(days=3))
    receive(env, po, 10)
    so = confirmed_so(env, "A", qty=4, price=250, promised=TODAY + timedelta(days=1))
    d = shipped_dispatch(env, so, freight=30)
    a = env.api("admin1")
    a.post(f"/logistics/dispatches/{d['id']}/deliver", {"received_by": "Recepción"})
    inv = a.post("/einvoicing/invoices/from-dispatch", {"dispatch_id": d["id"]})
    a.post(f"/einvoicing/invoices/{inv['id']}/issue")
    g = env.api("gerente")
    k = {x["code"]: x for x in g.get("/kpi/dashboard")["kpis"]}
    assert D(k["revenue"]["value"]) == 1000
    assert D(k["gross_margin"]["value"]) == 60
    assert D(k["supplier_otd"]["value"]) == 100
    assert D(k["otif"]["value"]) == 100
    assert D(k["logistics_cost_per_order"]["value"]) == 30
    assert D(k["inventory_value"]["value"]) == 600
    assert D(k["ar_balance"]["value"]) == D(1190)
    assert k["revenue"]["status"] == "no_target"  # sin meta configurada no se califica
    assert k["supplier_otd"]["confidence"] == "low"  # una sola observación


def test_targets_status_and_alerts(env):
    stock_in(env, "A", qty=2, price=10)  # debajo del mínimo (5)
    a = env.api("admin1")
    a.put("/kpi/targets", {"kpi_code": "items_below_min", "target": "0", "critical_threshold": "1"})
    kpi = env.api("gerente").get("/kpi/kpis/items_below_min")
    assert D(kpi["value"]) == 1 and kpi["status"] == "critical" and D(kpi["target"]) == 0
    created = a.post("/kpi/alerts/evaluate")["created"]
    assert created >= 2  # alerta del KPI + alerta operativa de faltante
    alerts = a.get("/kpi/alerts")["items"]
    assert {x["source"] for x in alerts} >= {"kpi:items_below_min", "stock:min"}
    assert a.post("/kpi/alerts/evaluate")["created"] == 0  # sin duplicados
    a.post(f"/kpi/alerts/{alerts[0]['id']}/ack", {"notes": "Orden de compra en curso"})


def test_dashboard_respects_permissions(env):
    vendedor = env.api("vendedor")
    mods = {k["module"] for k in vendedor.get("/kpi/dashboard")["kpis"]}
    assert "finance" not in mods and "inventory" in mods
    vendedor.get("/kpi/kpis/revenue", expect=404 if False else 403)
    csv = env.client.get("/api/v1/kpi/dashboard.csv", headers=env.api("gerente").headers)
    assert csv.status_code == 200 and "formula" in csv.text.splitlines()[0]


def test_trend(env):
    t = env.api("gerente").get("/kpi/kpis/revenue/trend?months=3")
    assert len(t) == 3 and all(p["value"] is None for p in t)
