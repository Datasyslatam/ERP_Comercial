"""Documentos de inventario (transferencias, ajustes, consumos, bajas), conteos físicos y kardex."""
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.crud import get_owned
from app.core.deps import Principal
from app.core.errors import BusinessRuleViolation, Conflict
from app.core.money import ZERO, money
from app.core.money import qty as q
from app.core.numbering import next_number
from app.core.policies import enforce_approval_limit, enforce_sod
from app.modules.accounting.posting import post_inventory_value
from app.modules.inventory import stock
from app.modules.inventory.models import (
    InventoryDocument,
    InventoryDocumentLine,
    Location,
    PhysicalCount,
    PhysicalCountLine,
    StockBalance,
)


def create_document(db: Session, p: Principal, data: dict) -> InventoryDocument:
    lines = data.pop("lines")
    if not lines:
        raise BusinessRuleViolation("El documento requiere líneas")
    doc = InventoryDocument(company_id=p.company_id, number=next_number(db, p.company_id, "inventory_document"),
                            created_by_id=p.user_id, **data)
    for ln in lines:
        stock.get_item(db, p.company_id, ln["item_id"])
        for k in ("from_location_id", "to_location_id"):
            if ln.get(k):
                stock.get_location(db, p.company_id, ln[k])
        t = doc.doc_type
        if t == "transfer" and not (ln.get("from_location_id") and ln.get("to_location_id")):
            raise BusinessRuleViolation("Las transferencias requieren ubicación de origen y destino")
        if t in ("consumption", "scrap") and (not ln.get("from_location_id") or Decimal(ln["quantity"]) <= 0):
            raise BusinessRuleViolation("Consumos y bajas requieren ubicación de origen y cantidad positiva")
        if t == "adjustment":
            loc = ln.get("to_location_id") if Decimal(ln["quantity"]) > 0 else ln.get("from_location_id")
            if not loc:
                raise BusinessRuleViolation("Ajuste positivo exige ubicación destino; negativo exige ubicación origen")
        doc.lines.append(InventoryDocumentLine(**ln))
    if doc.doc_type == "consumption" and not doc.cost_center_id:
        raise BusinessRuleViolation("Los consumos internos requieren centro de costo")
    db.add(doc)
    db.flush()
    return doc


def _doc_value(db: Session, doc: InventoryDocument) -> Decimal:
    total = ZERO
    for ln in doc.lines:
        cost = ln.unit_cost if (ln.quantity > 0 and ln.unit_cost is not None) else stock.current_cost(db, doc.company_id,
                                                                                                    ln.item_id)
        total += abs(ln.quantity) * cost
    return money(total)


def approve_document(db: Session, p: Principal, doc_id: int) -> InventoryDocument:
    doc = get_owned(db, InventoryDocument, doc_id, p.company_id, lock=True)
    if doc.status != "draft":
        raise Conflict("El documento no está en borrador")
    enforce_sod(p, "sod_adjustment_self_approval", doc.created_by_id, "aprobar")
    enforce_approval_limit(db, p, "inventory_adjustment", _doc_value(db, doc))
    doc.status, doc.approved_by_id = "approved", p.user_id
    log_action(db, "approve", "inventory_documents", doc.id, doc.reason)
    return doc


def post_document(db: Session, p: Principal, doc_id: int) -> InventoryDocument:
    doc = get_owned(db, InventoryDocument, doc_id, p.company_id, lock=True)
    if doc.status == "posted":
        return doc
    needs_approval = doc.doc_type in ("adjustment", "scrap")
    if needs_approval and doc.status != "approved":
        raise BusinessRuleViolation("Los ajustes y bajas deben aprobarse antes de aplicarse")
    if doc.status not in ("draft", "approved"):
        raise Conflict("Estado inválido para aplicar")
    ins: dict[int, Decimal] = defaultdict(lambda: ZERO)
    outs: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for ln in doc.lines:
        src = stock.MoveSource("inventory_document", doc.id, ln.id, doc.number)
        if doc.doc_type == "transfer":
            stock.transfer(db, p.company_id, item_id=ln.item_id, from_location_id=ln.from_location_id,
                           to_location_id=ln.to_location_id, quantity=ln.quantity, lot_id=ln.lot_id, src=src,
                           reason=doc.reason, user_id=p.user_id)
        elif ln.quantity > 0 and doc.doc_type == "adjustment":
            cost = ln.unit_cost if ln.unit_cost is not None else stock.current_cost(db, p.company_id, ln.item_id)
            mv = stock.receive(db, p.company_id, item_id=ln.item_id, location_id=ln.to_location_id,
                               quantity=ln.quantity, unit_cost=cost, move_type="adjustment_in", lot_id=ln.lot_id,
                               src=src, reason=doc.reason, user_id=p.user_id)
            ins[ln.item_id] += mv.total_cost
        else:
            move_type = {"adjustment": "adjustment_out", "consumption": "consumption", "scrap": "scrap"}[doc.doc_type]
            mv = stock.issue(db, p.company_id, item_id=ln.item_id, location_id=ln.from_location_id,
                             quantity=abs(ln.quantity), move_type=move_type, lot_id=ln.lot_id, src=src,
                             reason=doc.reason, user_id=p.user_id)
            outs[ln.item_id] += mv.total_cost
    if doc.doc_type != "transfer":
        out_key = {"adjustment": "inventory_adjustment_loss", "scrap": "scrap_expense",
                   "consumption": "inventory_adjustment_loss"}[doc.doc_type]
        post_inventory_value(db, company_id=p.company_id, entry_date=doc.doc_date, key=f"inventory_document_in:{doc.id}",
                             description=f"{doc.number} {doc.reason}", source_type="inventory_document",
                             source_id=doc.id, by_item=dict(ins), counter_key="inventory_adjustment_gain",
                             inbound=True, user_id=p.user_id)
        post_inventory_value(db, company_id=p.company_id, entry_date=doc.doc_date,
                             key=f"inventory_document_out:{doc.id}", description=f"{doc.number} {doc.reason}",
                             source_type="inventory_document", source_id=doc.id, by_item=dict(outs),
                             counter_key=out_key, inbound=False, user_id=p.user_id, cost_center_id=doc.cost_center_id)
    doc.status, doc.posted_at = "posted", datetime.now(UTC)
    log_action(db, "post", "inventory_documents", doc.id, doc.reason)
    return doc


# ---------------------------------------------------------------- conteo físico
def open_count(db: Session, p: Principal, warehouse_id: int, count_date: date, notes: str | None) -> PhysicalCount:
    """Congela las existencias del sistema por ubicación/lote como base del conteo ciego."""
    cnt = PhysicalCount(company_id=p.company_id, number=next_number(db, p.company_id, "physical_count"),
                        warehouse_id=warehouse_id, count_date=count_date, notes=notes, created_by_id=p.user_id)
    rows = db.execute(select(StockBalance).join(Location, Location.id == StockBalance.location_id)
                      .where(StockBalance.company_id == p.company_id, Location.warehouse_id == warehouse_id,
                             StockBalance.qty_on_hand > 0)).scalars().all()
    for b in rows:
        cnt.lines.append(PhysicalCountLine(item_id=b.item_id, location_id=b.location_id, lot_id=b.lot_id,
                                           system_qty=b.qty_on_hand))
    db.add(cnt)
    db.flush()
    return cnt


def record_count(db: Session, p: Principal, count_id: int, entries: list[dict]) -> PhysicalCount:
    cnt = get_owned(db, PhysicalCount, count_id, p.company_id, lock=True)
    if cnt.status != "open":
        raise Conflict("El conteo no está abierto")
    by_key = {(ln.item_id, ln.location_id, ln.lot_id): ln for ln in cnt.lines}
    for e in entries:
        key = (e["item_id"], e["location_id"], e.get("lot_id"))
        ln = by_key.get(key)
        if ln is None:  # artículo encontrado que el sistema no tenía en esa ubicación
            stock.get_item(db, p.company_id, e["item_id"])
            ln = PhysicalCountLine(item_id=e["item_id"], location_id=e["location_id"], lot_id=e.get("lot_id"),
                                   system_qty=ZERO)
            cnt.lines.append(ln)
            by_key[key] = ln
        if Decimal(e["counted_qty"]) < 0:
            raise BusinessRuleViolation("La cantidad contada no puede ser negativa")
        ln.counted_qty = q(e["counted_qty"])
    return cnt


def close_count(db: Session, p: Principal, count_id: int) -> PhysicalCount:
    """Aprueba el conteo y genera los movimientos de diferencia (requiere usuario distinto a quien lo abrió)."""
    cnt = get_owned(db, PhysicalCount, count_id, p.company_id, lock=True)
    if cnt.status != "open":
        raise Conflict("El conteo no está abierto")
    pending = [ln for ln in cnt.lines if ln.counted_qty is None]
    if pending:
        raise BusinessRuleViolation(f"Hay {len(pending)} líneas sin contar")
    enforce_sod(p, "sod_adjustment_self_approval", cnt.created_by_id, "aprobar")
    ins: dict[int, Decimal] = defaultdict(lambda: ZERO)
    outs: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for ln in cnt.lines:
        bal = stock._lock_balance(db, p.company_id, ln.item_id, ln.location_id, ln.lot_id)
        # La diferencia se mide contra la existencia actual: se asume que la bodega no movió mercancía durante
        # el conteo (procedimiento operativo documentado en el manual de usuario).
        diff = ln.counted_qty - bal.qty_on_hand
        src = stock.MoveSource("physical_count", cnt.id, ln.id, cnt.number)
        if diff > 0:
            mv = stock.receive(db, p.company_id, item_id=ln.item_id, location_id=ln.location_id, quantity=diff,
                               unit_cost=stock.current_cost(db, p.company_id, ln.item_id), move_type="count_in",
                               lot_id=ln.lot_id, src=src, reason=f"Sobrante conteo {cnt.number}", user_id=p.user_id)
            ins[ln.item_id] += mv.total_cost
        elif diff < 0:
            if -diff > bal.qty_on_hand - bal.qty_reserved:
                raise BusinessRuleViolation("El faltante afecta cantidades reservadas; libere reservas primero",
                                            details={"item_id": ln.item_id, "location_id": ln.location_id})
            mv = stock.issue(db, p.company_id, item_id=ln.item_id, location_id=ln.location_id, quantity=-diff,
                             move_type="count_out", lot_id=ln.lot_id, src=src, reason=f"Faltante conteo {cnt.number}",
                             user_id=p.user_id)
            outs[ln.item_id] += mv.total_cost
    post_inventory_value(db, company_id=p.company_id, entry_date=cnt.count_date, key=f"count_in:{cnt.id}",
                         description=f"Sobrantes conteo {cnt.number}", source_type="physical_count", source_id=cnt.id,
                         by_item=dict(ins), counter_key="inventory_adjustment_gain", inbound=True, user_id=p.user_id)
    post_inventory_value(db, company_id=p.company_id, entry_date=cnt.count_date, key=f"count_out:{cnt.id}",
                         description=f"Faltantes conteo {cnt.number}", source_type="physical_count", source_id=cnt.id,
                         by_item=dict(outs), counter_key="inventory_adjustment_loss", inbound=False, user_id=p.user_id)
    cnt.status, cnt.approved_by_id = "posted", p.user_id
    log_action(db, "approve", "physical_counts", cnt.id, "Conteo aprobado y ajustado")
    return cnt


# ---------------------------------------------------------------- consultas
def kardex(db: Session, company_id: int, item_id: int, start: date, end: date, location_id: int | None = None) -> dict:
    """Kardex valorizado con saldo inicial y acumulado, calculado directamente desde los movimientos."""
    loc_filter = "and (to_location_id = :loc or from_location_id = :loc)" if location_id else ""
    sign = ("case when to_location_id = :loc and from_location_id is distinct from :loc then 1 "
            "when from_location_id = :loc and to_location_id is distinct from :loc then -1 else 0 end") if location_id \
        else "case when to_location_id is not null and from_location_id is null then 1 " \
             "when from_location_id is not null and to_location_id is null then -1 else 0 end"
    params = {"c": company_id, "i": item_id, "s": start, "e": end, "loc": location_id}
    opening = db.execute(text(f"""
        select coalesce(sum(({sign}) * quantity), 0) q, coalesce(sum(({sign}) * total_cost), 0) v
          from stock_moves where company_id = :c and item_id = :i and move_date < :s {loc_filter}"""), params).one()
    rows = db.execute(text(f"""
        select id, move_date, move_type, reference, reason, source_type, source_id, lot_id, from_location_id,
               to_location_id, quantity, unit_cost, total_cost, ({sign}) as sign
          from stock_moves where company_id = :c and item_id = :i and move_date >= :s
           and move_date < (cast(:e as date) + 1) {loc_filter}
         order by move_date, id"""), params).all()
    bal_q, bal_v = Decimal(opening.q), Decimal(opening.v)
    out = []
    for r in rows:
        if r.sign == 0 and not location_id:
            continue  # transferencias internas no alteran el saldo de la empresa
        bal_q += r.sign * r.quantity
        bal_v += r.sign * r.total_cost
        out.append({"id": r.id, "date": r.move_date, "type": r.move_type, "reference": r.reference,
                    "reason": r.reason, "source": f"{r.source_type}:{r.source_id}", "lot_id": r.lot_id,
                    "in": r.quantity if r.sign > 0 else None, "out": r.quantity if r.sign < 0 else None,
                    "unit_cost": r.unit_cost, "value": r.sign * r.total_cost, "balance_qty": bal_q,
                    "balance_value": money(bal_v)})
    return {"item_id": item_id, "opening_qty": Decimal(opening.q), "opening_value": money(opening.v),
            "moves": out, "closing_qty": bal_q, "closing_value": money(bal_v)}


def stock_on_hand(db: Session, company_id: int, warehouse_id: int | None = None, item_id: int | None = None,
                  below_min: bool = False) -> list[dict]:
    sql = """
        select b.item_id, i.sku, i.name, l.warehouse_id, b.location_id, l.code location_code, b.lot_id,
               lt.lot_number, lt.expiry_date, lt.status lot_status, b.qty_on_hand, b.qty_reserved,
               b.qty_on_hand - b.qty_reserved as qty_available, coalesce(c.avg_cost, 0) avg_cost,
               round(b.qty_on_hand * coalesce(c.avg_cost, 0), 2) as value, i.min_stock, i.max_stock
          from stock_balances b
          join items i on i.id = b.item_id
          join locations l on l.id = b.location_id
          left join lots lt on lt.id = b.lot_id
          left join item_costs c on c.item_id = b.item_id and c.company_id = b.company_id
         where b.company_id = :c and b.qty_on_hand > 0
    """
    params = {"c": company_id}
    if warehouse_id:
        sql += " and l.warehouse_id = :w"
        params["w"] = warehouse_id
    if item_id:
        sql += " and b.item_id = :i"
        params["i"] = item_id
    rows = [dict(r._mapping) for r in db.execute(text(sql + " order by i.sku, l.code"), params)]
    if below_min:
        totals: dict[int, Decimal] = defaultdict(lambda: ZERO)
        for r in rows:
            totals[r["item_id"]] += r["qty_available"]
        rows = [r for r in rows if totals[r["item_id"]] < r["min_stock"]]
    return rows


def replenishment_alerts(db: Session, company_id: int) -> list[dict]:
    """Artículos inventariables con disponible total por debajo del mínimo (incluye los que no tienen existencia)."""
    sql = text("""
        select i.id item_id, i.sku, i.name, i.min_stock, i.max_stock,
               coalesce(sum(case when (b.lot_id is null or lt.status = 'released')
                                 and l.location_type in ('storage','dispatch')
                            then b.qty_on_hand - b.qty_reserved end), 0) available
          from items i
          left join stock_balances b on b.item_id = i.id
          left join locations l on l.id = b.location_id
          left join lots lt on lt.id = b.lot_id
         where i.company_id = :c and i.is_stocked and i.is_active and i.min_stock > 0
         group by i.id having coalesce(sum(case when (b.lot_id is null or lt.status = 'released')
                                 and l.location_type in ('storage','dispatch')
                            then b.qty_on_hand - b.qty_reserved end), 0) < i.min_stock
         order by i.sku""")
    return [dict(r._mapping) | {"suggested_order": max(r.max_stock - r.available, r.min_stock - r.available)}
            for r in db.execute(sql, {"c": company_id})]


def expiring_lots(db: Session, company_id: int, days: int = 30, today: date | None = None) -> list[dict]:
    today = today or date.today()
    sql = text("""
        select lt.id lot_id, lt.lot_number, lt.expiry_date, lt.status, i.sku, i.name, sum(b.qty_on_hand) qty,
               lt.expiry_date - cast(:t as date) as days_left
          from lots lt join items i on i.id = lt.item_id
          join stock_balances b on b.lot_id = lt.id
         where lt.company_id = :c and lt.expiry_date is not null and lt.expiry_date <= cast(:t as date) + :d
         group by lt.id, i.sku, i.name having sum(b.qty_on_hand) > 0
         order by lt.expiry_date""")
    return [dict(r._mapping) for r in db.execute(sql, {"c": company_id, "t": today, "d": days})]
