"""Ciclo de abastecimiento: solicitud → cotización → orden → recepción → factura de proveedor."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, CompanyMixin, IdMixin, Qty, Rate, TimestampMixin, UnitCost


class PurchaseRequisition(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "purchase_requisitions"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        CheckConstraint(
            "status in ('draft','submitted','approved','rejected','cancelled','ordered')", name="status_valid"
        ),
    )

    number: Mapped[str] = mapped_column(String(30))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"))
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    needed_by: Mapped[date | None] = mapped_column(Date)
    justification: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    total_estimated: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["PurchaseRequisitionLine"]] = relationship(
        cascade="all, delete-orphan", order_by="PurchaseRequisitionLine.id", lazy="selectin"
    )


class PurchaseRequisitionLine(IdMixin, Base):
    __tablename__ = "purchase_requisition_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="qty_positive"),)

    requisition_id: Mapped[int] = mapped_column(ForeignKey("purchase_requisitions.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    description: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    estimated_unit_price: Mapped[Decimal] = mapped_column(UnitCost, default=Decimal("0"))


class RequestForQuotation(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "rfqs"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        CheckConstraint("status in ('open','awarded','cancelled')", name="status_valid"),
    )

    number: Mapped[str] = mapped_column(String(30))
    requisition_id: Mapped[int] = mapped_column(ForeignKey("purchase_requisitions.id"))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="open")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    quotes: Mapped[list["SupplierQuote"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class SupplierQuote(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "supplier_quotes"
    __table_args__ = (
        UniqueConstraint("rfq_id", "supplier_id"),
        CheckConstraint("status in ('received','selected','rejected')", name="status_valid"),
    )

    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("parties.id"))
    quote_reference: Mapped[str | None] = mapped_column(String(60))
    quote_date: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    delivery_days: Mapped[int] = mapped_column(default=0)
    payment_term_id: Mapped[int | None] = mapped_column(ForeignKey("payment_terms.id"))
    status: Mapped[str] = mapped_column(String(10), default="received")
    total: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    lines: Mapped[list["SupplierQuoteLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class SupplierQuoteLine(IdMixin, Base):
    __tablename__ = "supplier_quote_lines"
    __table_args__ = (CheckConstraint("quantity > 0 and unit_price >= 0", name="values_valid"),)

    quote_id: Mapped[int] = mapped_column(ForeignKey("supplier_quotes.id", ondelete="CASCADE"), index=True)
    requisition_line_id: Mapped[int] = mapped_column(ForeignKey("purchase_requisition_lines.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    unit_price: Mapped[Decimal] = mapped_column(UnitCost)
    tax_id: Mapped[int | None] = mapped_column(ForeignKey("taxes.id"))


class PurchaseOrder(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        CheckConstraint(
            "status in ('draft','submitted','approved','rejected','partially_received','received','closed','cancelled')",
            name="status_valid",
        ),
    )

    number: Mapped[str] = mapped_column(String(30))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), index=True)
    requisition_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_requisitions.id"))
    quote_id: Mapped[int | None] = mapped_column(ForeignKey("supplier_quotes.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"))
    order_date: Mapped[date] = mapped_column(Date)
    expected_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    exchange_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("1"))
    payment_term_id: Mapped[int | None] = mapped_column(ForeignKey("payment_terms.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    subtotal: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    tax_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        cascade="all, delete-orphan", order_by="PurchaseOrderLine.line_no", lazy="selectin"
    )


class PurchaseOrderLine(IdMixin, Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        UniqueConstraint("purchase_order_id", "line_no"),
        CheckConstraint("quantity > 0 and unit_price >= 0", name="values_valid"),
        CheckConstraint("qty_received >= 0 and qty_invoiced >= 0 and qty_rejected >= 0", name="progress_nonneg"),
    )

    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True)
    line_no: Mapped[int] = mapped_column()
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    requisition_line_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_requisition_lines.id"))
    description: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    unit_price: Mapped[Decimal] = mapped_column(UnitCost)
    tax_id: Mapped[int | None] = mapped_column(ForeignKey("taxes.id"))
    qty_received: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qty_rejected: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qty_invoiced: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))

    @property
    def line_subtotal(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))


class GoodsReceipt(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "goods_receipts"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        CheckConstraint("status in ('draft','posted','cancelled')", name="status_valid"),
    )

    number: Mapped[str] = mapped_column(String(30))
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("parties.id"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    receipt_date: Mapped[date] = mapped_column(Date)
    supplier_delivery_note: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(10), default="draft")
    received_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lines: Mapped[list["GoodsReceiptLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class GoodsReceiptLine(IdMixin, Base):
    __tablename__ = "goods_receipt_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="qty_positive"),
        CheckConstraint(
            "inspection_status in ('not_required','pending','accepted','rejected','partial')", name="insp_valid"
        ),
    )

    receipt_id: Mapped[int] = mapped_column(ForeignKey("goods_receipts.id", ondelete="CASCADE"), index=True)
    po_line_id: Mapped[int] = mapped_column(ForeignKey("purchase_order_lines.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    lot_number: Mapped[str | None] = mapped_column(String(60))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lots.id"))
    unit_cost: Mapped[Decimal] = mapped_column(UnitCost, default=Decimal("0"))  # moneda funcional
    qty_accepted: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qty_rejected: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qty_invoiced: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    inspection_status: Mapped[str] = mapped_column(String(14), default="not_required")


class SupplierInvoice(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "supplier_invoices"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        # Prevención de duplicados: el mismo número del proveedor no se registra dos veces.
        UniqueConstraint("company_id", "supplier_id", "supplier_invoice_number"),
        CheckConstraint("status in ('draft','posted','cancelled')", name="status_valid"),
    )

    number: Mapped[str] = mapped_column(String(30))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), index=True)
    supplier_invoice_number: Mapped[str] = mapped_column(String(60))
    supplier_cufe: Mapped[str | None] = mapped_column(String(120))
    supplier_control_number: Mapped[str | None] = mapped_column(String(40))  # Número de control (VE)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"))
    invoice_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    exchange_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("1"))
    subtotal: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    tax_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    withholding_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    payable_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(10), default="draft")
    match_status: Mapped[str | None] = mapped_column(String(20))
    match_notes: Mapped[str | None] = mapped_column(Text)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    posted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    lines: Mapped[list["SupplierInvoiceLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    taxes: Mapped[list["SupplierInvoiceTax"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class SupplierInvoiceLine(IdMixin, Base):
    __tablename__ = "supplier_invoice_lines"
    __table_args__ = (CheckConstraint("quantity > 0 and unit_price >= 0", name="values_valid"),)

    invoice_id: Mapped[int] = mapped_column(ForeignKey("supplier_invoices.id", ondelete="CASCADE"), index=True)
    receipt_line_id: Mapped[int | None] = mapped_column(ForeignKey("goods_receipt_lines.id"))
    po_line_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_order_lines.id"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    expense_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"))
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    unit_price: Mapped[Decimal] = mapped_column(UnitCost)
    tax_id: Mapped[int | None] = mapped_column(ForeignKey("taxes.id"))
    line_subtotal: Mapped[Decimal] = mapped_column(default=Decimal("0"))


class SupplierInvoiceTax(IdMixin, Base):
    __tablename__ = "supplier_invoice_taxes"

    invoice_id: Mapped[int] = mapped_column(ForeignKey("supplier_invoices.id", ondelete="CASCADE"), index=True)
    tax_id: Mapped[int] = mapped_column(ForeignKey("taxes.id"))
    base: Mapped[Decimal]
    rate: Mapped[Decimal] = mapped_column(Qty)
    amount: Mapped[Decimal]
    is_withholding: Mapped[bool] = mapped_column(default=False)
    # Retención practicada al causar: comprobante que se entrega al proveedor y fecha en que se practicó
    certificate_number: Mapped[str | None] = mapped_column(String(30))
    certificate_date: Mapped[date | None] = mapped_column(Date)
