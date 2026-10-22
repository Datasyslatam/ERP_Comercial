"""Documentos comerciales en PDF y su envío por correo con cola de reintentos y bitácora.

Documentos: cotización, pedido de venta, orden de compra y factura / nota electrónica. Cada uno se envía solo
en los estados en que tiene sentido para el negocio (p. ej. una OC aprobada, una factura emitida).
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import Principal
from app.core.errors import BusinessRuleViolation, Forbidden, NotFound
from app.modules.accounting.models import BankAccount, OpenItem, Payment
from app.modules.documents import mailer
from app.modules.documents.models import DocumentEmail
from app.modules.documents.pdf import DocData, Line, fdate, money, render
from app.modules.documents.words import amount_in_words
from app.modules.einvoicing.models import NumberingRange, SalesInvoice
from app.modules.inventory.models import Warehouse
from app.modules.masters.models import Item, Party, PaymentTerm, Tax, UnitOfMeasure
from app.modules.org.models import Company, IntegrationEvent, Site
from app.modules.purchasing.models import PurchaseOrder
from app.modules.sales.models import SalesOrder, SalesQuote


@dataclass(frozen=True)
class DocType:
    model: type
    read_perm: str
    send_perm: str
    title: str
    sendable: tuple[str, ...]  # estados en que el documento puede enviarse


DOCS: dict[str, DocType] = {
    "sales_quote": DocType(SalesQuote, "sales.quote.read", "sales.quote.create", "Cotización", ("draft", "sent", "accepted")),
    "sales_order": DocType(SalesOrder, "sales.order.read", "sales.order.create", "Pedido de venta",
                           ("confirmed", "partially_dispatched", "dispatched", "closed")),
    "purchase_order": DocType(PurchaseOrder, "purchasing.order.read", "purchasing.order.create", "Orden de compra",
                              ("approved", "partially_received", "received", "closed")),
    "sales_invoice": DocType(SalesInvoice, "einvoicing.invoice.read", "einvoicing.invoice.create", "Factura electrónica",
                             ("issued",)),
    "payment": DocType(Payment, "accounting.payments.read", "accounting.payments.create", "Comprobante de pago",
                       ("posted",)),
}
PAYMENT_TITLES = {"receipt": "Recibo de caja", "disbursement": "Comprobante de egreso"}
DOC_LABELS = {"invoice": "Factura de venta", "credit_note": "Nota crédito", "debit_note": "Nota débito",
              "supplier_invoice": "Factura de proveedor", "opening": "Saldo inicial"}
METHODS = {"transfer": "Transferencia", "cash": "Efectivo", "check": "Cheque", "card": "Tarjeta",
           "mobile_payment": "Pago móvil", "other": "Otro"}
NOTE_TITLES = {"invoice": "Factura electrónica de venta", "credit_note": "Nota crédito", "debit_note": "Nota débito"}
ID_LABELS = {"NIT": "NIT", "RIF": "RIF", "CC": "C.C.", "CE": "C.E.", "CI": "C.I.", "PAS": "Pasaporte", "EXT": "Doc. extranjero"}


def _get(db: Session, p: Principal, doc_type: str, doc_id: int, perm: str = "read"):
    meta = DOCS.get(doc_type)
    if meta is None:
        raise NotFound("Tipo de documento no soportado")
    needed = meta.read_perm if perm == "read" else meta.send_perm
    if not p.has(needed):
        raise Forbidden("Permiso insuficiente", details={"missing": [needed]})
    obj = db.get(meta.model, doc_id)
    if obj is None or obj.company_id != p.company_id:
        raise NotFound("Documento no encontrado")
    site_id = getattr(obj, "site_id", None)
    if site_id is not None:
        p.ensure_site(site_id)
    return meta, obj


def number_of(doc_type: str, obj) -> str:
    if doc_type == "sales_invoice":
        return obj.full_number or f"Borrador {obj.id}"
    return obj.number


def _tax_id(id_type: str | None, tax_id: str | None, dv: str | None) -> str:
    if not tax_id:
        return ""
    return f"{ID_LABELS.get(id_type or '', id_type or '')} {tax_id}{f'-{dv}' if dv else ''}".strip()


def _company_block(c: Company) -> dict:
    contact = " · ".join(x for x in (c.phone, c.email) if x)
    return {"name": c.trade_name or c.legal_name,
            "tax_id": " · ".join(x for x in (c.legal_name if c.trade_name else None,
                                             _tax_id("NIT" if c.country_code == "CO" else "RIF", c.tax_id,
                                                     c.tax_id_check_digit)) if x),
            "address": ", ".join(x for x in (c.address, c.city) if x), "contact": contact}


def _party_block(party: Party) -> dict:
    return {"name": party.legal_name, "tax_id": _tax_id(party.id_type, party.tax_id, party.check_digit),
            "address": ", ".join(x for x in (party.address, party.city) if x),
            "contact": " · ".join(x for x in (party.phone, party.email) if x)}


def _items(db: Session, ids: set[int]) -> dict[int, tuple[Item, str]]:
    if not ids:
        return {}
    items = {i.id: i for i in db.scalars(select(Item).where(Item.id.in_(ids)))}
    uoms = dict(db.execute(select(UnitOfMeasure.id, UnitOfMeasure.code)).all())
    return {i: (it, uoms.get(it.base_uom_id, "")) for i, it in items.items()}


def _taxes_summary(db: Session, lines, currency: str) -> list[tuple[str, str, bool]]:
    """Impuestos por tarifa a partir de las líneas (cotización, pedido y OC no guardan el desglose)."""
    by_tax: dict[int, Decimal] = {}
    for base, tax_id in lines:
        if tax_id:
            by_tax[tax_id] = by_tax.get(tax_id, Decimal("0")) + base
    out = []
    taxes = {t.id: t for t in db.scalars(select(Tax).where(Tax.id.in_(by_tax)))} if by_tax else {}
    for tax_id, base in by_tax.items():
        t = taxes[tax_id]
        if t.kind and "withholding" in t.kind:
            continue
        out.append((f"{t.name}", money(base * t.rate / 100), False))
    return out


def _term_name(db: Session, term_id: int | None) -> str | None:
    if not term_id:
        return None
    t = db.get(PaymentTerm, term_id)
    return t.name if t else None


def payment_data(db: Session, pay: Payment) -> DocData:
    """Recibo de caja (recaudo de cliente) o comprobante de egreso (pago a proveedor) con sus retenciones."""
    company = db.get(Company, pay.company_id)
    party = db.get(Party, pay.party_id)
    bank = db.get(BankAccount, pay.bank_account_id)
    receipt = pay.kind == "receipt"
    rows, applied = [], Decimal("0")
    for a in pay.allocations:
        item = db.get(OpenItem, a.open_item_id)
        rows.append([item.document_number, f"{DOC_LABELS.get(item.document_type, item.document_type)} · emitida "
                     f"{fdate(item.issue_date)}", fdate(item.due_date), money(item.original_amount), money(a.amount)])
        applied += a.amount
    totals = [("Total aplicado a documentos", money(applied), False)]
    if pay.withholding_amount:
        totals.append(("Retenciones", f"-{money(pay.withholding_amount)}", False))
    if pay.igtf_amount:
        totals.append(("IGTF", money(pay.igtf_amount), False))
    totals.append((f"{'Valor recibido' if receipt else 'Valor pagado'} {pay.currency}", money(pay.amount), True))
    fiscal = []
    for w in pay.withholdings:
        tax = db.get(Tax, w.tax_id)
        rate = "" if "%" in tax.name else f" ({money(tax.rate)} %)"
        text = f"{tax.name}{rate} sobre base {money(w.base)}: {money(w.amount)}"
        if w.certificate_number:
            text += f" · comprobante de retención {w.certificate_number}"
        fiscal.append(("Retención practicada por el cliente" if receipt else "Retención practicada", text))
    fields = [("Fecha", fdate(pay.payment_date)), ("Medio de pago", METHODS.get(pay.method, pay.method)),
              ("Referencia", pay.reference or "-"), ("Cuenta bancaria", bank.name if bank else "-"),
              ("Moneda", pay.currency)]
    if pay.currency != company.functional_currency:
        fields.append(("Tasa de cambio", money(pay.exchange_rate, 4)))
    return DocData(
        title=PAYMENT_TITLES[pay.kind], number=pay.number, company=_company_block(company),
        party_label="Recibido de" if receipt else "Pagado a", party=_party_block(party), fields=fields, lines=[],
        columns=[("Documento", 30, "L"), ("Concepto", 77.9, "L"), ("Vence", 22, "C"), ("Valor documento", 28, "R"),
                 ("Aplicado", 30, "R")],
        rows=rows, totals=totals, currency=pay.currency, fiscal=fiscal,
        notes=f"Son: {amount_in_words(pay.amount, pay.currency)}",
        notice="ANULADO" if pay.status == "voided" else None,
        terms=None if receipt else ("Recibí conforme: ______________________________\n"
                                    "C.C./NIT: __________________   Fecha: ____________"))


def document_data(db: Session, doc_type: str, obj) -> DocData:
    if doc_type == "payment":
        return payment_data(db, obj)
    company = db.get(Company, obj.company_id)
    party_id = getattr(obj, "customer_id", None) or getattr(obj, "supplier_id", None)
    party = db.get(Party, party_id)
    items = _items(db, {ln.item_id for ln in obj.lines})
    currency = obj.currency

    def line(ln, subtotal: Decimal | None = None) -> Line:
        item, uom = items.get(ln.item_id, (None, ""))
        gross = Decimal(ln.quantity) * Decimal(ln.unit_price)
        disc = Decimal(getattr(ln, "discount_pct", 0) or 0)
        if subtotal is None:
            subtotal = (gross * (1 - disc / 100)).quantize(Decimal("0.01"))
        return Line(code=item.sku if item else "", description=getattr(ln, "description", None) or (item.name if item else ""),
                    quantity=ln.quantity, uom=getattr(ln, "uom_code", None) or uom, unit_price=ln.unit_price,
                    discount_pct=disc, subtotal=subtotal)

    lines = [line(ln, getattr(ln, "line_subtotal", None) if doc_type == "sales_invoice" else None) for ln in obj.lines]
    totals = [("Subtotal", money(obj.subtotal), False)]
    if doc_type == "sales_invoice":
        tax_ids = {x.tax_id for x in obj.taxes}
        names = dict(db.execute(select(Tax.id, Tax.name).where(Tax.id.in_(tax_ids))).all()) if tax_ids else {}
        if obj.discount_total:
            totals.append(("Descuentos", money(obj.discount_total), False))
        for t in obj.taxes:
            name = names.get(t.tax_id, "Impuesto")
            totals.append((name if "%" in name else f"{name} ({money(t.rate, 2)} %)", money(t.amount), False))
    else:
        bases = [(ln_obj.subtotal, src.tax_id) for ln_obj, src in zip(lines, obj.lines, strict=True)]
        totals += _taxes_summary(db, bases, currency)
        if not any(label != "Subtotal" for label, _, _ in totals) and obj.tax_total:
            totals.append(("Impuestos", money(obj.tax_total), False))
    totals.append((f"Total {currency}", money(obj.total), True))

    meta = DOCS[doc_type]
    common = dict(company=_company_block(company), party=_party_block(party), lines=lines, totals=totals,
                  currency=currency, number=number_of(doc_type, obj))
    term = _term_name(db, getattr(obj, "payment_term_id", None))
    if doc_type == "sales_quote":
        return DocData(title=meta.title, party_label="Cliente", notes=obj.notes,
                       fields=[("Fecha", fdate(obj.quote_date)), ("Vigente hasta", fdate(obj.valid_until)),
                               ("Moneda", currency), ("Forma de pago", term or "-"),
                               ("Atención", obj.contact_name or "-")],
                       terms=f"Precios sujetos a disponibilidad de inventario. Oferta válida hasta el {fdate(obj.valid_until)}.",
                       **common)
    if doc_type == "sales_order":
        wh = db.get(Warehouse, obj.warehouse_id)
        return DocData(title=meta.title, party_label="Cliente", notes=obj.notes,
                       fields=[("Fecha", fdate(obj.order_date)), ("Entrega prometida", fdate(obj.promised_date)),
                               ("Moneda", currency), ("Forma de pago", term or "-"),
                               ("Despacha desde", wh.name if wh else "-"), ("Entregar en", obj.delivery_address or "-")],
                       **common)
    if doc_type == "purchase_order":
        wh = db.get(Warehouse, obj.warehouse_id)
        site = db.get(Site, obj.site_id)
        parts = (wh.name if wh else None, site.address if site else None, site.city if site else None)
        delivery = ", ".join(x for x in parts if x)
        return DocData(title=meta.title, party_label="Proveedor", notes=obj.notes,
                       fields=[("Fecha", fdate(obj.order_date)), ("Entrega esperada", fdate(obj.expected_date)),
                               ("Moneda", currency), ("Forma de pago", term or "-"), ("Lugar de entrega", delivery or "-")],
                       terms="Cite el número de esta orden en su remisión y factura. "
                             "Solo se recibe lo pactado en cantidad y precio.",
                       **common)
    # Factura o nota electrónica
    fiscal = []
    if obj.fiscal_uid:
        fiscal.append(("CUFE / CUDE" if company.country_code == "CO" else "Identificador", obj.fiscal_uid))
    if obj.control_number:
        fiscal.append(("Número de control", obj.control_number))
    if obj.numbering_range_id:
        rng = db.get(NumberingRange, obj.numbering_range_id)
        if rng:
            fiscal.append(("Autorización de numeración",
                           f"{rng.authorization_number} del {fdate(rng.valid_from)} al {fdate(rng.valid_to)}, "
                           f"rango {rng.prefix or ''}{rng.range_from} a {rng.prefix or ''}{rng.range_to}"))
    if obj.reference_invoice_id:
        ref = db.get(SalesInvoice, obj.reference_invoice_id)
        fiscal.append(("Documento referenciado", f"{ref.full_number if ref else obj.reference_invoice_id}"
                       + (f" · {obj.correction_reason}" if obj.correction_reason else "")))
    notice = None if obj.legal_validity else ("Documento de PRUEBAS: sin validez fiscal" if obj.edoc_environment == "sandbox"
                                              else "Pendiente de validación por la autoridad tributaria")
    return DocData(title=NOTE_TITLES.get(obj.doc_type, meta.title), party_label="Adquiriente",
                   fields=[("Fecha de emisión", fdate(obj.issue_date)), ("Vencimiento", fdate(obj.due_date)),
                           ("Forma de pago", "Contado" if obj.payment_form == "cash" else "Crédito"), ("Moneda", currency),
                           ("Tasa de cambio", money(obj.exchange_rate, 4) if currency != company.functional_currency else "-")],
                   fiscal=fiscal, notice=notice, **common)


def pdf_for(db: Session, p: Principal, doc_type: str, doc_id: int) -> tuple[str, bytes]:
    _, obj = _get(db, p, doc_type, doc_id)
    data = document_data(db, doc_type, obj)
    return filename_for(data), render(data)


def filename_for(data: DocData) -> str:
    """Nombre ASCII (cabeceras HTTP y clientes de correo antiguos): Cotizacion_CT-000001.pdf"""
    raw = unicodedata.normalize("NFKD", f"{data.title}_{data.number}").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_") + ".pdf"


# ---------------------------------------------------------------- correo
def _split(addresses: list[str] | None) -> list[str]:
    return [a.strip() for a in (addresses or []) if a and a.strip()]


def default_message(db: Session, doc_type: str, obj) -> dict:
    company = db.get(Company, obj.company_id)
    party = db.get(Party, getattr(obj, "customer_id", None) or getattr(obj, "supplier_id", None)
                   or getattr(obj, "party_id", None))
    name = company.trade_name or company.legal_name
    number = number_of(doc_type, obj)
    title = DOCS[doc_type].title
    if doc_type == "sales_invoice":
        title = NOTE_TITLES.get(obj.doc_type, title)
    elif doc_type == "payment":
        title = PAYMENT_TITLES[obj.kind]
    intro = {
        "sales_quote": f"adjuntamos la cotización {number}, vigente hasta el {fdate(getattr(obj, 'valid_until', None))}.",
        "sales_order": f"adjuntamos la confirmación de su pedido {number}.",
        "purchase_order": f"adjuntamos la orden de compra {number}. Por favor confirme la fecha de entrega y cite "
                          "este número en su remisión y factura.",
        "sales_invoice": f"adjuntamos la representación gráfica del documento {number}.",
        "payment": (f"adjuntamos el recibo de caja {number} por el pago recibido. Gracias por su pago."
                    if getattr(obj, "kind", "") == "receipt" else
                    f"adjuntamos el comprobante de egreso {number} con el detalle de los documentos pagados"
                    " y, si aplica, los comprobantes de retención."),
    }[doc_type]
    return {"to": [party.email] if party and party.email else [],
            "subject": f"{title} {number} · {name}",
            "body": (f"Señores {party.legal_name if party else ''}:\n\nCordial saludo; {intro}\n\n"
                     f"Quedamos atentos a cualquier inquietud.\n\n{name}")}


def queue_email(db: Session, p: Principal, doc_type: str, doc_id: int, to: list[str], cc: list[str] | None,
                subject: str | None, body: str | None) -> DocumentEmail:
    meta, obj = _get(db, p, doc_type, doc_id, perm="send")
    status = obj.status
    if doc_type == "sales_quote":
        from app.modules.sales.service import quote_status

        status = quote_status(obj)
        if status == "expired":
            raise BusinessRuleViolation("La cotización está vencida; emita una nueva antes de enviarla")
    if status not in meta.sendable:
        raise BusinessRuleViolation(f"No se envía un documento en estado «{status}»",
                                    details={"allowed": list(meta.sendable)})
    to, cc = _split(to), _split(cc)
    if not to:
        raise BusinessRuleViolation("Indique al menos un destinatario")
    if len(to) + len(cc) > 10:
        raise BusinessRuleViolation("Máximo 10 destinatarios por envío")
    mailer.ensure_configured()
    defaults = default_message(db, doc_type, obj)
    number = number_of(doc_type, obj)
    em = DocumentEmail(company_id=p.company_id, doc_type=doc_type, doc_id=obj.id, doc_number=number,
                       to_addresses=", ".join(to), cc_addresses=", ".join(cc) or None,
                       subject=(subject or defaults["subject"])[:255], body=body or defaults["body"],
                       created_by_id=p.user_id)
    db.add(em)
    db.flush()
    db.add(IntegrationEvent(company_id=p.company_id, event_type="document.email", payload={"email_id": em.id},
                            idempotency_key=f"document_email:{em.id}", max_attempts=5))
    if doc_type == "sales_quote" and obj.status == "draft":
        obj.status = "sent"  # enviarla al cliente es lo que la hace "enviada"
    log_action(db, "send", obj.__tablename__, obj.id, f"Envío por correo de {number} a {em.to_addresses}")
    return em


def process_email(db: Session, ev: IntegrationEvent) -> None:
    """Manejador del worker: genera el PDF vigente y entrega el correo."""
    em = db.get(DocumentEmail, ev.payload["email_id"], with_for_update=True)
    if em is None or em.status == "sent":
        return
    em.attempts += 1
    obj = db.get(DOCS[em.doc_type].model, em.doc_id)
    data = document_data(db, em.doc_type, obj)
    company = db.get(Company, em.company_id)
    user_email = None
    if em.created_by_id:
        from app.modules.iam.models import User

        u = db.get(User, em.created_by_id)
        user_email = u.email if u else None
    msg = mailer.build(sender_name=company.trade_name or company.legal_name,
                       to=em.to_addresses.split(", "), cc=em.cc_addresses.split(", ") if em.cc_addresses else [],
                       reply_to=company.email or user_email, subject=em.subject, body=em.body,
                       attachments=[(filename_for(data), "application/pdf", render(data))])
    em.message_id = mailer.send(msg, em.company_id)
    em.status, em.sent_at, em.error = "sent", datetime.now(UTC), None


def email_failed(db: Session, ev: IntegrationEvent, exc: Exception) -> None:
    em = db.get(DocumentEmail, ev.payload["email_id"], with_for_update=True)
    if em is None:
        return
    em.attempts = ev.attempts
    em.error = f"{type(exc).__name__}: {exc}"[:2000]
    if ev.attempts >= ev.max_attempts:
        em.status = "failed"


def history(db: Session, p: Principal, doc_type: str, doc_id: int) -> list[DocumentEmail]:
    _get(db, p, doc_type, doc_id)
    return list(db.scalars(select(DocumentEmail).where(
        DocumentEmail.company_id == p.company_id, DocumentEmail.doc_type == doc_type,
        DocumentEmail.doc_id == doc_id).order_by(DocumentEmail.id.desc())))
