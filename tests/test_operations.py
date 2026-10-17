"""Producción y servicios: módulo activable, consumo a WIP, costeo real, desperdicio, cierre con variación."""
from helpers import TODAY, D, all_entries_balanced, entries_for, stock_in
from sqlalchemy import select

from app.core.db import SessionLocal
from app.modules.org.models import CompanyModule


def _enable(env):
    env.api("admin1").put("/company/modules/operations", {"enabled": True})


def test_module_disabled_for_commercial_company(env):
    env.api("admin1").get("/operations/work-orders", expect=403)
    _enable(env)
    env.api("admin1").get("/operations/work-orders")
    with SessionLocal() as db:
        assert db.scalar(select(CompanyModule).where(CompanyModule.module_code == "operations")).enabled


def test_production_order_costing(env):
    _enable(env)
    stock_in(env, "A", qty=20, price=10)  # componente
    a, b = env.api("admin1"), env.api("admin2")
    bom = a.post("/operations/boms", {"code": "BOM-LOT", "item_id": env["items"]["LOT"], "base_quantity": "1",
                                      "lines": [{"component_item_id": env["items"]["A"], "quantity": "2"}]})
    loc = env["locations"]
    wo = a.post("/operations/work-orders", {
        "wo_type": "production", "site_id": env["site_id"], "item_id": env["items"]["LOT"], "bom_id": bom["id"],
        "planned_qty": "5", "planned_hours": "4", "production_location_id": loc["receiving"],
        "output_location_id": loc["storage"], "planned_start": str(TODAY), "planned_end": str(TODAY)})
    assert D(wo["materials"][0]["planned_qty"]) == 10 and D(wo["estimated_cost"]) == 100
    b.post(f"/operations/work-orders/{wo['id']}/release")
    a.post(f"/operations/work-orders/{wo['id']}/issues", {"issues": [
        {"item_id": env["items"]["A"], "location_id": loc["storage"], "quantity": "10"}]})
    a.post(f"/operations/work-orders/{wo['id']}/time-logs", {"log_date": str(TODAY), "resource_name": "Operario 1",
                                                            "activity": "Ensamble", "hours": "4",
                                                            "cost_per_hour": "5"})
    # Lote obligatorio para el producto terminado
    a.post(f"/operations/work-orders/{wo['id']}/output", {"good_qty": "4", "scrap_qty": "1"}, expect=422)
    out = a.post(f"/operations/work-orders/{wo['id']}/output", {
        "good_qty": "4", "scrap_qty": "1", "lot_number": "PT-001", "expiry_date": str(TODAY.replace(year=TODAY.year + 1)),
        "complete": True})
    s = out["summary"]
    assert D(s["actual_cost"]) == 120 and D(s["scrap_qty"]) == 1 and out["status"] == "completed"
    avail = a.get(f"/inventory/availability/{env['items']['LOT']}")
    assert D(avail["available"]) == 4 and D(avail["avg_cost"]) == 30  # 120 / 4 unidades buenas
    closed = b.post(f"/operations/work-orders/{wo['id']}/close")
    assert closed["status"] == "closed" and D(closed["summary"]["cost_variance"]) == 20
    assert len(entries_for("work_order", wo["id"])) >= 3
    # WIP queda en cero tras trasladar el costo al producto terminado
    from helpers import scalar

    wip = scalar("""select coalesce(sum(l.debit - l.credit), 0) from journal_lines l join accounts a on a.id = l.account_id
                    where a.code = '141005'""")
    assert wip == 0
    assert all_entries_balanced(env["company_id"])
    k = {x["code"]: x for x in env.api("gerente").get("/kpi/dashboard?module=operations")["kpis"]}
    assert D(k["scrap_rate"]["value"]) == 20 and D(k["productivity"]["value"]) == 1


def test_service_work_order(env):
    _enable(env)
    a = env.api("admin1")
    wo = a.post("/operations/work-orders", {"wo_type": "service", "site_id": env["site_id"],
                                            "project_name": "Implementación cliente X", "planned_hours": "10",
                                            "deliverables": "Informe final", "customer_id": env["customer_id"]})
    env.api("admin2").post(f"/operations/work-orders/{wo['id']}/release")
    a.post(f"/operations/work-orders/{wo['id']}/time-logs", {"log_date": str(TODAY), "resource_name": "Consultor",
                                                            "activity": "Levantamiento", "hours": "6"})
    done = env.api("admin2").post(f"/operations/work-orders/{wo['id']}/complete", {"progress_pct": "100"})
    assert D(done["summary"]["actual_hours"]) == 6
