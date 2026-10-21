"""Servicios del ciclo de compras con controles de aprobación, tolerancias, cruce a tres vías y contabilización."""
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
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
from app.core.policies import enforce_approval_limit, enforce_sod
from app.modules.accounting.models import BudgetLine, OpenItem
from app.modules.accounting.posting import post_inventory_value, post_supplier_invoice
from app.modules.inventory import stock
from app.modules.inventory.models import Warehouse
from app.modules.masters.models import Item, Party, PaymentTerm, Tax
from app.modules.masters.service import compute_taxes, party_withholdings
from app.modules.purchasing.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    PurchaseRequisitionLine,
    RequestForQuotation,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierInvoiceTax,
    SupplierQuote,
    SupplierQuoteLine,
)


def _supplier(db: Session, company_id: int, party_id: int) -> Party:
    party = get_owned(db, Party, party_id, company_id)
    if not party.is_supplier or not party.is_active:
        raise BusinessRuleViolation(f"El tercero {party.code} no es un proveedor activo")
    return party


def _tax(db: Session, company_id: int, tax_id: int | None) -> Tax | None:
    return get_owned(db, Tax, tax_id, company_id) if tax_id else None


# ---------------------------------------------------------------- solicitudes de compra
def create_requisition(db: Session, p: Principal, data: dict) -> PurchaseRequisition:
    lines = data.pop("lines")
    if not lines:
        raise BusinessRuleViolation("La solicitud requiere al menos una línea")
    check_company_refs(db, PurchaseRequisition, p.company_id, data)
    p.ensure_site(data["site_id"])
    req = PurchaseRequisition(company_id=p.company_id, number=next_number(db, p.company_id, "purchase_requisition"),
                              requested_by_id=p.user_id, **data)
    total = ZERO
    for ln in lines:
        get_owned(db, Item, ln["item_id"], p.company_id)
        req.lines.append(PurchaseRequisitionLine(**ln))
        total += money(Decimal(ln["quantity"]) * Decimal(ln.get("estimated_unit_price") or 0))
    req.total_estimated = total
    db.add(req)
    db.flush()
    return req


def submit_requisition(db: Session, p: Principal, req_id: int) -> PurchaseRequisition:
    req = get_owned(db, PurchaseRequisition, req_id, p.company_id, lock=True)
    if req.status != "draft":
        raise Conflict("Solo se envían solicitudes en borrador")
    req.status = "submitted"
    req.submitted_at = datetime.now(UTC)
    return req


def decide_requisition(db: Session, p: Principal, req_id: int, approve: bool, reason: str | None) -> PurchaseRequisition:
    req = get_owned(db, PurchaseRequisition, req_id, p.company_id, lock=True)
    if req.status != "submitted":
        raise Conflict("La solicitud no está pendiente de aprobación")
    enforce_sod(p, "sod_requisition_self_approval", req.requested_by_id, "aprobar")
    if approve:
        enforce_approval_limit(db, p, "purchase_requisition", req.total_estimated)
        req.status, req.approved_by_id, req.approved_at = "approved", p.user_id, datetime.now(UTC)
    else:
        if not reason:
            raise BusinessRuleViolation("El rechazo requiere un motivo")
        req.status, req.rejection_reason = "rejected", reason
    log_action(db, "approve" if approve else "reject", "purchase_requisitions", req.id, reason)
    return req


# ---------------------------------------------------------------- cotizaciones
def create_rfq(db: Session, p: Principal, requisition_id: int, due_date: date | None) -> RequestForQuotation:
    req = get_owned(db, PurchaseRequisition, requisition_id, p.company_id)
    if req.status != "approved":
        raise BusinessRuleViolation("Solo se cotizan solicitudes aprobadas")
    rfq = RequestForQuotation(company_id=p.company_id, number=next_number(db, p.company_id, "rfq"),
                              requisition_id=req.id, due_date=due_date, created_by_id=p.user_id)
    db.add(rfq)
    db.flush()
    return rfq


def add_quote(db: Session, p: Principal, rfq_id: int, data: dict) -> SupplierQuote:
    rfq = get_owned(db, RequestForQuotation, rfq_id, p.company_id, lock=True)
    if rfq.status != "open":
        raise Conflict("La solicitud de cotización está cerrada")
    _supplier(db, p.company_id, data["supplier_id"])
    req = db.get(PurchaseRequisition, rfq.requisition_id)
    valid_lines = {ln.id: ln for ln in req.lines}
    lines = data.pop("lines")
    quote = SupplierQuote(company_id=p.company_id, rfq_id=rfq.id, **data)
    total = ZERO
    for ln in lines:
        rl = valid_lines.get(ln["requisition_line_id"])
        if rl is None:
            raise BusinessRuleViolation("La línea cotizada no pertenece a la solicitud")
        _tax(db, p.company_id, ln.get("tax_id"))
        quote.lines.append(SupplierQuoteLine(item_id=rl.item_id, **ln))
        total += money(Decimal(ln["quantity"]) * Decimal(ln["unit_price"]))
    quote.total = total
    db.add(quote)
    db.flush()
    return quote


def compare_quotes(db: Session, p: Principal, rfq_id: int) -> dict:
    rfq = get_owned(db, RequestForQuotation, rfq_id, p.company_id)
    req = db.get(PurchaseRequisition, rfq.requisition_id)
    per_line = []
    for rl in req.lines:
        offers = []
        for qt in rfq.quotes:
            for ql in qt.lines:
                if ql.requisition_line_id == rl.id:
                    offers.append({"quote_id": qt.id, "supplier_id": qt.supplier_id, "unit_price": ql.unit_price,
                                   "quantity": ql.quantity, "delivery_days": qt.delivery_days,
                                   "currency": qt.currency})
        offers.sort(key=lambda o: (o["unit_price"], o["delivery_days"]))
        last = last_purchase_price(db, p.company_id, rl.item_id)
        per_line.append({"requisition_line_id": rl.id, "item_id": rl.item_id, "quantity": rl.quantity,
                         "last_price": last, "best": offers[0] if offers else None, "offers": offers})
    totals = sorted(({"quote_id": qt.id, "supplier_id": qt.supplier_id, "total": qt.total,
                      "delivery_days": qt.delivery_days, "lines_quoted": len(qt.lines)} for qt in rfq.quotes),
                    key=lambda t: (-t["lines_quoted"], t["total"]))
    return {"rfq_id": rfq.id, "lines": per_line, "suppliers": totals,
            "recommended_quote_id": totals[0]["quote_id"] if totals else None}


def award_quote(db: Session, p: Principal, rfq_id: int, quote_id: int, warehouse_id: int) -> PurchaseOrder:
    rfq = get_owned(db, RequestForQuotation, rfq_id, p.company_id, lock=True)
    if rfq.status != "open":
        raise Conflict("La solicitud de cotización ya fue adjudicada o cancelada")
    quote = next((qt for qt in rfq.quotes if qt.id == quote_id), None)
    if quote is None:
        raise BusinessRuleViolation("La cotización no pertenece a esta solicitud")
    req = db.get(PurchaseRequisition, rfq.requisition_id)
    for qt in rfq.quotes:
        qt.status = "selected" if qt.id == quote.id else "rejected"
    rfq.status = "awarded"
    po = create_order(db, p, {
        "site_id": req.site_id, "supplier_id": quote.supplier_id, "warehouse_id": warehouse_id,
        "requisition_id": req.id, "quote_id": quote.id, "cost_center_id": req.cost_center_id,
        "order_date": date.today(), "expected_date": date.today() + timedelta(days=quote.delivery_days),
        "currency": quote.currency, "payment_term_id": quote.payment_term_id,
        "lines": [{"item_id": ql.item_id, "quantity": ql.quantity, "unit_price": ql.unit_price, "tax_id": ql.tax_id,
                   "requisition_line_id": ql.requisition_line_id} for ql in quote.lines],
    })
    req.status = "ordered"
    log_action(db, "approve", "rfqs", rfq.id, f"Adjudicada a cotización {quote.id}; OC {po.number}")
    return po


# ---------------------------------------------------------------- órdenes de compra
def _resolve_rate(db: Session, company, currency: str, on: date, given: Decimal | None) -> Decimal:
    if currency == company.functional_currency:
        return Decimal("1")
    if given:
        return Decimal(given)
    from app.modules.org.models import ExchangeRate

    rate = db.scalar(select(ExchangeRate.rate).where(
        ExchangeRate.from_currency == currency, ExchangeRate.to_currency == company.functional_currency,
        ExchangeRate.rate_date <= on).order_by(ExchangeRate.rate_date.desc()).limit(1))
    if rate is None:
        raise BusinessRuleViolation(f"No hay tasa de cambio {currency}->{company.functional_currency} al {on}")
    return rate


def create_order(db: Session, p: Principal, data: dict) -> PurchaseOrder:
    lines = data.pop("lines")
    if not lines:
        raise BusinessRuleViolation("La orden requiere al menos una línea")
    check_company_refs(db, PurchaseOrder, p.company_id, data)
    p.ensure_site(data["site_id"])
    _supplier(db, p.company_id, data["supplier_id"])
    data["exchange_rate"] = _resolve_rate(db, p.company, data["currency"], data["order_date"],
                                          data.get("exchange_rate"))
    po = PurchaseOrder(company_id=p.company_id, number=next_number(db, p.company_id, "purchase_order"),
                       created_by_id=p.user_id, **data)
    calc = []
    for i, ln in enumerate(lines, start=1):
        item = get_owned(db, Item, ln["item_id"], p.company_id)
        if not item.is_active:
            raise BusinessRuleViolation(f"El artículo {item.sku} está inactivo")
        tax = _tax(db, p.company_id, ln.get("tax_id") or item.purchase_tax_id)
        ln["tax_id"] = tax.id if tax else None
        po.lines.append(PurchaseOrderLine(line_no=i, **ln))
        calc.append((money(Decimal(ln["quantity"]) * Decimal(ln["unit_price"])), tax))
    res = compute_taxes(calc, [], "purchases")
    po.subtotal, po.tax_total, po.total = res.subtotal, res.tax_total, res.total
    db.add(po)
    db.flush()
    return po


def submit_order(db: Session, p: Principal, po_id: int) -> PurchaseOrder:
    po = get_owned(db, PurchaseOrder, po_id, p.company_id, lock=True)
    if po.status != "draft":
        raise Conflict("Solo se envían órdenes en borrador")
    po.status = "submitted"
    return po


def budget_status(db: Session, company_id: int, cost_center_id: int | None, on: date,
                  extra: Decimal = ZERO) -> dict:
    budget = db.scalar(select(func.sum(BudgetLine.amount)).where(
        BudgetLine.company_id == company_id, BudgetLine.category == "purchases", BudgetLine.year == on.year,
        BudgetLine.month == on.month,
        BudgetLine.cost_center_id.is_(None) if cost_center_id is None else BudgetLine.cost_center_id == cost_center_id))
    committed = db.scalar(select(func.coalesce(func.sum(PurchaseOrder.subtotal * PurchaseOrder.exchange_rate), 0)).where(
        PurchaseOrder.company_id == company_id,
        PurchaseOrder.status.in_(("approved", "partially_received", "received", "closed")),
        func.extract("year", PurchaseOrder.order_date) == on.year,
        func.extract("month", PurchaseOrder.order_date) == on.month,
        PurchaseOrder.cost_center_id.is_(None) if cost_center_id is None else PurchaseOrder.cost_center_id == cost_center_id))
    committed = money(committed)
    return {"budget": budget, "committed": committed, "after": committed + extra,
            "exceeded": budget is not None and committed + extra > budget}


def decide_order(db: Session, p: Principal, po_id: int, approve: bool, reason: str | None) -> tuple[PurchaseOrder, dict]:
    po = get_owned(db, PurchaseOrder, po_id, p.company_id, lock=True)
    if po.status != "submitted":
        raise Conflict("La orden no está pendiente de aprobación")
    enforce_sod(p, "sod_po_self_approval", po.created_by_id, "aprobar")
    budget = budget_status(db, p.company_id, po.cost_center_id, po.order_date, money(po.subtotal * po.exchange_rate))
    if approve:
        enforce_approval_limit(db, p, "purchase_order", money(po.total * po.exchange_rate))
        if budget["exceeded"] and p.company.setting("purchase_budget_control") == "block":
            raise BusinessRuleViolation("La orden excede el presupuesto de compras del periodo", details=budget)
        po.status, po.approved_by_id, po.approved_at = "approved", p.user_id, datetime.now(UTC)
    else:
        if not reason:
            raise BusinessRuleViolation("El rechazo requiere un motivo")
        po.status = "rejected"
        po.notes = ((po.notes or "") + f"\nRechazo: {reason}").strip()
    log_action(db, "approve" if approve else "reject", "purchase_orders", po.id, reason)
    return po, budget


def cancel_order(db: Session, p: Principal, po_id: int, reason: str) -> PurchaseOrder:
    po = get_owned(db, PurchaseOrder, po_id, p.company_id, lock=True)
    if any(ln.qty_received > 0 for ln in po.lines):
        raise BusinessRuleViolation("No se puede anular una orden con recepciones; ciérrela")
    if po.status in ("cancelled", "closed"):
        raise Conflict("La orden ya está cerrada o anulada")
    po.status = "cancelled"
    log_action(db, "void", "purchase_orders", po.id, reason)
    return po


def _refresh_po_status(po: PurchaseOrder) -> None:
    if all(ln.qty_received - ln.qty_rejected >= ln.quantity for ln in po.lines):
        po.status = "received"
    elif any(ln.qty_received > 0 for ln in po.lines):
        po.status = "partially_received"


# ---------------------------------------------------------------- recepciones
def receive(db: Session, p: Principal, po_id: int, data: dict) -> GoodsReceipt:
    from app.modules.quality.service import create_receiving_inspection

    po = get_owned(db, PurchaseOrder, po_id, p.company_id, lock=True)
    if po.status not in ("approved", "partially_received"):
        raise BusinessRuleViolation("Solo se reciben órdenes aprobadas y no cerradas")
    tolerance = Decimal(str(p.company.setting("receipt_over_tolerance_pct")))
    po_lines = {ln.id: ln for ln in po.lines}
    wh = db.get(Warehouse, po.warehouse_id)
    receiving_loc = data.get("location_id")
    gr = GoodsReceipt(company_id=p.company_id, number=next_number(db, p.company_id, "goods_receipt"),
                      purchase_order_id=po.id, supplier_id=po.supplier_id, receipt_date=data["receipt_date"],
                      supplier_delivery_note=data.get("supplier_delivery_note"), status="posted",
                      received_by_id=p.user_id, posted_at=datetime.now(UTC), location_id=0)
    values: dict[int, Decimal] = defaultdict(lambda: ZERO)
    inspections = []
    if not data["lines"]:
        raise BusinessRuleViolation("La recepción requiere al menos una línea")
    for ln in data["lines"]:
        pl = po_lines.get(ln["po_line_id"])
        if pl is None:
            raise BusinessRuleViolation("La línea no pertenece a la orden")
        quantity = q(ln["quantity"])
        pending = pl.quantity - (pl.qty_received - pl.qty_rejected)
        if quantity > pending * (1 + tolerance / 100):
            raise BusinessRuleViolation(
                f"Línea {pl.line_no}: se recibe {quantity} y solo quedan {pending} pendientes",
                details={"po_line_id": pl.id, "pending": str(pending)})
        item = db.get(Item, pl.item_id)
        needs_qc = item.requires_inspection
        lot = stock.get_or_create_lot(db, p.company_id, item, ln.get("lot_number"), expiry_date=ln.get("expiry_date"),
                                      supplier_id=po.supplier_id, status="quarantine" if needs_qc else "released")
        if lot is not None and needs_qc and lot.status == "released":
            lot.status = "quarantine"
        loc_type = "quality" if needs_qc else "storage"
        loc_id = stock.default_location(db, p.company_id, wh.id, loc_type).id if (needs_qc or not receiving_loc) \
            else receiving_loc
        unit_cost = (pl.unit_price * po.exchange_rate).quantize(Decimal("0.000001"))
        grl = GoodsReceiptLine(po_line_id=pl.id, item_id=pl.item_id, quantity=quantity, lot_number=ln.get("lot_number"),
                               expiry_date=ln.get("expiry_date"), lot_id=lot.id if lot else None, unit_cost=unit_cost,
                               qty_accepted=ZERO if needs_qc else quantity,
                               inspection_status="pending" if needs_qc else "not_required")
        gr.lines.append(grl)
        gr.location_id = loc_id
        pl.qty_received += quantity
        values[pl.item_id] += money(quantity * unit_cost)
        inspections.append((grl, needs_qc, loc_id))
    db.add(gr)
    db.flush()
    for grl, needs_qc, loc_id in inspections:
        stock.receive(db, p.company_id, item_id=grl.item_id, location_id=loc_id, quantity=grl.quantity,
                      unit_cost=grl.unit_cost, move_type="receipt", lot_id=grl.lot_id,
                      src=stock.MoveSource("goods_receipt", gr.id, grl.id, gr.number),
                      reason=f"Recepción OC {po.number}", user_id=p.user_id)
        if needs_qc:
            create_receiving_inspection(db, p, grl, gr)
    _refresh_po_status(po)
    post_inventory_value(db, company_id=p.company_id, entry_date=gr.receipt_date, key=f"goods_receipt:{gr.id}",
                         description=f"Recepción {gr.number} OC {po.number}", source_type="goods_receipt",
                         source_id=gr.id, by_item=values, counter_key="grni", inbound=True, user_id=p.user_id)
    log_action(db, "post", "goods_receipts", gr.id, f"Recepción {gr.number} de OC {po.number}")
    return gr


# ---------------------------------------------------------------- facturas de proveedor (cruce a tres vías)
def create_supplier_invoice(db: Session, p: Principal, data: dict) -> SupplierInvoice:
    supplier = _supplier(db, p.company_id, data["supplier_id"])
    dup = db.scalar(select(SupplierInvoice.id).where(
        SupplierInvoice.company_id == p.company_id, SupplierInvoice.supplier_id == supplier.id,
        SupplierInvoice.supplier_invoice_number == data["supplier_invoice_number"]))
    if dup:
        raise Conflict("Esta factura del proveedor ya fue registrada", details={"invoice_id": dup})
    lines = data.pop("lines")
    if not lines:
        raise BusinessRuleViolation("La factura requiere al menos una línea")
    data["exchange_rate"] = _resolve_rate(db, p.company, data["currency"], data["invoice_date"],
                                          data.get("exchange_rate"))
    if not data.get("due_date"):
        term = db.get(PaymentTerm, supplier.payment_term_id) if supplier.payment_term_id else None
        data["due_date"] = data["invoice_date"] + timedelta(days=term.days if term else 0)
    tol_price = Decimal(str(p.company.setting("invoice_price_tolerance_pct")))
    inv = SupplierInvoice(company_id=p.company_id, number=next_number(db, p.company_id, "supplier_invoice"),
                          created_by_id=p.user_id, **data)
    calc, notes, status = [], [], "matched"
    for ln in lines:
        if ln.get("receipt_line_id"):
            rl = db.get(GoodsReceiptLine, ln["receipt_line_id"])
            gr = db.get(GoodsReceipt, rl.receipt_id) if rl else None
            if gr is None or gr.company_id != p.company_id or gr.supplier_id != supplier.id:
                raise BusinessRuleViolation("La línea de recepción no corresponde al proveedor")
            pl = db.get(PurchaseOrderLine, rl.po_line_id)
            po = db.get(PurchaseOrder, pl.purchase_order_id)
            if po.currency != inv.currency:
                raise BusinessRuleViolation("La moneda de la factura difiere de la orden de compra")
            invoiceable = rl.qty_accepted - rl.qty_invoiced
            quantity = q(ln["quantity"])
            if quantity > invoiceable:
                raise BusinessRuleViolation(
                    f"Se factura {quantity} pero solo hay {invoiceable} recibido y aceptado sin facturar",
                    details={"receipt_line_id": rl.id})
            price = Decimal(ln["unit_price"])
            if pl.unit_price and abs(price - pl.unit_price) / pl.unit_price * 100 > tol_price:
                raise BusinessRuleViolation(
                    f"Precio {price} fuera de tolerancia frente a la OC ({pl.unit_price})",
                    details={"po_line_id": pl.id, "tolerance_pct": str(tol_price)})
            if price != pl.unit_price:
                notes.append(f"Línea OC {pl.line_no}: precio {price} vs {pl.unit_price}")
                status = "price_variance"
            rl.qty_invoiced += quantity
            pl.qty_invoiced += quantity
            ln["po_line_id"], ln["item_id"] = pl.id, pl.item_id
            if not ln.get("tax_id"):
                ln["tax_id"] = pl.tax_id
            inv.purchase_order_id = inv.purchase_order_id or po.id
        else:
            if not ln.get("expense_account_id") and not ln.get("item_id"):
                raise BusinessRuleViolation("Las líneas sin recepción requieren cuenta de gasto o artículo de servicio")
            status = "no_receipt" if status == "matched" else status
        tax = _tax(db, p.company_id, ln.get("tax_id"))
        subtotal = money(Decimal(ln["quantity"]) * Decimal(ln["unit_price"]))
        inv.lines.append(SupplierInvoiceLine(line_subtotal=subtotal, **ln))
        calc.append((subtotal, tax))
    res = compute_taxes(calc, party_withholdings(db, supplier, p.company.is_withholding_agent, "purchases"),
                        "purchases")
    for t in res.taxes + res.withholdings:
        inv.taxes.append(SupplierInvoiceTax(tax_id=t.tax.id, base=t.base, rate=t.tax.rate, amount=t.amount,
                                            is_withholding=t.is_withholding))
    inv.subtotal, inv.tax_total, inv.withholding_total = res.subtotal, res.tax_total, res.withholding_total
    inv.total = res.total
    inv.payable_total = res.total - res.withholding_total
    inv.match_status, inv.match_notes = status, "\n".join(notes) or None
    db.add(inv)
    db.flush()
    return inv


def post_supplier_invoice_doc(db: Session, p: Principal, inv_id: int) -> SupplierInvoice:
    inv = get_owned(db, SupplierInvoice, inv_id, p.company_id, lock=True)
    if inv.status == "posted":
        return inv  # idempotente
    if inv.status != "draft":
        raise Conflict("La factura no está en borrador")
    entry = post_supplier_invoice(db, inv, p.user_id)
    inv.status, inv.journal_entry_id, inv.posted_by_id = "posted", entry.id, p.user_id
    db.add(OpenItem(company_id=p.company_id, kind="payable", party_id=inv.supplier_id, document_type="supplier_invoice",
                    document_id=inv.id, document_number=inv.supplier_invoice_number, issue_date=inv.invoice_date,
                    due_date=inv.due_date, currency=inv.currency, exchange_rate=inv.exchange_rate,
                    original_amount=inv.payable_total, open_amount=inv.payable_total, journal_entry_id=entry.id))
    db.flush()
    return inv


# ---------------------------------------------------------------- consultas de apoyo
def last_purchase_price(db: Session, company_id: int, item_id: int) -> Decimal | None:
    return db.scalar(select(PurchaseOrderLine.unit_price).join(PurchaseOrder).where(
        PurchaseOrder.company_id == company_id, PurchaseOrderLine.item_id == item_id,
        PurchaseOrder.status.in_(("approved", "partially_received", "received", "closed")))
        .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc()).limit(1))


def price_history(db: Session, company_id: int, item_id: int) -> list[dict]:
    rows = db.execute(select(PurchaseOrder.order_date, PurchaseOrder.number, PurchaseOrder.supplier_id,
                             PurchaseOrder.currency, PurchaseOrderLine.unit_price, PurchaseOrderLine.quantity)
                      .join(PurchaseOrder).where(PurchaseOrder.company_id == company_id,
                                                 PurchaseOrderLine.item_id == item_id,
                                                 PurchaseOrder.status.notin_(("draft", "rejected", "cancelled")))
                      .order_by(PurchaseOrder.order_date)).all()
    return [dict(r._mapping) for r in rows]


def supplier_evaluation(db: Session, company_id: int, supplier_id: int, start: date, end: date) -> dict:
    """Evaluación objetiva: puntualidad de entregas, conformidad de calidad y estabilidad de precios."""
    from app.modules.quality.models import Inspection

    receipts = db.execute(select(GoodsReceipt.receipt_date, PurchaseOrder.expected_date)
                          .join(PurchaseOrder, PurchaseOrder.id == GoodsReceipt.purchase_order_id)
                          .where(GoodsReceipt.company_id == company_id, GoodsReceipt.supplier_id == supplier_id,
                                 GoodsReceipt.receipt_date.between(start, end))).all()
    on_time = sum(1 for r in receipts if r.expected_date is None or r.receipt_date <= r.expected_date)
    insp = db.execute(select(func.coalesce(func.sum(Inspection.quantity), 0),
                             func.coalesce(func.sum(Inspection.qty_accepted), 0))
                      .where(Inspection.company_id == company_id, Inspection.supplier_id == supplier_id,
                             Inspection.status.in_(("accepted", "rejected", "partial")),
                             func.date(Inspection.inspected_at).between(start, end))).one()
    delivery = Decimal(on_time) / len(receipts) * 100 if receipts else None
    quality = Decimal(insp[1]) / Decimal(insp[0]) * 100 if insp[0] else None
    parts = [v for v in (delivery, quality) if v is not None]
    return {
        "supplier_id": supplier_id, "period": [start, end], "receipts": len(receipts),
        "on_time_pct": round(delivery, 2) if delivery is not None else None,
        "quality_acceptance_pct": round(quality, 2) if quality is not None else None,
        "score": round(sum(parts) / len(parts), 2) if parts else None,
        "data_quality": "ok" if receipts else "sin_datos",
    }


def supplier_ranking(db: Session, company_id: int, start: date, end: date) -> list[dict]:
    from app.modules.masters.models import Party

    ids = db.scalars(select(GoodsReceipt.supplier_id).where(
        GoodsReceipt.company_id == company_id, GoodsReceipt.receipt_date >= start, GoodsReceipt.receipt_date <= end)
        .distinct()).all()
    names = dict(db.execute(select(Party.id, Party.legal_name).where(Party.id.in_(ids))).all()) if ids else {}
    rows = [{**supplier_evaluation(db, company_id, sid, start, end), "supplier_name": names.get(sid)} for sid in ids]
    return sorted(rows, key=lambda r: (r["score"] is None, -(r["score"] or 0)))


def requisition_from_replenishment(db: Session, p: Principal, site_id: int, needed_by: date | None,
                                   quantities: dict[int, Decimal] | None) -> PurchaseRequisition:
    """Solicitud de compra con los artículos bajo mínimo y su cantidad sugerida (hasta el máximo).

    El precio estimado es el último precio de compra aprobado; `quantities` permite ajustar o excluir artículos."""
    from app.modules.inventory.service import replenishment_alerts

    suggestions = {r["item_id"]: r for r in replenishment_alerts(db, p.company_id)}
    if quantities is not None:
        unknown = set(quantities) - set(suggestions)
        if unknown:
            raise BusinessRuleViolation("Hay artículos que no están bajo el mínimo", details={"items": sorted(unknown)})
    lines = []
    for item_id, row in suggestions.items():
        qty = Decimal(quantities[item_id]) if quantities is not None and item_id in quantities \
            else (None if quantities is not None else Decimal(row["suggested_order"]))
        if not qty or qty <= 0:
            continue
        price = last_purchase_price(db, p.company_id, item_id) or ZERO
        lines.append({"item_id": item_id, "quantity": qty, "estimated_unit_price": price,
                      "description": f"Reabastecimiento: disponible {row['available']}, mínimo {row['min_stock']}"})
    if not lines:
        raise BusinessRuleViolation("No hay artículos por reabastecer")
    req = create_requisition(db, p, {"site_id": site_id, "needed_by": needed_by, "lines": lines,
                                     "justification": "Reabastecimiento de artículos bajo el stock mínimo"})
    log_action(db, "create", "purchase_requisitions", req.id,
               f"Solicitud generada desde reabastecimiento ({len(lines)} artículos)")
    return req
