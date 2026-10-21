"""Pedidos de venta: cálculo, control de cupo de crédito y reserva de inventario."""
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.crud import check_company_refs, get_owned
from app.core.deps import Principal
from app.core.errors import BusinessRuleViolation, Conflict
from app.core.money import ZERO, money
from app.core.numbering import next_number
from app.modules.accounting.models import OpenItem
from app.modules.inventory import stock
from app.modules.inventory.models import StockReservation
from app.modules.masters.models import Item, Party, Tax
from app.modules.masters.service import compute_taxes
from app.modules.sales.models import SalesOrder, SalesOrderLine, SalesQuote, SalesQuoteLine


def line_net(ln) -> Decimal:
    gross = Decimal(ln.quantity) * Decimal(ln.unit_price)
    return money(gross * (1 - Decimal(ln.discount_pct or 0) / 100))


def create_order(db: Session, p: Principal, data: dict) -> SalesOrder:
    from app.modules.purchasing.service import _resolve_rate

    lines = data.pop("lines")
    if not lines:
        raise BusinessRuleViolation("El pedido requiere al menos una línea")
    check_company_refs(db, SalesOrder, p.company_id, data)
    p.ensure_site(data["site_id"])
    customer = get_owned(db, Party, data["customer_id"], p.company_id)
    if not customer.is_customer or not customer.is_active:
        raise BusinessRuleViolation("El tercero no es un cliente activo")
    data.setdefault("payment_term_id", customer.payment_term_id)
    data.setdefault("delivery_address", customer.address)
    data["exchange_rate"] = _resolve_rate(db, p.company, data["currency"], data["order_date"], data.get("exchange_rate"))
    so = SalesOrder(company_id=p.company_id, number=next_number(db, p.company_id, "sales_order"),
                    created_by_id=p.user_id, **data)
    calc = []
    for i, ln in enumerate(lines, start=1):
        item = get_owned(db, Item, ln["item_id"], p.company_id)
        if not item.is_active:
            raise BusinessRuleViolation(f"El artículo {item.sku} está inactivo")
        if ln.get("unit_price") is None:
            ln["unit_price"] = item.list_price
        tax = get_owned(db, Tax, ln.get("tax_id") or item.sales_tax_id, p.company_id) \
            if (ln.get("tax_id") or item.sales_tax_id) else None
        ln["tax_id"] = tax.id if tax else None
        sol = SalesOrderLine(line_no=i, **ln)
        so.lines.append(sol)
        calc.append((line_net(sol), tax))
    res = compute_taxes(calc, [], "sales")
    so.subtotal, so.tax_total, so.total = res.subtotal, res.tax_total, res.total
    db.add(so)
    db.flush()
    return so


def credit_exposure(db: Session, company_id: int, customer_id: int) -> Decimal:
    open_ar = db.scalar(select(func.coalesce(func.sum(OpenItem.open_amount * OpenItem.exchange_rate), 0)).where(
        OpenItem.company_id == company_id, OpenItem.kind == "receivable", OpenItem.party_id == customer_id,
        OpenItem.status.in_(("open", "partial"))))
    pending_orders = db.scalar(select(func.coalesce(func.sum(SalesOrder.total * SalesOrder.exchange_rate), 0)).where(
        SalesOrder.company_id == company_id, SalesOrder.customer_id == customer_id,
        SalesOrder.status.in_(("confirmed", "partially_dispatched"))))
    return money(Decimal(open_ar) + Decimal(pending_orders))


def confirm_order(db: Session, p: Principal, so_id: int) -> SalesOrder:
    so = get_owned(db, SalesOrder, so_id, p.company_id, lock=True)
    if so.status != "draft":
        raise Conflict("Solo se confirman pedidos en borrador")
    customer = db.get(Party, so.customer_id, with_for_update=True)
    if customer.credit_limit and customer.credit_limit > 0:
        exposure = credit_exposure(db, p.company_id, customer.id) + money(so.total * so.exchange_rate)
        if exposure > customer.credit_limit:
            raise BusinessRuleViolation("El pedido excede el cupo de crédito del cliente",
                                        details={"limit": str(customer.credit_limit), "exposure": str(exposure)})
    for ln in so.lines:
        item = db.get(Item, ln.item_id)
        if not item.is_stocked:
            continue
        stock.reserve(db, p.company_id, item_id=ln.item_id, warehouse_id=so.warehouse_id, quantity=ln.quantity,
                      source_type="sales_order", source_id=so.id, source_line_id=ln.id)
        ln.qty_reserved = ln.quantity
    so.status = "confirmed"
    log_action(db, "approve", "sales_orders", so.id, "Pedido confirmado y reservado")
    return so


def active_reservations(db: Session, so_line_id: int) -> list[StockReservation]:
    return db.scalars(select(StockReservation).where(StockReservation.source_type == "sales_order",
                                                     StockReservation.source_line_id == so_line_id,
                                                     StockReservation.status == "active")
                      .order_by(StockReservation.id).with_for_update()
                      .execution_options(populate_existing=True)).all()


def cancel_order(db: Session, p: Principal, so_id: int, reason: str) -> SalesOrder:
    so = get_owned(db, SalesOrder, so_id, p.company_id, lock=True)
    if any(ln.qty_dispatched > 0 for ln in so.lines):
        raise BusinessRuleViolation("El pedido tiene despachos; ciérrelo en lugar de anularlo")
    if so.status in ("cancelled", "closed"):
        raise Conflict("El pedido ya está cerrado o anulado")
    from app.modules.logistics.models import DispatchOrder

    if db.scalar(select(DispatchOrder.id).where(DispatchOrder.sales_order_id == so.id,
                                                DispatchOrder.status.notin_(("cancelled",))).limit(1)):
        raise BusinessRuleViolation("Anule primero los despachos abiertos del pedido")
    for ln in so.lines:
        for res in active_reservations(db, ln.id):
            stock.release_reservation(db, res)
        ln.qty_reserved = ZERO
    so.status = "cancelled"
    log_action(db, "void", "sales_orders", so.id, reason)
    return so


def refresh_status(so: SalesOrder) -> None:
    if all(ln.qty_dispatched >= ln.quantity for ln in so.lines):
        so.status = "dispatched"
    elif any(ln.qty_dispatched > 0 for ln in so.lines):
        so.status = "partially_dispatched"


def close_order(db: Session, p: Principal, so_id: int, reason: str) -> SalesOrder:
    """Cierra un pedido con saldo pendiente que no se despachará: libera las reservas del saldo."""
    from app.modules.logistics.models import DispatchOrder

    so = get_owned(db, SalesOrder, so_id, p.company_id, lock=True)
    if so.status not in ("confirmed", "partially_dispatched"):
        raise Conflict("Solo se cierran pedidos confirmados o despachados parcialmente")
    if db.scalar(select(DispatchOrder.id).where(DispatchOrder.sales_order_id == so.id,
                                                DispatchOrder.status.in_(("draft", "picking", "picked", "packed")))
                 .limit(1)):
        raise BusinessRuleViolation("El pedido tiene despachos en preparación; termínelos o anúlelos antes de cerrarlo")
    pending = []
    for ln in so.lines:
        for res in active_reservations(db, ln.id):
            stock.release_reservation(db, res)
        ln.qty_reserved = ZERO
        if ln.quantity > ln.qty_dispatched:
            pending.append(f"línea {ln.line_no}: {ln.quantity - ln.qty_dispatched}")
    so.status = "closed"
    detail = "; ".join(pending) or "sin saldo"
    log_action(db, "close", "sales_orders", so.id, f"Cierre con saldo no despachado ({detail}): {reason}")
    return so


# ---------------------------------------------------------------- cotizaciones
def quote_status(q: SalesQuote, today: date | None = None) -> str:
    """Estado efectivo: una cotización abierta con vigencia vencida se presenta como vencida."""
    if q.status in ("draft", "sent") and q.valid_until < (today or date.today()):
        return "expired"
    return q.status


def create_quote(db: Session, p: Principal, data: dict) -> SalesQuote:
    lines = data.pop("lines")
    if not lines:
        raise BusinessRuleViolation("La cotización requiere al menos una línea")
    check_company_refs(db, SalesQuote, p.company_id, data)
    p.ensure_site(data["site_id"])
    customer = get_owned(db, Party, data["customer_id"], p.company_id)
    if not customer.is_customer or not customer.is_active:
        raise BusinessRuleViolation("El tercero no es un cliente activo")
    if data["valid_until"] < data["quote_date"]:
        raise BusinessRuleViolation("La vigencia no puede ser anterior a la fecha de la cotización")
    data.setdefault("payment_term_id", customer.payment_term_id)
    q = SalesQuote(company_id=p.company_id, number=next_number(db, p.company_id, "sales_quote"),
                   created_by_id=p.user_id, **data)
    calc = []
    for i, ln in enumerate(lines, start=1):
        item = get_owned(db, Item, ln["item_id"], p.company_id)
        if not item.is_active:
            raise BusinessRuleViolation(f"El artículo {item.sku} está inactivo")
        if ln.get("unit_price") is None:
            ln["unit_price"] = item.list_price
        tax_id = ln.get("tax_id") or item.sales_tax_id
        tax = get_owned(db, Tax, tax_id, p.company_id) if tax_id else None
        ln["tax_id"] = tax.id if tax else None
        ql = SalesQuoteLine(line_no=i, **ln)
        q.lines.append(ql)
        calc.append((line_net(ql), tax))
    res = compute_taxes(calc, [], "sales")
    q.subtotal, q.tax_total, q.total = res.subtotal, res.tax_total, res.total
    db.add(q)
    db.flush()
    return q


def _open_quote(db: Session, p: Principal, quote_id: int) -> SalesQuote:
    q = get_owned(db, SalesQuote, quote_id, p.company_id, lock=True)
    status = quote_status(q)
    if status == "expired":
        raise BusinessRuleViolation(f"La cotización venció el {q.valid_until.isoformat()}; emita una nueva")
    if status not in ("draft", "sent"):
        raise Conflict("La cotización ya fue cerrada")
    return q


def send_quote(db: Session, p: Principal, quote_id: int) -> SalesQuote:
    q = _open_quote(db, p, quote_id)
    if q.status != "draft":
        raise Conflict("La cotización ya fue enviada")
    q.status = "sent"
    log_action(db, "send", "sales_quotes", q.id, "Cotización enviada al cliente")
    return q


def reject_quote(db: Session, p: Principal, quote_id: int, reason: str) -> SalesQuote:
    q = get_owned(db, SalesQuote, quote_id, p.company_id, lock=True)
    if q.status not in ("draft", "sent"):
        raise Conflict("La cotización ya fue cerrada")
    q.status, q.lost_reason = "rejected", reason
    log_action(db, "reject", "sales_quotes", q.id, f"Cotización perdida: {reason}")
    return q


def convert_quote(db: Session, p: Principal, quote_id: int, data: dict) -> SalesOrder:
    """Genera el pedido de venta con las condiciones cotizadas (precios, descuentos e impuestos)."""
    q = _open_quote(db, p, quote_id)
    so = create_order(db, p, {
        "site_id": q.site_id, "customer_id": q.customer_id, "warehouse_id": data["warehouse_id"],
        "order_date": data.get("order_date") or date.today(), "promised_date": data.get("promised_date"),
        "currency": q.currency, "payment_term_id": q.payment_term_id,
        "notes": f"Cotización {q.number}" + (f". {q.notes}" if q.notes else ""),
        **({"delivery_address": data["delivery_address"]} if data.get("delivery_address") else {}),
        "lines": [{"item_id": ln.item_id, "quantity": ln.quantity, "unit_price": ln.unit_price,
                   "discount_pct": ln.discount_pct, "tax_id": ln.tax_id, "description": ln.description}
                  for ln in q.lines],
    })
    q.status, q.sales_order_id = "accepted", so.id
    log_action(db, "convert", "sales_quotes", q.id, f"Cotización aceptada: pedido {so.number}")
    return so
