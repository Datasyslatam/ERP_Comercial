"""Calidad: inspecciones con resultado sobre inventario (liberación/bloqueo), no conformidades y CAPA."""
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.crud import get_owned
from app.core.deps import Principal
from app.core.errors import BusinessRuleViolation, Conflict
from app.core.money import ZERO, money
from app.core.money import qty as q
from app.core.numbering import next_number
from app.modules.accounting.posting import post_inventory_value
from app.modules.inventory import stock
from app.modules.inventory.models import Location, Lot
from app.modules.masters.models import Item
from app.modules.quality.models import CapaAction, Inspection, InspectionPlan, InspectionResult, NonConformity


def find_plan(db: Session, company_id: int, item: Item, stage: str) -> InspectionPlan | None:
    plans = db.scalars(select(InspectionPlan).where(InspectionPlan.company_id == company_id,
                                                    InspectionPlan.stage == stage,
                                                    InspectionPlan.is_active.is_(True))).all()
    for pl in plans:
        if pl.item_id == item.id:
            return pl
    for pl in plans:
        if pl.item_id is None and pl.category_id and pl.category_id == item.category_id:
            return pl
    return next((pl for pl in plans if pl.item_id is None and pl.category_id is None), None)


def create_receiving_inspection(db: Session, p: Principal, receipt_line, receipt) -> Inspection:
    item = db.get(Item, receipt_line.item_id)
    plan = find_plan(db, p.company_id, item, "receiving")
    insp = Inspection(company_id=p.company_id, number=next_number(db, p.company_id, "inspection"),
                      plan_id=plan.id if plan else None, stage="receiving", item_id=item.id,
                      lot_id=receipt_line.lot_id, supplier_id=receipt.supplier_id, source_type="goods_receipt_line",
                      source_id=receipt_line.id, quantity=receipt_line.quantity,
                      due_date=receipt.receipt_date + timedelta(days=2))
    db.add(insp)
    db.flush()
    return insp


def create_inspection(db: Session, p: Principal, data: dict) -> Inspection:
    """Inspecciones en proceso, de producto terminado o de despacho registradas manualmente."""
    item = get_owned(db, Item, data["item_id"], p.company_id)
    if data["stage"] == "receiving":
        raise BusinessRuleViolation("Las inspecciones de recepción se generan desde la recepción de compras")
    plan = find_plan(db, p.company_id, item, data["stage"])
    insp = Inspection(company_id=p.company_id, number=next_number(db, p.company_id, "inspection"),
                      plan_id=plan.id if plan else None, **data)
    db.add(insp)
    db.flush()
    return insp


def _evaluate(plan: InspectionPlan | None, results: list[dict]) -> tuple[list[InspectionResult], bool]:
    chars = {c.id: c for c in (plan.characteristics if plan else [])}
    out, critical_fail = [], False
    given = {r.get("characteristic_id") for r in results}
    missing = [c.name for cid, c in chars.items() if cid not in given]
    if missing:
        raise BusinessRuleViolation(f"Faltan resultados para: {', '.join(missing)}")
    for r in results:
        ch = chars.get(r.get("characteristic_id"))
        ok = True
        if ch is not None:
            if ch.kind == "numeric":
                v = r.get("numeric_value")
                if v is None:
                    raise BusinessRuleViolation(f"'{ch.name}' requiere valor numérico")
                v = Decimal(str(v))
                ok = (ch.lower_limit is None or v >= ch.lower_limit) and (ch.upper_limit is None or v <= ch.upper_limit)
            elif ch.kind == "boolean":
                if r.get("bool_value") is None:
                    raise BusinessRuleViolation(f"'{ch.name}' requiere valor sí/no")
                ok = bool(r["bool_value"])
            else:
                ok = bool(r.get("is_conforming", True))
            critical_fail |= (not ok and ch.is_critical)
        else:
            ok = bool(r.get("is_conforming", True))
        out.append(InspectionResult(characteristic_id=ch.id if ch else None, name=ch.name if ch else r.get("name", "Observación"),
                                    numeric_value=r.get("numeric_value"), bool_value=r.get("bool_value"),
                                    text_value=r.get("text_value"), is_conforming=ok))
    return out, critical_fail


def record_result(db: Session, p: Principal, insp_id: int, data: dict) -> Inspection:
    """Registra resultados y dispone el material: aceptado → libera; rechazado → bloquea y devuelve al proveedor."""
    from app.modules.purchasing.models import GoodsReceipt, GoodsReceiptLine, PurchaseOrderLine

    insp = get_owned(db, Inspection, insp_id, p.company_id, lock=True)
    if insp.status != "pending":
        raise Conflict("La inspección ya fue cerrada")
    accepted, rejected = q(data["qty_accepted"]), q(data["qty_rejected"])
    if accepted < 0 or rejected < 0 or accepted + rejected != insp.quantity:
        raise BusinessRuleViolation(f"Aceptado + rechazado debe ser igual a la cantidad inspeccionada ({insp.quantity})")
    plan = db.get(InspectionPlan, insp.plan_id) if insp.plan_id else None
    results, critical_fail = _evaluate(plan, data.get("results", []))
    if critical_fail and accepted > 0 and not data.get("deviation_approved"):
        raise BusinessRuleViolation("Hay características críticas fuera de especificación; no se puede aceptar sin "
                                    "concesión aprobada (deviation_approved)")
    insp.results = results
    insp.qty_accepted, insp.qty_rejected = accepted, rejected
    insp.status = "accepted" if rejected == 0 else ("rejected" if accepted == 0 else "partial")
    insp.inspector_id, insp.inspected_at, insp.notes = p.user_id, datetime.now(UTC), data.get("notes")

    if insp.source_type == "goods_receipt_line":
        grl = db.get(GoodsReceiptLine, insp.source_id)
        gr = db.get(GoodsReceipt, grl.receipt_id)
        pl = db.get(PurchaseOrderLine, grl.po_line_id)
        quality_loc = db.get(Location, gr.location_id) if db.get(Location, gr.location_id).location_type == "quality" \
            else stock.default_location(db, p.company_id, db.get(Location, gr.location_id).warehouse_id, "quality")
        src = stock.MoveSource("inspection", insp.id, grl.id, insp.number)
        if accepted > 0:
            storage = stock.default_location(db, p.company_id, quality_loc.warehouse_id, "storage")
            stock.transfer(db, p.company_id, item_id=insp.item_id, from_location_id=quality_loc.id,
                           to_location_id=storage.id, quantity=accepted, lot_id=insp.lot_id, src=src,
                           reason=f"Liberación por inspección {insp.number}", user_id=p.user_id)
        if rejected > 0:
            mv = stock.issue(db, p.company_id, item_id=insp.item_id, location_id=quality_loc.id, quantity=rejected,
                             move_type="supplier_return", lot_id=insp.lot_id, src=src, unit_cost=grl.unit_cost,
                             reason=f"Devolución a proveedor por rechazo de calidad {insp.number}", user_id=p.user_id)
            post_inventory_value(db, company_id=p.company_id, entry_date=date.today(),
                                 key=f"supplier_return:{insp.id}", description=f"Devolución a proveedor {insp.number}",
                                 source_type="inspection", source_id=insp.id, by_item={insp.item_id: mv.total_cost},
                                 counter_key="grni", inbound=False, user_id=p.user_id)
            pl.qty_rejected += rejected
            raise_nc(db, p, source="inspection", description=data.get("nc_description") or
                     f"Rechazo en inspección de recepción {insp.number}", severity="critical" if critical_fail else "major",
                     inspection_id=insp.id, item_id=insp.item_id, lot_id=insp.lot_id, supplier_id=insp.supplier_id,
                     quantity_affected=rejected, cost_impact=mv.total_cost, disposition="return_to_supplier",
                     category=data.get("nc_category") or "recepcion")
        grl.qty_accepted, grl.qty_rejected = accepted, rejected
        grl.inspection_status = insp.status
        if insp.lot_id:
            lot = db.get(Lot, insp.lot_id)
            lot.status = "released" if accepted > 0 else "blocked"
            lot.status_reason = f"Inspección {insp.number}: {insp.status}"
        from app.modules.purchasing.models import PurchaseOrder
        from app.modules.purchasing.service import _refresh_po_status

        _refresh_po_status(db.get(PurchaseOrder, pl.purchase_order_id))
    elif rejected > 0:
        raise_nc(db, p, source="production" if insp.stage == "in_process" else "internal",
                 description=data.get("nc_description") or f"Rechazo en inspección {insp.number}", severity="major",
                 inspection_id=insp.id, item_id=insp.item_id, lot_id=insp.lot_id, quantity_affected=rejected,
                 category=data.get("nc_category"))
    log_action(db, "approve", "inspections", insp.id, f"Resultado {insp.status}: +{accepted} / -{rejected}")
    return insp


def set_lot_status(db: Session, p: Principal, lot_id: int, status: str, reason: str) -> Lot:
    lot = get_owned(db, Lot, lot_id, p.company_id, lock=True)
    if status not in ("released", "blocked", "quarantine"):
        raise BusinessRuleViolation("Estado de lote inválido")
    if status != "released":
        from app.modules.inventory.models import StockReservation

        active = db.scalar(select(StockReservation.id).where(StockReservation.lot_id == lot.id,
                                                             StockReservation.status == "active").limit(1))
        if active:
            raise BusinessRuleViolation("El lote tiene reservas activas; libérelas antes de bloquearlo")
    lot.status, lot.status_reason = status, reason
    log_action(db, "approve", "lots", lot.id, f"{status}: {reason}")
    return lot


def raise_nc(db: Session, p: Principal, **data) -> NonConformity:
    nc = NonConformity(company_id=p.company_id, number=next_number(db, p.company_id, "nonconformity"),
                       detected_at=datetime.now(UTC), created_by_id=p.user_id,
                       cost_impact=money(data.pop("cost_impact", ZERO) or ZERO), **data)
    db.add(nc)
    db.flush()
    return nc


_NC_FLOW = {"open": ("analysis",), "analysis": ("action",), "action": ("verification",),
            "verification": ("closed", "action")}


def advance_nc(db: Session, p: Principal, nc_id: int, to_status: str, data: dict) -> NonConformity:
    nc = get_owned(db, NonConformity, nc_id, p.company_id, lock=True)
    if to_status not in _NC_FLOW.get(nc.status, ()):
        raise BusinessRuleViolation(f"Transición inválida {nc.status} → {to_status}")
    if to_status == "action":
        if not (data.get("root_cause") or nc.root_cause):
            raise BusinessRuleViolation("Debe registrar el análisis de causa raíz antes de definir acciones")
        nc.root_cause = data.get("root_cause") or nc.root_cause
        nc.root_cause_method = data.get("root_cause_method") or nc.root_cause_method
    if to_status == "verification" and not any(a.status in ("done", "verified") for a in nc.actions):
        raise BusinessRuleViolation("No hay acciones ejecutadas para verificar")
    if to_status == "closed":
        if any(a.status == "open" for a in nc.actions):
            raise BusinessRuleViolation("Existen acciones abiertas")
        nc.closed_at = datetime.now(UTC)
    nc.status = to_status
    log_action(db, "approve", "nonconformities", nc.id, f"→ {to_status}")
    return nc


def add_action(db: Session, p: Principal, nc_id: int, data: dict) -> CapaAction:
    nc = get_owned(db, NonConformity, nc_id, p.company_id)
    if nc.status == "closed":
        raise Conflict("La no conformidad está cerrada")
    act = CapaAction(nonconformity_id=nc.id, **data)
    db.add(act)
    db.flush()
    return act


def update_action(db: Session, p: Principal, action_id: int, status: str, notes: str | None) -> CapaAction:
    act = db.get(CapaAction, action_id)
    if act is None:
        raise BusinessRuleViolation("Acción inexistente")
    get_owned(db, NonConformity, act.nonconformity_id, p.company_id)
    allowed = {"open": ("done", "cancelled"), "done": ("verified", "open")}
    if status not in allowed.get(act.status, ()):
        raise BusinessRuleViolation(f"Transición inválida {act.status} → {status}")
    act.status = status
    if status == "done":
        act.completed_at = datetime.now(UTC)
    if notes:
        act.effectiveness_notes = notes
    return act
