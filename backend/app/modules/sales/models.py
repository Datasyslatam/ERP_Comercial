"""Pedidos de venta: origen de reservas, despachos y facturación."""
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, CompanyMixin, IdMixin, Qty, Rate, TimestampMixin, UnitCost


class SalesOrder(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "sales_orders"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        CheckConstraint(
            "status in ('draft','confirmed','partially_dispatched','dispatched','closed','cancelled')",
            name="status_valid",
        ),
    )

    number: Mapped[str] = mapped_column(String(30))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    order_date: Mapped[date] = mapped_column(Date)
    promised_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    exchange_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("1"))
    payment_term_id: Mapped[int | None] = mapped_column(ForeignKey("payment_terms.id"))
    delivery_address: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(22), default="draft")
    subtotal: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    tax_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    lines: Mapped[list["SalesOrderLine"]] = relationship(
        cascade="all, delete-orphan", order_by="SalesOrderLine.line_no", lazy="selectin"
    )


class SalesOrderLine(IdMixin, Base):
    __tablename__ = "sales_order_lines"
    __table_args__ = (
        UniqueConstraint("sales_order_id", "line_no"),
        CheckConstraint("quantity > 0 and unit_price >= 0", name="values_valid"),
        CheckConstraint("discount_pct >= 0 and discount_pct <= 100", name="discount_valid"),
        CheckConstraint("qty_dispatched <= quantity", name="dispatch_within_qty"),
    )

    sales_order_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id", ondelete="CASCADE"), index=True)
    line_no: Mapped[int] = mapped_column()
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    description: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    unit_price: Mapped[Decimal] = mapped_column(UnitCost)
    discount_pct: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    tax_id: Mapped[int | None] = mapped_column(ForeignKey("taxes.id"))
    qty_reserved: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qty_dispatched: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qty_invoiced: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qty_returned: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))


class SalesQuote(IdMixin, CompanyMixin, TimestampMixin, Base):
    """Cotización a cliente: precede al pedido y deja trazabilidad de la oferta (aceptada, perdida o vencida)."""

    __tablename__ = "sales_quotes"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        CheckConstraint("status in ('draft','sent','accepted','rejected','cancelled')", name="status_valid"),
        CheckConstraint("valid_until >= quote_date", name="validity_valid"),
    )

    number: Mapped[str] = mapped_column(String(30))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), index=True)
    quote_date: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    payment_term_id: Mapped[int | None] = mapped_column(ForeignKey("payment_terms.id"))
    contact_name: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(10), default="draft")
    subtotal: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    tax_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text)
    lost_reason: Mapped[str | None] = mapped_column(String(255))
    sales_order_id: Mapped[int | None] = mapped_column(ForeignKey("sales_orders.id"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    lines: Mapped[list["SalesQuoteLine"]] = relationship(
        cascade="all, delete-orphan", order_by="SalesQuoteLine.line_no", lazy="selectin"
    )


class SalesQuoteLine(IdMixin, Base):
    __tablename__ = "sales_quote_lines"
    __table_args__ = (
        UniqueConstraint("quote_id", "line_no"),
        CheckConstraint("quantity > 0 and unit_price >= 0", name="values_valid"),
        CheckConstraint("discount_pct >= 0 and discount_pct <= 100", name="discount_valid"),
    )

    quote_id: Mapped[int] = mapped_column(ForeignKey("sales_quotes.id", ondelete="CASCADE"), index=True)
    line_no: Mapped[int] = mapped_column()
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    description: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    unit_price: Mapped[Decimal] = mapped_column(UnitCost)
    discount_pct: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    tax_id: Mapped[int | None] = mapped_column(ForeignKey("taxes.id"))
