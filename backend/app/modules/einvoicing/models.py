"""Facturación de ventas y documento electrónico (DIAN / SENIAT) desacoplado del proveedor tecnológico."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, CompanyMixin, IdMixin, Qty, Rate, TimestampMixin, UnitCost

# Estados explícitos del documento electrónico. Se mapean a los estados oficiales en cada adaptador.
EDOC_STATES = ("draft", "pending", "sent", "accepted", "rejected", "error")


class NumberingRange(IdMixin, CompanyMixin, TimestampMixin, Base):
    """Numeración autorizada (resolución DIAN o asignación de la imprenta digital SENIAT)."""

    __tablename__ = "numbering_ranges"
    __table_args__ = (
        UniqueConstraint("company_id", "doc_type", "prefix", "range_from"),
        CheckConstraint("range_to >= range_from and next_number >= range_from", name="range_valid"),
        CheckConstraint("environment in ('sandbox','production')", name="env_valid"),
        CheckConstraint("doc_type in ('invoice','credit_note','debit_note')", name="doctype_valid"),
    )

    doc_type: Mapped[str] = mapped_column(String(12))
    prefix: Mapped[str] = mapped_column(String(10))
    range_from: Mapped[int] = mapped_column()
    range_to: Mapped[int] = mapped_column()
    next_number: Mapped[int] = mapped_column()
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    authorization_number: Mapped[str] = mapped_column(String(60))
    technical_key: Mapped[str | None] = mapped_column(String(120))  # ClTec DIAN; nunca en el repositorio
    environment: Mapped[str] = mapped_column(String(10), default="sandbox")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SalesInvoice(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "sales_invoices"
    __table_args__ = (
        UniqueConstraint("company_id", "doc_type", "prefix", "number"),
        UniqueConstraint("company_id", "idempotency_key"),
        CheckConstraint("doc_type in ('invoice','credit_note','debit_note')", name="doctype_valid"),
        CheckConstraint("status in ('draft','issued','cancelled')", name="status_valid"),
        CheckConstraint(
            "edoc_status in ('draft','pending','sent','accepted','rejected','error')", name="edoc_status_valid"
        ),
        CheckConstraint("doc_type = 'invoice' or reference_invoice_id is not null", name="notes_reference"),
    )

    doc_type: Mapped[str] = mapped_column(String(12), default="invoice")
    prefix: Mapped[str | None] = mapped_column(String(10))
    number: Mapped[int | None] = mapped_column()
    full_number: Mapped[str | None] = mapped_column(String(40))
    numbering_range_id: Mapped[int | None] = mapped_column(ForeignKey("numbering_ranges.id"))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), index=True)
    sales_order_id: Mapped[int | None] = mapped_column(ForeignKey("sales_orders.id"))
    dispatch_id: Mapped[int | None] = mapped_column(ForeignKey("dispatch_orders.id"))
    reference_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("sales_invoices.id"))
    correction_code: Mapped[str | None] = mapped_column(String(4))
    correction_reason: Mapped[str | None] = mapped_column(String(255))
    issue_date: Mapped[date] = mapped_column(Date)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[date] = mapped_column(Date)
    payment_form: Mapped[str] = mapped_column(String(10), default="credit")  # cash / credit
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    exchange_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("1"))
    subtotal: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    discount_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    tax_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(10), default="draft")
    edoc_status: Mapped[str] = mapped_column(String(10), default="draft")
    edoc_environment: Mapped[str | None] = mapped_column(String(10))
    edoc_adapter: Mapped[str | None] = mapped_column(String(40))
    fiscal_uid: Mapped[str | None] = mapped_column(String(120))  # CUFE/CUDE (CO) o identificador de la imprenta
    control_number: Mapped[str | None] = mapped_column(String(40))  # Número de control (VE)
    legal_validity: Mapped[bool] = mapped_column(Boolean, default=False)
    edoc_message: Mapped[str | None] = mapped_column(Text)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    lines: Mapped[list["SalesInvoiceLine"]] = relationship(
        cascade="all, delete-orphan", order_by="SalesInvoiceLine.line_no", lazy="selectin"
    )
    taxes: Mapped[list["SalesInvoiceTax"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class SalesInvoiceLine(IdMixin, Base):
    __tablename__ = "sales_invoice_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0 and unit_price >= 0", name="values_valid"),
        CheckConstraint("discount_pct >= 0 and discount_pct <= 100", name="discount_valid"),
    )

    invoice_id: Mapped[int] = mapped_column(ForeignKey("sales_invoices.id", ondelete="CASCADE"), index=True)
    line_no: Mapped[int] = mapped_column()
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    uom_code: Mapped[str] = mapped_column(String(10))
    unit_price: Mapped[Decimal] = mapped_column(UnitCost)
    discount_pct: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    tax_id: Mapped[int | None] = mapped_column(ForeignKey("taxes.id"))
    tax_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    line_subtotal: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    so_line_id: Mapped[int | None] = mapped_column(ForeignKey("sales_order_lines.id"))
    dispatch_line_id: Mapped[int | None] = mapped_column(ForeignKey("dispatch_lines.id"))


class SalesInvoiceTax(IdMixin, Base):
    __tablename__ = "sales_invoice_taxes"

    invoice_id: Mapped[int] = mapped_column(ForeignKey("sales_invoices.id", ondelete="CASCADE"), index=True)
    tax_id: Mapped[int] = mapped_column(ForeignKey("taxes.id"))
    base: Mapped[Decimal]
    rate: Mapped[Decimal] = mapped_column(Qty)
    amount: Mapped[Decimal]


class EInvoiceSubmission(IdMixin, Base):
    """Cada intento de envío/consulta al proveedor tecnológico queda registrado (trazabilidad y conservación)."""

    __tablename__ = "einvoice_submissions"
    __table_args__ = (UniqueConstraint("invoice_id", "attempt_no"),)

    invoice_id: Mapped[int] = mapped_column(ForeignKey("sales_invoices.id"), index=True)
    attempt_no: Mapped[int] = mapped_column()
    operation: Mapped[str] = mapped_column(String(10))  # submit / status
    adapter: Mapped[str] = mapped_column(String(40))
    environment: Mapped[str] = mapped_column(String(10))
    document_sha256: Mapped[str | None] = mapped_column(String(64))
    document_attachment_id: Mapped[int | None] = mapped_column(ForeignKey("attachments.id"))
    result_status: Mapped[str] = mapped_column(String(10))
    provider_code: Mapped[str | None] = mapped_column(String(40))
    provider_message: Mapped[str | None] = mapped_column(Text)
    provider_tracking_id: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
