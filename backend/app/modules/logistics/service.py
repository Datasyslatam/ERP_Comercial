"""Despachos: preparación, verificación, envío (consumo de reservas + costo de ventas), entrega y devoluciones."""
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.crud import check_company_refs, get_owned
from app.core.deps import Principal
from app.core.errors import BusinessRuleViolation, Conflict
from app.core.money import ZERO
from app.core.money import qty as q
from app.core.numbering import next_number
from app.modules.accounting.posting import post_inventory_value
from app.modules.inventory import stock
from app.modules.logistics.models import (
    CustomerReturn,
    CustomerReturnLine,
    DeliveryIncident,
    DispatchLine,
    DispatchOrder,
    ShipmentEvent,
)
from app.modules.masters.models import Item, Party
from app.modules.sales import service as sales
from app.modules.sales.models import SalesOrder, SalesOrderLine

_OPEN = ("draft", "picking", "picked", "packed")


def _event(db: Session, d: DispatchOrder, status: str, user_id: int | None, notes: str | None = None,
           location_text: str | None = None) -> None:
    db.add(ShipmentEvent(dispatch_id=d.id, event_time=datetime.now(UTC), status=status, notes=notes,
                         location_text=location_text, created_by_id=user_id))


def _committed_in_dispatches(db: Session, so_line_id: int) -> Decimal:
    """Cantidad del renglón ya asignada a despachos abiertos (aún no enviados)."""
    return Decimal(db.scalar(select(func.coalesce(func.sum(DispatchLine.qty_requested), 0))
                             .join(DispatchOrder).where(DispatchLine.so_line_id == so_line_id,
                                                        DispatchOrder.status.in_(_OPEN))))


def create_dispatch(db: Session, p: Principal, so_id: int, data: dict) -> DispatchOrder:
    so = get_owned(db, SalesOrder, so_id, p.company_id, lock=True)
    if so.status not in ("confirmed", "partially_dispatched"):
        raise BusinessRuleViolation("Solo se despachan pedidos confirmados")
    lines_in = data.pop("lines", None)
    check_company_refs(db, DispatchOrder, p.company_id, data)
    if data.get("carrier_id"):
        carrier = get_owned(db, Party, data["carrier_id"], p.company_id)
        if not carrier.is_carrier:
            raise BusinessRuleViolation("El tercero indicado no es transportista")
    so_lines = {ln.id: ln for ln in so.lines}
    wanted = {ln["so_line_id"]: q(ln["quantity"]) for ln in lines_in} if lines_in else None
    d = DispatchOrder(company_id=p.company_id, number=next_number(db, p.company_id, "dispatch"), sales_order_id=so.id,
                      customer_id=so.customer_id, warehouse_id=so.warehouse_id, promised_date=so.promised_date,
                      delivery_address=data.pop("delivery_address", None) or so.delivery_address,
                      created_by_id=p.user_id, **data)
    for sol in so.lines:
        if wanted is not None and sol.id not in wanted:
            continue
        item = db.get(Item, sol.item_id)
        pending = sol.quantity - sol.qty_dispatched - _committed_in_dispatches(db, sol.id)
        limit = min(pending, sol.qty_reserved - sol.qty_dispatched - _committed_in_dispatches(db, sol.id)) \
            if item.is_stocked else pending
        quantity = wanted[sol.id] if wanted is not None else limit
        if quantity <= 0:
            continue
        if quantity > limit:
            raise BusinessRuleViolation(
                f"Línea {sol.line_no}: solicita {quantity} pero solo hay {limit} reservado y pendiente",
                details={"so_line_id": sol.id, "available_to_dispatch": str(limit)})
        d.lines.append(DispatchLine(so_line_id=sol.id, item_id=sol.item_id, qty_requested=quantity))
    if wanted and set(wanted) - set(so_lines):
        raise BusinessRuleViolation("Hay líneas que no pertenecen al pedido")
    if not d.lines:
        raise BusinessRuleViolation("No hay cantidades pendientes para despachar")
    db.add(d)
    db.flush()
    _event(db, d, "created", p.user_id)
    return d


def start_picking(db: Session, p: Principal, d_id: int) -> DispatchOrder:
    d = get_owned(db, DispatchOrder, d_id, p.company_id, lock=True)
    if d.status != "draft":
        raise Conflict("El despacho no está en borrador")
    d.status = "picking"
    _event(db, d, "picking", p.user_id)
    return d


def confirm_picking(db: Session, p: Principal, d_id: int, picks: list[dict]) -> DispatchOrder:
    """Verificación de cantidades preparadas: nunca superan lo solicitado (y por ende lo reservado)."""
    d = get_owned(db, DispatchOrder, d_id, p.company_id, lock=True)
    if d.status != "picking":
        raise Conflict("El despacho no está en preparación")
    by_id = {ln.id: ln for ln in d.lines}
    for pk in picks:
        ln = by_id.get(pk["dispatch_line_id"])
        if ln is None:
            raise BusinessRuleViolation("Línea de despacho inexistente")
        picked = q(pk["qty_picked"])
        if picked < 0 or picked > ln.qty_requested:
            raise BusinessRuleViolation(f"Cantidad preparada inválida (máximo {ln.qty_requested})")
        ln.qty_picked = picked
    if all(ln.qty_picked == 0 for ln in d.lines):
        raise BusinessRuleViolation("No se preparó ninguna cantidad")
    d.status, d.picked_at = "picked", datetime.now(UTC)
    _event(db, d, "picked", p.user_id)
    return d


def pack(db: Session, p: Principal, d_id: int, packages: int, weight: Decimal) -> DispatchOrder:
    d = get_owned(db, DispatchOrder, d_id, p.company_id, lock=True)
    if d.status != "picked":
        raise Conflict("El despacho debe estar preparado para empacar")
    if packages <= 0:
        raise BusinessRuleViolation("Indique el número de bultos")
    d.packages_count, d.gross_weight_kg, d.status, d.packed_at = packages, weight, "packed", datetime.now(UTC)
    _event(db, d, "packed", p.user_id)
    return d


def ship(db: Session, p: Principal, d_id: int, data: dict) -> DispatchOrder:
    """Salida física: consume reservas (nunca más de lo reservado), registra costo de ventas y documento de salida."""
    d = get_owned(db, DispatchOrder, d_id, p.company_id, lock=True)
    if d.status != "packed":
        raise Conflict("El despacho debe estar empacado para enviarse")
    if data.get("carrier_id"):
        carrier = get_owned(db, Party, data["carrier_id"], p.company_id)
        if not carrier.is_carrier:
            raise BusinessRuleViolation("El tercero indicado no es transportista")
    for k in ("carrier_id", "vehicle_plate", "driver_name", "tracking_number", "freight_cost", "route_id"):
        if data.get(k) is not None:
            setattr(d, k, data[k])
    so = db.get(SalesOrder, d.sales_order_id, with_for_update=True)
    cogs: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for ln in d.lines:
        if ln.qty_picked <= 0:
            continue
        sol = db.get(SalesOrderLine, ln.so_line_id)
        item = db.get(Item, ln.item_id)
        remaining, value = ln.qty_picked, ZERO
        if item.is_stocked:
            for res in sales.active_reservations(db, sol.id):
                if remaining <= 0:
                    break
                take = min(remaining, res.quantity - res.quantity_consumed)
                mv = stock.issue(db, p.company_id, item_id=ln.item_id, location_id=res.location_id, quantity=take,
                                 move_type="dispatch", lot_id=res.lot_id, reservation=res,
                                 src=stock.MoveSource("dispatch", d.id, ln.id, d.number),
                                 reason=f"Despacho pedido {so.number}", user_id=p.user_id)
                remaining -= take
                value += mv.total_cost
            if remaining > 0:
                raise BusinessRuleViolation(
                    f"El despacho de {item.sku} excede la cantidad reservada en {remaining}",
                    details={"dispatch_line_id": ln.id})
            cogs[ln.item_id] += value
            ln.unit_cost = (value / ln.qty_picked).quantize(Decimal("0.000001"))
        ln.qty_shipped = ln.qty_picked
        sol.qty_dispatched += ln.qty_shipped
    sales.refresh_status(so)
    d.status, d.shipped_at = "shipped", datetime.now(UTC)
    post_inventory_value(db, company_id=p.company_id, entry_date=d.shipped_at.date(), key=f"dispatch:{d.id}",
                         description=f"Costo de ventas despacho {d.number}", source_type="dispatch", source_id=d.id,
                         by_item=dict(cogs), counter_key="cogs", inbound=False, user_id=p.user_id)
    _event(db, d, "shipped", p.user_id, notes=data.get("notes"))
    log_action(db, "post", "dispatch_orders", d.id, f"Despacho enviado {d.number}")
    return d


def deliver(db: Session, p: Principal, d_id: int, data: dict) -> DispatchOrder:
    d = get_owned(db, DispatchOrder, d_id, p.company_id, lock=True)
    if d.status != "shipped":
        raise Conflict("Solo se confirma la entrega de despachos enviados")
    if not data.get("received_by"):
        raise BusinessRuleViolation("La evidencia de entrega exige el nombre de quien recibe")
    delivered = {x["dispatch_line_id"]: q(x["qty_delivered"]) for x in data.get("lines") or []}
    for ln in d.lines:
        qty_del = delivered.get(ln.id, ln.qty_shipped)
        if qty_del < 0 or qty_del > ln.qty_shipped:
            raise BusinessRuleViolation("La cantidad entregada no puede superar la enviada")
        ln.qty_delivered = qty_del
    full = all(ln.qty_delivered == ln.qty_shipped for ln in d.lines)
    d.status = "delivered" if full else "partially_delivered"
    d.delivered_at = data.get("delivered_at") or datetime.now(UTC)
    d.pod_received_by, d.pod_notes = data["received_by"], data.get("notes")
    _event(db, d, d.status, p.user_id, notes=data.get("notes"))
    if not full:
        db.add(DeliveryIncident(company_id=p.company_id, dispatch_id=d.id, incident_type="missing",
                                description="Entrega parcial registrada en la evidencia de entrega",
                                created_by_id=p.user_id))
    return d


def cancel_dispatch(db: Session, p: Principal, d_id: int, reason: str) -> DispatchOrder:
    d = get_owned(db, DispatchOrder, d_id, p.company_id, lock=True)
    if d.status not in _OPEN:
        raise BusinessRuleViolation("Solo se anulan despachos no enviados (las reservas siguen en el pedido)")
    d.status = "cancelled"
    _event(db, d, "cancelled", p.user_id, notes=reason)
    log_action(db, "void", "dispatch_orders", d.id, reason)
    return d


def register_incident(db: Session, p: Principal, d_id: int, data: dict) -> DeliveryIncident:
    d = get_owned(db, DispatchOrder, d_id, p.company_id)
    inc = DeliveryIncident(company_id=p.company_id, dispatch_id=d.id, created_by_id=p.user_id, **data)
    db.add(inc)
    db.flush()
    return inc


def resolve_incident(db: Session, p: Principal, inc_id: int, resolution: str) -> DeliveryIncident:
    inc = get_owned(db, DeliveryIncident, inc_id, p.company_id, lock=True)
    if inc.status == "resolved":
        raise Conflict("La incidencia ya está resuelta")
    inc.status, inc.resolution, inc.resolved_at = "resolved", resolution, datetime.now(UTC)
    return inc


def receive_return(db: Session, p: Principal, d_id: int, data: dict) -> CustomerReturn:
    """Devolución de cliente: reingresa al costo original del despacho y revierte el costo de ventas."""
    from app.modules.quality.service import raise_nc

    d = get_owned(db, DispatchOrder, d_id, p.company_id, lock=True)
    if d.status not in ("shipped", "delivered", "partially_delivered"):
        raise BusinessRuleViolation("Solo se reciben devoluciones de despachos enviados")
    stock.get_location(db, p.company_id, data["location_id"])
    ret = CustomerReturn(company_id=p.company_id, number=next_number(db, p.company_id, "customer_return"),
                         dispatch_id=d.id, customer_id=d.customer_id, location_id=data["location_id"],
                         return_date=data["return_date"], reason=data["reason"], status="received",
                         created_by_id=p.user_id)
    by_id = {ln.id: ln for ln in d.lines}
    values: dict[int, Decimal] = defaultdict(lambda: ZERO)
    db.add(ret)
    db.flush()
    for x in data["lines"]:
        ln = by_id.get(x["dispatch_line_id"])
        if ln is None:
            raise BusinessRuleViolation("La línea no pertenece al despacho")
        quantity = q(x["quantity"])
        if quantity <= 0 or ln.qty_returned + quantity > ln.qty_shipped:
            raise BusinessRuleViolation("La devolución supera la cantidad despachada")
        item = db.get(Item, ln.item_id)
        rl = CustomerReturnLine(dispatch_line_id=ln.id, item_id=ln.item_id, lot_id=x.get("lot_id"),
                                quantity=quantity, condition=x.get("condition", "resellable"))
        ret.lines.append(rl)
        db.flush()
        if item.is_stocked:
            mv = stock.receive(db, p.company_id, item_id=ln.item_id, location_id=ret.location_id, quantity=quantity,
                               unit_cost=ln.unit_cost or ZERO, move_type="customer_return", lot_id=rl.lot_id,
                               src=stock.MoveSource("customer_return", ret.id, rl.id, ret.number),
                               reason=f"Devolución {ret.number}: {ret.reason}", user_id=p.user_id)
            values[ln.item_id] += mv.total_cost
        ln.qty_returned += quantity
        db.get(SalesOrderLine, ln.so_line_id).qty_returned += quantity
        if rl.condition == "damaged":
            raise_nc(db, p, source="customer", description=f"Producto devuelto en mal estado ({ret.number}): "
                     f"{ret.reason}", severity="major", item_id=ln.item_id, lot_id=rl.lot_id,
                     customer_id=d.customer_id, quantity_affected=quantity, category="devolucion_cliente")
    post_inventory_value(db, company_id=p.company_id, entry_date=ret.return_date, key=f"customer_return:{ret.id}",
                         description=f"Devolución de cliente {ret.number}", source_type="customer_return",
                         source_id=ret.id, by_item=dict(values), counter_key="cogs", inbound=True, user_id=p.user_id)
    _event(db, d, "returned", p.user_id, notes=ret.reason)
    log_action(db, "post", "customer_returns", ret.id, ret.reason)
    return ret
