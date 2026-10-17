"""Órdenes de trabajo: liberación, consumo de materiales (inventario → WIP), tiempos, producción (WIP → producto
terminado a costo real), desperdicio, incidencias y cierre con variación."""
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.crud import check_company_refs, get_owned
from app.core.deps import Principal
from app.core.errors import BusinessRuleViolation, Conflict
from app.core.money import ZERO, money
from app.core.money import qty as q
from app.core.numbering import next_number
from app.modules.accounting.ledger import LineSpec, post_entry, posting_account
from app.modules.accounting.posting import post_inventory_value
from app.modules.inventory import stock
from app.modules.inventory.models import StockMove
from app.modules.masters.models import Item
from app.modules.operations.models import (
    BillOfMaterials,
    WorkOrder,
    WorkOrderIncident,
    WorkOrderMaterial,
    WorkOrderTimeLog,
)


def create_work_order(db: Session, p: Principal, data: dict) -> WorkOrder:
    materials = data.pop("materials", None) or []
    check_company_refs(db, WorkOrder, p.company_id, data)
    p.ensure_site(data["site_id"])
    wo = WorkOrder(company_id=p.company_id, number=next_number(db, p.company_id, "work_order"), created_by_id=p.user_id,
                   **data)
    if wo.wo_type == "production":
        if not (wo.item_id and wo.planned_qty and wo.planned_qty > 0):
            raise BusinessRuleViolation("La orden de producción requiere artículo y cantidad planificada")
        if not (wo.production_location_id and wo.output_location_id):
            raise BusinessRuleViolation("Indique ubicación de producción (WIP) y de producto terminado")
        if wo.bom_id and not materials:
            bom = get_owned(db, BillOfMaterials, wo.bom_id, p.company_id)
            factor = wo.planned_qty / bom.base_quantity
            materials = [{"item_id": bl.component_item_id,
                          "planned_qty": q(bl.quantity * factor * (1 + bl.scrap_pct / 100))} for bl in bom.lines]
    elif wo.wo_type == "service" and not (wo.project_name or wo.description):
        raise BusinessRuleViolation("La orden de servicio requiere proyecto o descripción del entregable")
    est = ZERO
    for m in materials:
        get_owned(db, Item, m["item_id"], p.company_id)
        unit = stock.current_cost(db, p.company_id, m["item_id"])
        wo.materials.append(WorkOrderMaterial(item_id=m["item_id"], planned_qty=q(m["planned_qty"]),
                                              estimated_unit_cost=unit))
        est += money(Decimal(m["planned_qty"]) * unit)
    if not wo.estimated_cost:
        wo.estimated_cost = est
    db.add(wo)
    db.flush()
    return wo


def _get(db: Session, p: Principal, wo_id: int, *statuses: str) -> WorkOrder:
    wo = get_owned(db, WorkOrder, wo_id, p.company_id, lock=True)
    if statuses and wo.status not in statuses:
        raise Conflict(f"La orden está en estado {wo.status}")
    return wo


def release(db: Session, p: Principal, wo_id: int) -> WorkOrder:
    wo = _get(db, p, wo_id, "draft")
    wo.status = "released"
    log_action(db, "approve", "work_orders", wo.id, "Liberada")
    return wo


def issue_materials(db: Session, p: Principal, wo_id: int, issues: list[dict]) -> WorkOrder:
    """Entrega de materiales a producción: salida de bodega y cargo a productos en proceso."""
    wo = _get(db, p, wo_id, "released", "in_progress")
    mats = {m.item_id: m for m in wo.materials}
    values: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for x in issues:
        m = mats.get(x["item_id"])
        if m is None:
            raise BusinessRuleViolation("El material no está planificado en la orden")
        quantity = q(x["quantity"])
        src = stock.MoveSource("work_order", wo.id, m.id, wo.number)
        mv = stock.issue(db, p.company_id, item_id=m.item_id, location_id=x["location_id"], quantity=quantity,
                         move_type="production_issue", lot_id=x.get("lot_id"), src=src,
                         reason=f"Consumo OT {wo.number}", user_id=p.user_id)
        m.issued_qty += quantity
        m.issued_cost += mv.total_cost
        values[m.item_id] += mv.total_cost
    if wo.status == "released":
        wo.status, wo.actual_start = "in_progress", datetime.now(UTC)
    post_inventory_value(db, company_id=p.company_id, entry_date=date.today(),
                         key=f"wo_issue:{wo.id}:{uuid.uuid4().hex}",
                         description=f"Consumo de materiales OT {wo.number}", source_type="work_order",
                         source_id=wo.id, by_item=dict(values), counter_key="wip", inbound=False, user_id=p.user_id,
                         cost_center_id=wo.cost_center_id)
    return wo


def log_time(db: Session, p: Principal, wo_id: int, data: dict) -> WorkOrderTimeLog:
    wo = _get(db, p, wo_id, "released", "in_progress")
    tl = WorkOrderTimeLog(work_order_id=wo.id, **data)
    db.add(tl)
    if wo.status == "released":
        wo.status, wo.actual_start = "in_progress", datetime.now(UTC)
    db.flush()
    labor = money(tl.hours * tl.cost_per_hour)
    if labor > 0:
        post_entry(db, company_id=p.company_id, entry_date=tl.log_date, journal_type="general",
                   description=f"Mano de obra aplicada OT {wo.number}",
                   lines=[LineSpec(account_id=posting_account(db, p.company_id, "wip"), debit=labor,
                                   cost_center_id=wo.cost_center_id),
                          LineSpec(account_id=posting_account(db, p.company_id, "applied_labor"), credit=labor,
                                   cost_center_id=wo.cost_center_id)],
                   idempotency_key=f"wo_labor:{tl.id}", source_type="work_order", source_id=wo.id, user_id=p.user_id)
    return tl


def report_incident(db: Session, p: Principal, wo_id: int, data: dict) -> WorkOrderIncident:
    wo = _get(db, p, wo_id)
    inc = WorkOrderIncident(work_order_id=wo.id, created_at=datetime.now(UTC), created_by_id=p.user_id, **data)
    db.add(inc)
    db.flush()
    return inc


def _transferred(db: Session, wo_id: int) -> Decimal:
    return Decimal(db.scalar(select(func.coalesce(func.sum(StockMove.total_cost), 0)).where(
        StockMove.source_type == "work_order", StockMove.source_id == wo_id,
        StockMove.move_type == "production_output")))


def actual_cost(wo: WorkOrder) -> Decimal:
    return sum((m.issued_cost for m in wo.materials), ZERO) + sum(
        (money(t.hours * t.cost_per_hour) for t in wo.time_logs), ZERO)


def report_output(db: Session, p: Principal, wo_id: int, data: dict) -> WorkOrder:
    """Reporte de producción: buenas, desperdicio y reproceso. Las buenas ingresan a costo real acumulado."""
    wo = _get(db, p, wo_id, "in_progress")
    good, scrap, rework = q(data["good_qty"]), q(data.get("scrap_qty") or 0), q(data.get("rework_qty") or 0)
    if good < 0 or scrap < 0 or rework < 0 or good + scrap + rework == 0:
        raise BusinessRuleViolation("Cantidades de producción inválidas")
    wo.scrap_qty += scrap
    wo.rework_qty += rework
    if good > 0:
        if wo.wo_type != "production":
            raise BusinessRuleViolation("Solo las órdenes de producción generan producto terminado")
        item = db.get(Item, wo.item_id)
        lot = stock.get_or_create_lot(db, p.company_id, item, data.get("lot_number"), expiry_date=data.get("expiry_date"))
        # Costo pendiente en proceso (acumulado menos lo ya trasladado) se absorbe en las unidades buenas;
        # el desperdicio normal queda incluido en el costo unitario.
        remaining = money(actual_cost(wo) - _transferred(db, wo.id))
        unit_cost = (remaining / good).quantize(Decimal("0.000001")) if remaining > 0 else ZERO
        mv = stock.receive(db, p.company_id, item_id=wo.item_id, location_id=wo.output_location_id, quantity=good,
                           unit_cost=unit_cost, move_type="production_output", lot_id=lot.id if lot else None,
                           src=stock.MoveSource("work_order", wo.id, None, wo.number),
                           reason=f"Producción OT {wo.number}", user_id=p.user_id)
        wo.produced_qty += good
        post_inventory_value(db, company_id=p.company_id, entry_date=date.today(),
                             key=f"wo_output:{wo.id}:{uuid.uuid4().hex}",
                             description=f"Producto terminado OT {wo.number}", source_type="work_order",
                             source_id=wo.id, by_item={wo.item_id: mv.total_cost}, counter_key="wip", inbound=True,
                             user_id=p.user_id)
    if wo.planned_qty:
        wo.progress_pct = min(Decimal("100"), (wo.produced_qty / wo.planned_qty * 100).quantize(Decimal("0.01")))
    if data.get("complete"):
        wo.status, wo.actual_end = "completed", datetime.now(UTC)
    return wo


def complete(db: Session, p: Principal, wo_id: int, progress: Decimal | None = None) -> WorkOrder:
    wo = _get(db, p, wo_id, "in_progress", "released")
    wo.status, wo.actual_end = "completed", datetime.now(UTC)
    if progress is not None:
        wo.progress_pct = progress
    elif wo.wo_type != "production":
        wo.progress_pct = Decimal("100")
    return wo


def close(db: Session, p: Principal, wo_id: int) -> WorkOrder:
    """Cierra la orden y lleva el saldo remanente de productos en proceso a variación de producción."""
    wo = _get(db, p, wo_id, "completed")
    absorbed = money(actual_cost(wo))
    transferred = _transferred(db, wo.id)
    remainder = money(absorbed - Decimal(transferred)) if wo.wo_type == "production" else absorbed
    if remainder != 0:
        wip = posting_account(db, p.company_id, "wip")
        var = posting_account(db, p.company_id, "production_variance")
        post_entry(db, company_id=p.company_id, entry_date=date.today(), journal_type="general",
                   description=f"Cierre OT {wo.number}: saldo de proceso a variación",
                   lines=[LineSpec(account_id=var, debit=remainder if remainder > 0 else ZERO,
                                   credit=-remainder if remainder < 0 else ZERO, cost_center_id=wo.cost_center_id),
                          LineSpec(account_id=wip, debit=-remainder if remainder < 0 else ZERO,
                                   credit=remainder if remainder > 0 else ZERO)],
                   idempotency_key=f"wo_close:{wo.id}", source_type="work_order", source_id=wo.id, user_id=p.user_id)
    wo.status = "closed"
    log_action(db, "post", "work_orders", wo.id, f"Cerrada; costo real {absorbed}, variación {remainder}")
    return wo


def summary(wo: WorkOrder) -> dict:
    act = actual_cost(wo)
    hours = sum((t.hours for t in wo.time_logs), ZERO)
    return {
        "planned_qty": wo.planned_qty, "produced_qty": wo.produced_qty, "scrap_qty": wo.scrap_qty,
        "rework_qty": wo.rework_qty, "estimated_cost": wo.estimated_cost, "actual_cost": act,
        "cost_variance": act - wo.estimated_cost, "planned_hours": wo.planned_hours, "actual_hours": hours,
        "progress_pct": wo.progress_pct,
        "late": bool(wo.planned_end and wo.status not in ("completed", "closed") and wo.planned_end < date.today()),
    }
