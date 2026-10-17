"""Facturación de ventas: borrador → emisión (numeración autorizada + contabilización + cartera) →
envío asíncrono al proveedor tecnológico mediante la bandeja de salida con reintentos e idempotencia.

Reglas:
- La emisión asigna número del rango autorizado vigente bajo bloqueo de fila (sin huecos ni duplicados).
- Una factura emitida no se modifica ni se anula: se corrige con nota crédito/débito.
- Un documento rechazado puede reenviarse con el mismo número tras corregir datos del tercero.
- Nunca se marca validez fiscal si el adaptador no es de producción y la respuesta no es verificable.
"""
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.config import get_settings
from app.core.crud import get_owned
from app.core.deps import Principal
from app.core.errors import BusinessRuleViolation, Conflict
from app.core.money import ZERO, money
from app.core.money import qty as q
from app.core.storage import save_attachment
from app.modules.accounting.models import OpenItem
from app.modules.accounting.posting import post_sales_invoice
from app.modules.einvoicing.models import (
    EInvoiceSubmission,
    NumberingRange,
    SalesInvoice,
    SalesInvoiceLine,
    SalesInvoiceTax,
)
from app.modules.logistics.models import DispatchLine, DispatchOrder
from app.modules.masters.models import Item, Party, PaymentTerm, Tax, UnitOfMeasure
from app.modules.masters.service import compute_taxes
from app.modules.org.models import Company, IntegrationEvent
from app.modules.sales.models import SalesOrder, SalesOrderLine
from integrations.einvoicing import get_adapter
from integrations.einvoicing.base import EDocument, ELine, EParty, ETax, TransientProviderError

CORRECTION_CODES_CO = {
    "credit_note": {"1": "Devolución parcial", "2": "Anulación de factura", "3": "Rebaja o descuento",
                    "4": "Ajuste de precio", "5": "Otros"},
    "debit_note": {"1": "Intereses", "2": "Gastos por cobrar", "3": "Cambio del valor", "4": "Otros"},
}


def _due(db: Session, customer: Party, issue: date, term_id: int | None) -> date:
    term = db.get(PaymentTerm, term_id or customer.payment_term_id) if (term_id or customer.payment_term_id) else None
    return issue + timedelta(days=term.days if term else 0)


def _fill_totals(db: Session, inv: SalesInvoice) -> None:
    calc = []
    for ln in inv.lines:
        gross = money(ln.quantity * ln.unit_price)
        ln.discount_amount = money(gross * ln.discount_pct / 100)
        ln.line_subtotal = gross - ln.discount_amount
        calc.append((ln.line_subtotal, db.get(Tax, ln.tax_id) if ln.tax_id else None))
    res = compute_taxes(calc, [], "sales")
    for ln, amount in zip(inv.lines, res.line_taxes, strict=False):
        ln.tax_amount = amount
    inv.taxes = [SalesInvoiceTax(tax_id=t.tax.id, base=t.base, rate=t.tax.rate, amount=t.amount) for t in res.taxes]
    inv.subtotal = res.subtotal
    inv.discount_total = sum((ln.discount_amount for ln in inv.lines), ZERO)
    inv.tax_total, inv.total = res.tax_total, res.total


def create_from_dispatch(db: Session, p: Principal, dispatch_id: int, issue_date: date | None = None) -> SalesInvoice:
    d = get_owned(db, DispatchOrder, dispatch_id, p.company_id, lock=True)
    if d.status not in ("shipped", "delivered", "partially_delivered"):
        raise BusinessRuleViolation("Solo se factura mercancía despachada")
    so = db.get(SalesOrder, d.sales_order_id)
    customer = db.get(Party, so.customer_id)
    issue = issue_date or date.today()
    inv = SalesInvoice(company_id=p.company_id, site_id=so.site_id, customer_id=so.customer_id, sales_order_id=so.id,
                       dispatch_id=d.id, issue_date=issue, due_date=_due(db, customer, issue, so.payment_term_id),
                       payment_form="cash" if _due(db, customer, issue, so.payment_term_id) == issue else "credit",
                       currency=so.currency, exchange_rate=so.exchange_rate,
                       idempotency_key=f"dispatch:{d.id}:{datetime.now(UTC).timestamp()}", created_by_id=p.user_id)
    n = 0
    for dl in d.lines:
        pending = dl.qty_shipped - dl.qty_returned - dl.qty_invoiced
        if pending <= 0:
            continue
        sol = db.get(SalesOrderLine, dl.so_line_id)
        item = db.get(Item, dl.item_id)
        n += 1
        inv.lines.append(SalesInvoiceLine(line_no=n, item_id=item.id, description=sol.description or item.name,
                                          quantity=pending, uom_code=db.get(UnitOfMeasure, item.base_uom_id).code,
                                          unit_price=sol.unit_price, discount_pct=sol.discount_pct, tax_id=sol.tax_id,
                                          so_line_id=sol.id, dispatch_line_id=dl.id))
    if not inv.lines:
        raise BusinessRuleViolation("El despacho no tiene cantidades pendientes de facturar")
    _fill_totals(db, inv)
    db.add(inv)
    db.flush()
    return inv


def create_note(db: Session, p: Principal, invoice_id: int, data: dict) -> SalesInvoice:
    """Nota crédito o débito sobre una factura emitida."""
    orig = get_owned(db, SalesInvoice, invoice_id, p.company_id)
    if orig.doc_type != "invoice" or orig.status != "issued":
        raise BusinessRuleViolation("Las notas solo se generan sobre facturas emitidas")
    doc_type = data["doc_type"]
    codes = CORRECTION_CODES_CO[doc_type]
    if p.company.country_code == "CO" and data["correction_code"] not in codes:
        raise BusinessRuleViolation(f"Código de corrección inválido; opciones: {codes}")
    orig_lines = {ln.id: ln for ln in orig.lines}
    issue = data.get("issue_date") or date.today()
    note = SalesInvoice(company_id=p.company_id, doc_type=doc_type, site_id=orig.site_id, customer_id=orig.customer_id,
                        sales_order_id=orig.sales_order_id, dispatch_id=orig.dispatch_id, reference_invoice_id=orig.id,
                        correction_code=data["correction_code"], correction_reason=data["reason"], issue_date=issue,
                        due_date=issue if doc_type == "credit_note" else issue + (orig.due_date - orig.issue_date),
                        payment_form=orig.payment_form, currency=orig.currency, exchange_rate=orig.exchange_rate,
                        idempotency_key=f"note:{orig.id}:{datetime.now(UTC).timestamp()}", created_by_id=p.user_id)
    credited = _credited_by_line(db, orig.id) if doc_type == "credit_note" else {}
    for i, x in enumerate(data["lines"], start=1):
        ol = orig_lines.get(x["invoice_line_id"])
        if ol is None:
            raise BusinessRuleViolation("La línea no pertenece a la factura")
        quantity = q(x.get("quantity") or ol.quantity)
        price = Decimal(x["unit_price"]) if x.get("unit_price") is not None else ol.unit_price
        if doc_type == "credit_note":
            already = credited.get(_line_key(ol), ZERO)
            if quantity * price > ol.quantity * ol.unit_price - already + Decimal("0.01"):
                raise BusinessRuleViolation(f"La nota crédito excede el valor pendiente de la línea {ol.line_no}")
        note.lines.append(SalesInvoiceLine(line_no=i, item_id=ol.item_id, description=x.get("description") or ol.description,
                                           quantity=quantity, uom_code=ol.uom_code, unit_price=price,
                                           discount_pct=ol.discount_pct, tax_id=ol.tax_id, so_line_id=ol.so_line_id,
                                           dispatch_line_id=ol.dispatch_line_id))
    _fill_totals(db, note)
    if doc_type == "credit_note":
        oi = db.scalar(select(OpenItem).where(OpenItem.company_id == p.company_id, OpenItem.document_id == orig.id,
                                              OpenItem.document_type == "invoice", OpenItem.kind == "receivable"))
        if oi is None or note.total > oi.open_amount:
            raise BusinessRuleViolation(
                "La nota crédito supera el saldo pendiente de la factura; si ya fue pagada, gestione la devolución "
                "de dinero (pendiente en esta versión)")
    db.add(note)
    db.flush()
    return note


def _line_key(ln) -> tuple:
    return (ln.dispatch_line_id, ln.so_line_id, ln.item_id)


def _credited_by_line(db: Session, invoice_id: int) -> dict[tuple, Decimal]:
    """Valor ya acreditado por notas crédito emitidas, por renglón de la factura origen."""
    notes = db.scalars(select(SalesInvoice).where(SalesInvoice.reference_invoice_id == invoice_id,
                                                  SalesInvoice.doc_type == "credit_note",
                                                  SalesInvoice.status == "issued")).all()
    out: dict[tuple, Decimal] = {}
    for n in notes:
        for ln in n.lines:
            out[_line_key(ln)] = out.get(_line_key(ln), ZERO) + ln.quantity * ln.unit_price
    return out


def _take_number(db: Session, inv: SalesInvoice) -> NumberingRange:
    rng = db.scalar(select(NumberingRange).where(
        NumberingRange.company_id == inv.company_id, NumberingRange.doc_type == inv.doc_type,
        NumberingRange.is_active.is_(True), NumberingRange.valid_from <= inv.issue_date,
        NumberingRange.valid_to >= inv.issue_date, NumberingRange.next_number <= NumberingRange.range_to)
        .order_by(NumberingRange.valid_to).with_for_update())
    if rng is None:
        raise BusinessRuleViolation(f"No hay numeración autorizada vigente para '{inv.doc_type}' al {inv.issue_date}")
    inv.prefix, inv.number = rng.prefix, rng.next_number
    inv.full_number = f"{rng.prefix}{rng.next_number}"
    inv.numbering_range_id = rng.id
    rng.next_number += 1
    return rng


def issue(db: Session, p: Principal, invoice_id: int) -> SalesInvoice:
    inv = get_owned(db, SalesInvoice, invoice_id, p.company_id, lock=True)
    if inv.status == "issued":
        return inv  # idempotente
    if inv.status != "draft":
        raise Conflict("Solo se emiten documentos en borrador")
    customer = db.get(Party, inv.customer_id)
    if not customer.is_active:
        raise BusinessRuleViolation("El cliente está inactivo")
    _fill_totals(db, inv)
    if inv.total <= 0:
        raise BusinessRuleViolation("El documento debe tener valor positivo")
    _take_number(db, inv)
    inv.status, inv.edoc_status, inv.issued_at = "issued", "pending", datetime.now(UTC)
    entry = post_sales_invoice(db, inv, p.user_id)
    inv.journal_entry_id = entry.id
    if inv.doc_type in ("invoice", "debit_note"):
        db.add(OpenItem(company_id=inv.company_id, kind="receivable", party_id=inv.customer_id, document_type=inv.doc_type,
                        document_id=inv.id, document_number=inv.full_number, issue_date=inv.issue_date,
                        due_date=inv.due_date, currency=inv.currency, exchange_rate=inv.exchange_rate,
                        original_amount=inv.total, open_amount=inv.total, journal_entry_id=entry.id))
    else:
        oi = db.scalar(select(OpenItem).where(OpenItem.company_id == inv.company_id, OpenItem.kind == "receivable",
                                              OpenItem.document_type == "invoice",
                                              OpenItem.document_id == inv.reference_invoice_id).with_for_update())
        if oi is None or inv.total > oi.open_amount:
            raise BusinessRuleViolation("La nota crédito supera el saldo pendiente de la factura")
        oi.open_amount -= inv.total
        oi.status = "paid" if oi.open_amount == 0 else "partial"
    if inv.doc_type == "invoice":
        # Las notas no alteran cantidades facturadas: las devoluciones físicas se controlan con qty_returned.
        for ln in inv.lines:
            if ln.so_line_id:
                db.get(SalesOrderLine, ln.so_line_id).qty_invoiced += ln.quantity
            if ln.dispatch_line_id:
                dl = db.get(DispatchLine, ln.dispatch_line_id)
                dl.qty_invoiced += ln.quantity
                if dl.qty_invoiced > dl.qty_shipped - dl.qty_returned:
                    raise BusinessRuleViolation("Se está facturando más de lo despachado (neto de devoluciones)")
    enqueue_submission(db, inv)
    log_action(db, "post", "sales_invoices", inv.id, f"Emitido {inv.full_number}")
    return inv


def enqueue_submission(db: Session, inv: SalesInvoice) -> IntegrationEvent:
    attempt = db.scalar(select(func.count()).select_from(IntegrationEvent).where(
        IntegrationEvent.event_type == "einvoice.submit",
        IntegrationEvent.idempotency_key.like(f"einvoice:{inv.id}:%"))) + 1
    ev = IntegrationEvent(company_id=inv.company_id, event_type="einvoice.submit", payload={"invoice_id": inv.id},
                          idempotency_key=f"einvoice:{inv.id}:{attempt}")
    db.add(ev)
    db.flush()
    return ev


def resend(db: Session, p: Principal, invoice_id: int) -> SalesInvoice:
    inv = get_owned(db, SalesInvoice, invoice_id, p.company_id, lock=True)
    if inv.edoc_status not in ("rejected", "error"):
        raise BusinessRuleViolation("Solo se reenvían documentos rechazados o con error")
    inv.edoc_status = "pending"
    enqueue_submission(db, inv)
    log_action(db, "post", "sales_invoices", inv.id, "Reenvío al proveedor tecnológico")
    return inv


def cancel_draft(db: Session, p: Principal, invoice_id: int, reason: str) -> SalesInvoice:
    inv = get_owned(db, SalesInvoice, invoice_id, p.company_id, lock=True)
    if inv.status != "draft":
        raise BusinessRuleViolation("Un documento emitido no se anula: emita una nota crédito")
    inv.status = "cancelled"
    log_action(db, "void", "sales_invoices", inv.id, reason)
    return inv


# ---------------------------------------------------------------- integración con el proveedor
def adapter_name_for(company: Company) -> str:
    s = get_settings()
    return s.einvoice_adapter_co if company.country_code == "CO" else s.einvoice_adapter_ve


def to_edocument(db: Session, inv: SalesInvoice) -> EDocument:
    company = db.get(Company, inv.company_id)
    cust = db.get(Party, inv.customer_id)
    rng = db.get(NumberingRange, inv.numbering_range_id)
    issuer = EParty(id_type="NIT" if company.country_code == "CO" else "RIF", tax_id=company.tax_id,
                    check_digit=company.tax_id_check_digit, legal_name=company.legal_name, email=company.email,
                    address=company.address, city=company.city, city_code=company.city_code,
                    country_code=company.country_code, fiscal_regime=company.fiscal_regime)
    customer = EParty(id_type=cust.id_type, tax_id=cust.tax_id, check_digit=cust.check_digit,
                      legal_name=cust.legal_name, email=cust.email, address=cust.address, city=cust.city,
                      city_code=cust.city_code, country_code=cust.country_code, fiscal_regime=cust.fiscal_regime)
    taxes = {}
    for t in inv.taxes:
        tax = db.get(Tax, t.tax_id)
        taxes[t.tax_id] = ETax(code=tax.electronic_code or tax.code, name=tax.name, rate=t.rate, base=t.base,
                               amount=t.amount)
    lines = []
    for ln in inv.lines:
        tax = db.get(Tax, ln.tax_id) if ln.tax_id else None
        lines.append(ELine(line_no=ln.line_no, sku=db.get(Item, ln.item_id).sku, description=ln.description,
                           quantity=ln.quantity, uom_code=ln.uom_code, unit_price=ln.unit_price,
                           discount_amount=ln.discount_amount, line_subtotal=ln.line_subtotal,
                           tax=ETax(code=tax.electronic_code or tax.code, name=tax.name, rate=tax.rate,
                                    base=ln.line_subtotal, amount=ln.tax_amount) if tax else None))
    ref = db.get(SalesInvoice, inv.reference_invoice_id) if inv.reference_invoice_id else None
    issued = inv.issued_at or datetime.now(UTC)
    return EDocument(
        internal_id=inv.id, doc_type=inv.doc_type, prefix=inv.prefix, number=inv.number, issue_date=inv.issue_date,
        issue_time=issued.astimezone().time().replace(microsecond=0), due_date=inv.due_date, currency=inv.currency,
        exchange_rate=inv.exchange_rate, functional_currency=company.functional_currency, issuer=issuer,
        customer=customer, lines=lines, taxes=list(taxes.values()), subtotal=inv.subtotal,
        discount_total=inv.discount_total, tax_total=inv.tax_total, total=inv.total, payment_form=inv.payment_form,
        authorization_number=rng.authorization_number, authorization_range=(rng.range_from, rng.range_to),
        authorization_valid=(rng.valid_from, rng.valid_to), technical_key=rng.technical_key,
        reference_uid=ref.fiscal_uid if ref else None, reference_number=ref.full_number if ref else None,
        reference_date=ref.issue_date if ref else None, correction_code=inv.correction_code,
        correction_reason=inv.correction_reason, notes=inv.notes,
    )


def process_submission(db: Session, ev: IntegrationEvent) -> None:
    """Ejecuta el envío de un evento. Lanza TransientProviderError para que el despachador reintente."""
    inv = db.get(SalesInvoice, ev.payload["invoice_id"], with_for_update=True)
    if inv.edoc_status == "accepted":
        return  # ya aceptado: el reintento no reenvía (idempotencia)
    company = db.get(Company, inv.company_id)
    name = adapter_name_for(company)
    adapter = get_adapter(name)
    doc = to_edocument(db, inv)
    attempt = (db.scalar(select(func.max(EInvoiceSubmission.attempt_no)).where(
        EInvoiceSubmission.invoice_id == inv.id)) or 0) + 1
    result = adapter.submit(doc)  # TransientProviderError → reintento gestionado por la bandeja de salida
    att = None
    if result.document:
        att = save_attachment(db, company_id=inv.company_id, entity_type="sales_invoices", entity_id=inv.id,
                              filename=result.document_filename or f"{inv.full_number}.xml",
                              content_type="application/json" if (result.document_filename or "").endswith(".json")
                              else "application/xml", data=result.document, user_id=None,
                              description=f"Documento electrónico ({adapter.environment})")
    db.add(EInvoiceSubmission(invoice_id=inv.id, attempt_no=attempt, operation="submit", adapter=name,
                              environment=result.environment, document_sha256=att.sha256 if att else None,
                              document_attachment_id=att.id if att else None, result_status=result.status,
                              provider_code=result.provider_code, provider_message=result.message,
                              provider_tracking_id=result.tracking_id))
    inv.edoc_status = result.status
    inv.edoc_environment, inv.edoc_adapter = result.environment, name
    inv.edoc_message = result.message
    if result.fiscal_uid:
        inv.fiscal_uid = result.fiscal_uid
    if result.control_number:
        inv.control_number = result.control_number
    # La validez fiscal solo se reconoce con respuesta de producción explícita del proveedor.
    inv.legal_validity = bool(result.legal_validity and result.environment == "production"
                              and result.status == "accepted")
    db.flush()


def submission_failed(db: Session, ev: IntegrationEvent, exc: Exception) -> None:
    """Registra un intento fallido (error temporal o inesperado) sin alterar la numeración ni la contabilidad."""
    inv = db.get(SalesInvoice, ev.payload["invoice_id"], with_for_update=True)
    attempt = (db.scalar(select(func.max(EInvoiceSubmission.attempt_no)).where(
        EInvoiceSubmission.invoice_id == inv.id)) or 0) + 1
    name = adapter_name_for(db.get(Company, inv.company_id))
    db.add(EInvoiceSubmission(invoice_id=inv.id, attempt_no=attempt, operation="submit", adapter=name,
                              environment="unknown", result_status="error", provider_message=str(exc)[:2000]))
    inv.edoc_status = "error"
    inv.edoc_message = f"{'Error temporal' if isinstance(exc, TransientProviderError) else 'Error'}: {exc}"[:2000]


def reconciliation(db: Session, company_id: int, start: date, end: date) -> dict:
    """Conciliación factura ↔ cartera ↔ contabilidad para un rango de fechas."""
    from app.modules.accounting.models import JournalEntry

    invs = db.scalars(select(SalesInvoice).where(SalesInvoice.company_id == company_id,
                                                 SalesInvoice.status == "issued",
                                                 SalesInvoice.issue_date.between(start, end))).all()
    issues = []
    for inv in invs:
        je = db.get(JournalEntry, inv.journal_entry_id) if inv.journal_entry_id else None
        if je is None or je.status != "posted":
            issues.append({"invoice": inv.full_number, "problem": "sin asiento contable vigente"})
        elif je.total_debit != je.total_credit:
            issues.append({"invoice": inv.full_number, "problem": "asiento inconsistente"})
        if inv.doc_type != "credit_note":
            oi = db.scalar(select(OpenItem).where(OpenItem.company_id == company_id, OpenItem.document_id == inv.id,
                                                  OpenItem.document_type == inv.doc_type))
            if oi is None:
                issues.append({"invoice": inv.full_number, "problem": "sin partida en cartera"})
            elif oi.original_amount != inv.total:
                issues.append({"invoice": inv.full_number, "problem": "valor en cartera distinto al facturado"})
        if inv.edoc_status != "accepted":
            issues.append({"invoice": inv.full_number, "problem": f"documento electrónico en estado {inv.edoc_status}"})
    return {"period": [start, end], "documents": len(invs), "issues": issues, "ok": not issues}
