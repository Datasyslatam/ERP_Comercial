"""Contabilidad por partida doble, cartera (CxC/CxP), tesorería, conciliación, presupuestos y metas."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, CompanyMixin, IdMixin, Rate, TimestampMixin

ACCOUNT_TYPES = ("asset", "liability", "equity", "revenue", "expense", "cost")

# Claves de parametrización contable (posting_accounts.key).
POSTING_KEYS = (
    "inventory", "grni", "accounts_payable", "accounts_receivable", "revenue", "sales_returns", "cogs",
    "inventory_adjustment_gain", "inventory_adjustment_loss", "scrap_expense", "wip", "production_variance",
    "opening_balance", "fx_difference", "freight_expense", "purchase_price_variance", "applied_labor", "retained_earnings",
)


class Account(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("company_id", "code"),
        CheckConstraint("account_type in ('asset','liability','equity','revenue','expense','cost')", name="type_valid"),
        CheckConstraint("normal_balance in ('debit','credit')", name="normal_valid"),
    )

    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    account_type: Mapped[str] = mapped_column(String(10))
    normal_balance: Mapped[str] = mapped_column(String(6))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    is_postable: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_party: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_cost_center: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cash: Mapped[bool] = mapped_column(Boolean, default=False)  # caja y bancos (flujo de efectivo)
    cash_flow_activity: Mapped[str | None] = mapped_column(String(12))  # operating/investing/financing
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PostingAccount(IdMixin, CompanyMixin, Base):
    __tablename__ = "posting_accounts"
    __table_args__ = (UniqueConstraint("company_id", "key"),)

    key: Mapped[str] = mapped_column(String(40))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))


class FiscalPeriod(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "fiscal_periods"
    __table_args__ = (
        UniqueConstraint("company_id", "year", "month"),
        CheckConstraint("status in ('open','closed')", name="status_valid"),
        CheckConstraint("month between 1 and 12", name="month_valid"),
    )

    year: Mapped[int] = mapped_column()
    month: Mapped[int] = mapped_column()
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(8), default="open")
    closed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopened_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopen_reason: Mapped[str | None] = mapped_column(Text)


class JournalEntry(IdMixin, CompanyMixin, TimestampMixin, Base):
    """Comprobante contable. Una vez contabilizado es inmutable (trigger); se corrige por reverso."""

    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        UniqueConstraint("company_id", "idempotency_key"),
        CheckConstraint("status in ('draft','posted','reversed')", name="status_valid"),
        Index("ix_journal_source", "source_type", "source_id"),
        Index("ix_journal_date", "company_id", "entry_date"),
    )

    number: Mapped[str] = mapped_column(String(30))
    entry_date: Mapped[date] = mapped_column(Date)
    period_id: Mapped[int] = mapped_column(ForeignKey("fiscal_periods.id"))
    journal_type: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(10), default="draft")
    source_type: Mapped[str | None] = mapped_column(String(40))
    source_id: Mapped[int | None] = mapped_column()
    idempotency_key: Mapped[str] = mapped_column(String(160))
    reversal_of_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    posted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_debit: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total_credit: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", order_by="JournalLine.line_no"
    )


class JournalLine(IdMixin, CompanyMixin, Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint(
            "debit >= 0 and credit >= 0 and (debit = 0 or credit = 0) and debit + credit > 0", name="one_side"
        ),
        Index("ix_journal_lines_account", "company_id", "account_id"),
    )

    entry_id: Mapped[int] = mapped_column(ForeignKey("journal_entries.id", ondelete="CASCADE"), index=True)
    line_no: Mapped[int] = mapped_column()
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    debit: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    description: Mapped[str | None] = mapped_column(String(255))
    party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"))
    currency: Mapped[str | None] = mapped_column(ForeignKey("currencies.code"))
    amount_currency: Mapped[Decimal | None] = mapped_column()
    exchange_rate: Mapped[Decimal | None] = mapped_column(Rate)

    entry: Mapped[JournalEntry] = relationship(back_populates="lines")


class OpenItem(IdMixin, CompanyMixin, TimestampMixin, Base):
    """Partida abierta de cartera: CxC (receivable) o CxP (payable). Importes en moneda del documento."""

    __tablename__ = "open_items"
    __table_args__ = (
        UniqueConstraint("company_id", "kind", "document_type", "document_id"),
        CheckConstraint("kind in ('receivable','payable')", name="kind_valid"),
        CheckConstraint("open_amount >= 0 and open_amount <= original_amount", name="open_within"),
        CheckConstraint("status in ('open','partial','paid','cancelled')", name="status_valid"),
        Index("ix_open_items_party", "company_id", "kind", "party_id"),
    )

    kind: Mapped[str] = mapped_column(String(10))
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id"))
    document_type: Mapped[str] = mapped_column(String(30))
    document_id: Mapped[int] = mapped_column()
    document_number: Mapped[str] = mapped_column(String(60))
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    exchange_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("1"))
    original_amount: Mapped[Decimal]
    open_amount: Mapped[Decimal]
    status: Mapped[str] = mapped_column(String(10), default="open")
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"))


class BankAccount(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (UniqueConstraint("company_id", "name"),)

    name: Mapped[str] = mapped_column(String(120))
    bank_name: Mapped[str] = mapped_column(String(120))
    account_number_masked: Mapped[str] = mapped_column(String(40))
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    gl_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Payment(IdMixin, CompanyMixin, TimestampMixin, Base):
    """Recaudo de cliente (receipt) o pago a proveedor (disbursement)."""

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        UniqueConstraint("company_id", "idempotency_key"),
        CheckConstraint("kind in ('receipt','disbursement')", name="kind_valid"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("status in ('posted','voided')", name="status_valid"),
    )

    number: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(12))
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id"))
    payment_date: Mapped[date] = mapped_column(Date)
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("bank_accounts.id"))
    method: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    exchange_rate: Mapped[Decimal] = mapped_column(Rate, default=Decimal("1"))
    amount: Mapped[Decimal]
    withholding_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    igtf_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    reference: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(8), default="posted")
    idempotency_key: Mapped[str] = mapped_column(String(160))
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    allocations: Mapped[list["PaymentAllocation"]] = relationship(cascade="all, delete-orphan")
    withholdings: Mapped[list["PaymentWithholding"]] = relationship(cascade="all, delete-orphan")


class PaymentAllocation(IdMixin, Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), index=True)
    open_item_id: Mapped[int] = mapped_column(ForeignKey("open_items.id"), index=True)
    amount: Mapped[Decimal]


class PaymentWithholding(IdMixin, Base):
    """Retenciones que el cliente nos practica al pagar (o que practicamos al pagar, si aplica)."""

    __tablename__ = "payment_withholdings"

    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), index=True)
    tax_id: Mapped[int] = mapped_column(ForeignKey("taxes.id"))
    base: Mapped[Decimal]
    amount: Mapped[Decimal]
    # Solo en pagos a proveedores: número del comprobante de retención que se entrega al proveedor
    certificate_number: Mapped[str | None] = mapped_column(String(30))


class BankStatement(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "bank_statements"

    bank_account_id: Mapped[int] = mapped_column(ForeignKey("bank_accounts.id"))
    statement_date: Mapped[date] = mapped_column(Date)
    opening_balance: Mapped[Decimal]
    closing_balance: Mapped[Decimal]
    source_filename: Mapped[str | None] = mapped_column(String(255))
    imported_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    lines: Mapped[list["BankStatementLine"]] = relationship(cascade="all, delete-orphan", order_by="BankStatementLine.id")


class BankStatementLine(IdMixin, Base):
    __tablename__ = "bank_statement_lines"
    __table_args__ = (CheckConstraint("status in ('unmatched','matched','ignored')", name="status_valid"),)

    statement_id: Mapped[int] = mapped_column(ForeignKey("bank_statements.id", ondelete="CASCADE"), index=True)
    txn_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(255))
    reference: Mapped[str | None] = mapped_column(String(80))
    amount: Mapped[Decimal]  # positivo = abono (ingreso), negativo = cargo (egreso)
    status: Mapped[str] = mapped_column(String(10), default="unmatched")
    matched_journal_line_id: Mapped[int | None] = mapped_column(ForeignKey("journal_lines.id"), unique=True)
    matched_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class BudgetLine(IdMixin, CompanyMixin, TimestampMixin, Base):
    """Presupuesto mensual por dimensión. category: purchases, expenses, revenue."""

    __tablename__ = "budget_lines"
    __table_args__ = (
        UniqueConstraint("company_id", "year", "month", "category", "cost_center_id", "account_id", "site_id"),
        CheckConstraint("category in ('purchases','expenses','revenue')", name="category_valid"),
        CheckConstraint("amount >= 0", name="amount_nonneg"),
    )

    year: Mapped[int] = mapped_column()
    month: Mapped[int] = mapped_column()
    category: Mapped[str] = mapped_column(String(12))
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"))
    amount: Mapped[Decimal]
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class StrategicGoal(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "strategic_goals"
    __table_args__ = (UniqueConstraint("company_id", "code"),)

    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    kpi_code: Mapped[str] = mapped_column(String(60))
    target_value: Mapped[Decimal] = mapped_column(Rate)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    weight: Mapped[Decimal] = mapped_column(default=Decimal("1"))
