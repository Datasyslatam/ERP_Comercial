"""Datos maestros compartidos: terceros, artículos, unidades, impuestos y condiciones de pago.

Un único maestro de terceros (clientes, proveedores, transportistas) evita duplicar datos entre módulos.
"""
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, IdMixin, Qty, TimestampMixin

ITEM_TYPES = ("raw_material", "supply", "wip", "finished_good", "merchandise", "service")
TAX_KINDS = ("vat", "consumption", "withholding_income", "withholding_vat", "withholding_ica", "igtf")


class UnitOfMeasure(IdMixin, Base):
    __tablename__ = "uoms"

    code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(60))
    category: Mapped[str] = mapped_column(String(20))  # unit, weight, volume, length, time


class UomConversion(IdMixin, Base):
    """Factor: 1 from_uom = factor * to_uom. item_id nulo => conversión general."""

    __tablename__ = "uom_conversions"
    __table_args__ = (
        UniqueConstraint("item_id", "from_uom_id", "to_uom_id"),
        CheckConstraint("factor > 0", name="factor_positive"),
    )

    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    from_uom_id: Mapped[int] = mapped_column(ForeignKey("uoms.id"))
    to_uom_id: Mapped[int] = mapped_column(ForeignKey("uoms.id"))
    factor: Mapped[Decimal] = mapped_column(Qty)


class PaymentTerm(IdMixin, Base):
    __tablename__ = "payment_terms"
    __table_args__ = (UniqueConstraint("company_id", "code"), CheckConstraint("days >= 0", name="days_nonneg"))

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(80))
    days: Mapped[int] = mapped_column(default=0)


class Tax(IdMixin, TimestampMixin, Base):
    """Impuesto o retención parametrizable. Las tarifas deben validarse con el asesor tributario."""

    __tablename__ = "taxes"
    __table_args__ = (
        UniqueConstraint("company_id", "code"),
        CheckConstraint("rate >= 0 and rate <= 100", name="rate_range"),
        CheckConstraint("base in ('subtotal','vat')", name="base_valid"),
        CheckConstraint("applies_to in ('sales','purchases','both')", name="applies_valid"),
    )

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(30))
    rate: Mapped[Decimal] = mapped_column(Qty)  # porcentaje
    base: Mapped[str] = mapped_column(String(10), default="subtotal")
    min_base_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    applies_to: Mapped[str] = mapped_column(String(10), default="both")
    electronic_code: Mapped[str | None] = mapped_column(String(10))  # código del anexo técnico
    # Cuenta usada en ventas (impuesto generado / retención que nos practican) y compras (descontable / retención por pagar)
    sales_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    purchase_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def is_withholding(self) -> bool:
        return self.kind.startswith("withholding")


class ItemCategory(IdMixin, TimestampMixin, Base):
    __tablename__ = "item_categories"
    __table_args__ = (UniqueConstraint("company_id", "code"),)

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("item_categories.id"))
    inventory_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    revenue_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    cogs_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    expense_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))


class Item(IdMixin, TimestampMixin, Base):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("company_id", "sku"),
        CheckConstraint(
            "item_type in ('raw_material','supply','wip','finished_good','merchandise','service')", name="type_valid"
        ),
        CheckConstraint("min_stock >= 0 and max_stock >= 0", name="minmax_nonneg"),
        CheckConstraint("not (item_type = 'service' and is_stocked)", name="service_not_stocked"),
    )

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    sku: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    barcode: Mapped[str | None] = mapped_column(String(60))
    item_type: Mapped[str] = mapped_column(String(20))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("item_categories.id"))
    base_uom_id: Mapped[int] = mapped_column(ForeignKey("uoms.id"))
    is_stocked: Mapped[bool] = mapped_column(Boolean, default=True)
    track_lots: Mapped[bool] = mapped_column(Boolean, default=False)
    track_expiry: Mapped[bool] = mapped_column(Boolean, default=False)
    track_serials: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_inspection: Mapped[bool] = mapped_column(Boolean, default=False)
    sales_tax_id: Mapped[int | None] = mapped_column(ForeignKey("taxes.id"))
    purchase_tax_id: Mapped[int | None] = mapped_column(ForeignKey("taxes.id"))
    min_stock: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    max_stock: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    list_price: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[ItemCategory | None] = relationship(lazy="joined")


class Party(IdMixin, TimestampMixin, Base):
    """Tercero: cliente, proveedor y/o transportista."""

    __tablename__ = "parties"
    __table_args__ = (
        UniqueConstraint("company_id", "id_type", "tax_id"),
        UniqueConstraint("company_id", "code"),
        CheckConstraint("is_customer or is_supplier or is_carrier", name="has_role"),
    )

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    person_type: Mapped[str] = mapped_column(String(12), default="organization")  # organization / person
    legal_name: Mapped[str] = mapped_column(String(200))
    trade_name: Mapped[str | None] = mapped_column(String(200))
    id_type: Mapped[str] = mapped_column(String(10))  # NIT, CC, CE, PAS, RIF, CI, EXT
    tax_id: Mapped[str] = mapped_column(String(30))
    check_digit: Mapped[str | None] = mapped_column(String(2))
    is_customer: Mapped[bool] = mapped_column(Boolean, default=False)
    is_supplier: Mapped[bool] = mapped_column(Boolean, default=False)
    is_carrier: Mapped[bool] = mapped_column(Boolean, default=False)
    fiscal_regime: Mapped[str | None] = mapped_column(String(60))
    is_withholding_agent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_special_taxpayer: Mapped[bool] = mapped_column(Boolean, default=False)
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    city_code: Mapped[str | None] = mapped_column(String(10))
    country_code: Mapped[str] = mapped_column(String(2), default="CO")
    payment_term_id: Mapped[int | None] = mapped_column(ForeignKey("payment_terms.id"))
    credit_limit: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    withholdings: Mapped[list[Tax]] = relationship(secondary="party_withholdings", lazy="selectin")


class PartyWithholding(Base):
    """Retenciones aplicables: en compras las practicamos al proveedor; en ventas nos las practica el cliente."""

    __tablename__ = "party_withholdings"

    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id", ondelete="CASCADE"), primary_key=True)
    tax_id: Mapped[int] = mapped_column(ForeignKey("taxes.id"), primary_key=True)
