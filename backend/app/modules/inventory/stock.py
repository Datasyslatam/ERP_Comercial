"""Motor de inventario: entradas, salidas, transferencias y reservas con bloqueo por fila.

Todas las cantidades se expresan en la unidad base del artículo. La valoración es costo promedio
ponderado perpetuo por empresa. Las funciones no hacen commit: participan en la transacción del llamador.
"""
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleViolation, NotFound
from app.core.money import ZERO, money
from app.core.money import qty as q
from app.modules.inventory.models import ItemCost, Location, Lot, StockBalance, StockMove, StockReservation, Warehouse
from app.modules.masters.models import Item

COST_Q = Decimal("0.000001")


@dataclass
class MoveSource:
    source_type: str
    source_id: int
    source_line_id: int | None = None
    reference: str | None = None


def get_item(db: Session, company_id: int, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None or item.company_id != company_id:
        raise NotFound(f"Artículo {item_id} no encontrado")
    return item


def get_location(db: Session, company_id: int, location_id: int) -> Location:
    loc = db.get(Location, location_id)
    if loc is None or loc.company_id != company_id or not loc.is_active:
        raise NotFound(f"Ubicación {location_id} no encontrada o inactiva")
    return loc


def get_or_create_lot(db: Session, company_id: int, item: Item, lot_number: str | None, *,
                      expiry_date: date | None = None, supplier_id: int | None = None,
                      status: str = "released") -> Lot | None:
    if not (item.track_lots or item.track_serials):
        if lot_number:
            raise BusinessRuleViolation(f"El artículo {item.sku} no maneja lotes")
        return None
    if not lot_number:
        raise BusinessRuleViolation(f"El artículo {item.sku} exige número de lote/serie")
    if item.track_expiry and expiry_date is None:
        raise BusinessRuleViolation(f"El artículo {item.sku} exige fecha de vencimiento")
    lot = db.scalar(select(Lot).where(Lot.company_id == company_id, Lot.item_id == item.id,
                                      Lot.lot_number == lot_number))
    if lot is None:
        lot = Lot(company_id=company_id, item_id=item.id, lot_number=lot_number, expiry_date=expiry_date,
                  supplier_id=supplier_id, status=status)
        db.add(lot)
        db.flush()
    return lot


def _lock_balance(db: Session, company_id: int, item_id: int, location_id: int, lot_id: int | None) -> StockBalance:
    db.flush()  # populate_existing refresca desde BD: primero se persisten los cambios pendientes
    stmt = pg_insert(StockBalance).values(
        company_id=company_id, item_id=item_id, location_id=location_id, lot_id=lot_id, qty_on_hand=0, qty_reserved=0
    ).on_conflict_do_nothing()
    db.execute(stmt)
    lot_cond = StockBalance.lot_id.is_(None) if lot_id is None else StockBalance.lot_id == lot_id
    return db.scalar(
        select(StockBalance)
        .where(StockBalance.item_id == item_id, StockBalance.location_id == location_id, lot_cond)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _lock_cost(db: Session, company_id: int, item_id: int) -> ItemCost:
    db.flush()
    db.execute(pg_insert(ItemCost).values(company_id=company_id, item_id=item_id, avg_cost=0, qty_total=0)
               .on_conflict_do_nothing())
    return db.scalar(select(ItemCost).where(ItemCost.company_id == company_id, ItemCost.item_id == item_id)
                     .with_for_update().execution_options(populate_existing=True))


def current_cost(db: Session, company_id: int, item_id: int) -> Decimal:
    c = db.get(ItemCost, {"item_id": item_id, "company_id": company_id})
    return c.avg_cost if c else ZERO


def _move(db: Session, company_id: int, *, move_type: str, item_id: int, lot_id: int | None, from_loc: int | None,
          to_loc: int | None, quantity: Decimal, unit_cost: Decimal, src: MoveSource, reason: str,
          user_id: int | None, move_date: datetime | None) -> StockMove:
    if not reason or not reason.strip():
        raise BusinessRuleViolation("Todo movimiento de inventario requiere un motivo")
    mv = StockMove(
        company_id=company_id, move_type=move_type, item_id=item_id, lot_id=lot_id, from_location_id=from_loc,
        to_location_id=to_loc, quantity=quantity, unit_cost=unit_cost, total_cost=money(quantity * unit_cost),
        source_type=src.source_type, source_id=src.source_id, source_line_id=src.source_line_id,
        reference=src.reference, reason=reason, created_by_id=user_id, move_date=move_date or datetime.now(UTC),
    )
    db.add(mv)
    return mv


def receive(db: Session, company_id: int, *, item_id: int, location_id: int, quantity, unit_cost, move_type: str,
            src: MoveSource, reason: str, user_id: int | None, lot_id: int | None = None,
            move_date: datetime | None = None) -> StockMove:
    """Entrada valorizada: actualiza saldo y costo promedio ponderado."""
    quantity, unit_cost = q(quantity), Decimal(unit_cost).quantize(COST_Q)
    if quantity <= 0:
        raise BusinessRuleViolation("La cantidad recibida debe ser positiva")
    if unit_cost < 0:
        raise BusinessRuleViolation("El costo unitario no puede ser negativo")
    item = get_item(db, company_id, item_id)
    if not item.is_stocked:
        raise BusinessRuleViolation(f"El artículo {item.sku} no es inventariable")
    get_location(db, company_id, location_id)
    cost = _lock_cost(db, company_id, item_id)
    bal = _lock_balance(db, company_id, item_id, location_id, lot_id)
    new_qty = cost.qty_total + quantity
    cost.avg_cost = ((cost.qty_total * cost.avg_cost + quantity * unit_cost) / new_qty).quantize(COST_Q)
    cost.qty_total = new_qty
    bal.qty_on_hand += quantity
    return _move(db, company_id, move_type=move_type, item_id=item_id, lot_id=lot_id, from_loc=None,
                 to_loc=location_id, quantity=quantity, unit_cost=unit_cost, src=src, reason=reason,
                 user_id=user_id, move_date=move_date)


def issue(db: Session, company_id: int, *, item_id: int, location_id: int, quantity, move_type: str,
          src: MoveSource, reason: str, user_id: int | None, lot_id: int | None = None,
          reservation: StockReservation | None = None, move_date: datetime | None = None,
          unit_cost: Decimal | None = None) -> StockMove:
    """Salida al costo promedio vigente. Con reserva, consume la cantidad reservada."""
    quantity = q(quantity)
    if quantity <= 0:
        raise BusinessRuleViolation("La cantidad a retirar debe ser positiva")
    get_item(db, company_id, item_id)
    cost = _lock_cost(db, company_id, item_id)
    bal = _lock_balance(db, company_id, item_id, location_id, lot_id)
    if reservation is not None:
        pending = reservation.quantity - reservation.quantity_consumed
        if reservation.status != "active" or quantity > pending:
            raise BusinessRuleViolation("La salida excede la cantidad reservada pendiente")
        if (reservation.location_id, reservation.lot_id) != (location_id, lot_id):
            raise BusinessRuleViolation("La salida no corresponde a la ubicación/lote reservados")
        bal.qty_reserved -= quantity
        reservation.quantity_consumed += quantity
        if reservation.quantity_consumed == reservation.quantity:
            reservation.status = "consumed"
    else:
        available = bal.qty_on_hand - bal.qty_reserved
        if quantity > available:
            raise BusinessRuleViolation(
                "Existencia disponible insuficiente",
                details={"item_id": item_id, "location_id": location_id, "available": str(available),
                         "requested": str(quantity)},
            )
    if quantity > bal.qty_on_hand:
        raise BusinessRuleViolation("La operación dejaría inventario negativo")
    bal.qty_on_hand -= quantity
    used_cost = cost.avg_cost if unit_cost is None else Decimal(unit_cost).quantize(COST_Q)
    cost.qty_total -= quantity
    if cost.qty_total == 0:
        cost.avg_cost = cost.avg_cost  # se conserva el último costo como referencia
    return _move(db, company_id, move_type=move_type, item_id=item_id, lot_id=lot_id, from_loc=location_id,
                 to_loc=None, quantity=quantity, unit_cost=used_cost, src=src, reason=reason, user_id=user_id,
                 move_date=move_date)


def transfer(db: Session, company_id: int, *, item_id: int, from_location_id: int, to_location_id: int, quantity,
             src: MoveSource, reason: str, user_id: int | None, lot_id: int | None = None,
             respect_reservations: bool = True) -> StockMove:
    quantity = q(quantity)
    if quantity <= 0:
        raise BusinessRuleViolation("La cantidad a transferir debe ser positiva")
    if from_location_id == to_location_id:
        raise BusinessRuleViolation("Origen y destino deben ser diferentes")
    get_location(db, company_id, to_location_id)
    # Bloqueo en orden determinista para evitar interbloqueos.
    first, second = sorted([from_location_id, to_location_id])
    b1 = _lock_balance(db, company_id, item_id, first, lot_id)
    b2 = _lock_balance(db, company_id, item_id, second, lot_id)
    src_bal, dst_bal = (b1, b2) if first == from_location_id else (b2, b1)
    available = src_bal.qty_on_hand - (src_bal.qty_reserved if respect_reservations else ZERO)
    if quantity > available:
        raise BusinessRuleViolation("Existencia disponible insuficiente para transferir",
                                    details={"available": str(available)})
    src_bal.qty_on_hand -= quantity
    dst_bal.qty_on_hand += quantity
    return _move(db, company_id, move_type="transfer", item_id=item_id, lot_id=lot_id, from_loc=from_location_id,
                 to_loc=to_location_id, quantity=quantity, unit_cost=current_cost(db, company_id, item_id), src=src,
                 reason=reason, user_id=user_id, move_date=None)


def reserve(db: Session, company_id: int, *, item_id: int, warehouse_id: int, quantity, source_type: str,
            source_id: int, source_line_id: int, today: date | None = None) -> list[StockReservation]:
    """Reserva FEFO (primero en vencer, primero en salir) sobre lotes liberados y no vencidos."""
    quantity = q(quantity)
    today = today or date.today()
    rows = db.execute(
        select(StockBalance, Lot)
        .join(Location, Location.id == StockBalance.location_id)
        .outerjoin(Lot, Lot.id == StockBalance.lot_id)
        .where(
            StockBalance.company_id == company_id, StockBalance.item_id == item_id,
            Location.warehouse_id == warehouse_id, Location.location_type.in_(("storage", "dispatch")),
            StockBalance.qty_on_hand > StockBalance.qty_reserved,
            or_(StockBalance.lot_id.is_(None),
                and_(Lot.status == "released", or_(Lot.expiry_date.is_(None), Lot.expiry_date >= today))),
        )
        .order_by(Lot.expiry_date.asc().nulls_last(), StockBalance.id)
        .with_for_update(of=StockBalance)
        .execution_options(populate_existing=True)
    ).all()
    remaining = quantity
    created = []
    for bal, _lot in rows:
        if remaining <= 0:
            break
        take = min(remaining, bal.qty_on_hand - bal.qty_reserved)
        if take <= 0:
            continue
        bal.qty_reserved += take
        res = StockReservation(company_id=company_id, item_id=item_id, location_id=bal.location_id,
                               lot_id=bal.lot_id, quantity=take, source_type=source_type, source_id=source_id,
                               source_line_id=source_line_id)
        db.add(res)
        created.append(res)
        remaining -= take
    if remaining > 0:
        raise BusinessRuleViolation(
            "Existencia disponible insuficiente para reservar",
            details={"item_id": item_id, "requested": str(quantity), "missing": str(remaining)},
        )
    db.flush()
    return created


def release_reservation(db: Session, res: StockReservation) -> Decimal:
    if res.status != "active":
        return ZERO
    pending = res.quantity - res.quantity_consumed
    bal = _lock_balance(db, res.company_id, res.item_id, res.location_id, res.lot_id)
    bal.qty_reserved -= pending
    res.status = "released" if res.quantity_consumed == 0 else "consumed"
    if res.quantity_consumed > 0:
        res.quantity = res.quantity_consumed
    return pending


def available_qty(db: Session, company_id: int, item_id: int, warehouse_id: int | None = None) -> Decimal:
    stmt = (select(func.coalesce(func.sum(StockBalance.qty_on_hand - StockBalance.qty_reserved), 0))
            .join(Location, Location.id == StockBalance.location_id)
            .outerjoin(Lot, Lot.id == StockBalance.lot_id)
            .where(StockBalance.company_id == company_id, StockBalance.item_id == item_id,
                   Location.location_type.in_(("storage", "dispatch")),
                   or_(StockBalance.lot_id.is_(None), Lot.status == "released")))
    if warehouse_id:
        stmt = stmt.where(Location.warehouse_id == warehouse_id)
    return Decimal(db.scalar(stmt))


def default_location(db: Session, company_id: int, warehouse_id: int, location_type: str) -> Location:
    loc = db.scalar(select(Location).where(Location.company_id == company_id, Location.warehouse_id == warehouse_id,
                                           Location.location_type == location_type, Location.is_active.is_(True))
                    .order_by(Location.id))
    if loc is None:
        wh = db.get(Warehouse, warehouse_id)
        raise BusinessRuleViolation(
            f"La bodega {wh.code if wh else warehouse_id} no tiene ubicación de tipo '{location_type}'"
        )
    return loc


def consistency_report(db: Session, company_id: int) -> list[dict]:
    """Compara saldos proyectados contra la suma de movimientos. Lista vacía = inventario consistente."""
    sql = text("""
        with mv as (
            select item_id, loc as location_id, lot_id, sum(qty) as qty from (
                select item_id, to_location_id as loc, lot_id, quantity as qty from stock_moves
                 where company_id = :c and to_location_id is not null
                union all
                select item_id, from_location_id, lot_id, -quantity from stock_moves
                 where company_id = :c and from_location_id is not null
            ) x group by item_id, loc, lot_id
        )
        select coalesce(b.item_id, mv.item_id) item_id, coalesce(b.location_id, mv.location_id) location_id,
               coalesce(b.lot_id, mv.lot_id) lot_id, coalesce(b.qty_on_hand, 0) balance, coalesce(mv.qty, 0) moves
          from (select * from stock_balances where company_id = :c) b
          full join mv on mv.item_id = b.item_id and mv.location_id = b.location_id
                      and coalesce(mv.lot_id, 0) = coalesce(b.lot_id, 0)
         where coalesce(b.qty_on_hand, 0) <> coalesce(mv.qty, 0)
    """)
    return [dict(r._mapping) for r in db.execute(sql, {"c": company_id})]
