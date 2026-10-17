"""Estructura organizacional: empresas, sedes, unidades, centros de costo, monedas, tasas, secuencias."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, JsonType, Rate, TimestampMixin

DEFAULT_COMPANY_SETTINGS = {
    # Segregación de funciones
    "sod_requisition_self_approval": False,
    "sod_po_self_approval": False,
    "sod_adjustment_self_approval": False,
    "sod_journal_self_post": False,
    "sod_opening_balance_self_approval": False,
    # Tolerancias
    "receipt_over_tolerance_pct": "0",
    "invoice_price_tolerance_pct": "1",
    "invoice_qty_tolerance_pct": "0",
    # Reservas e inventario
    "reservation_strategy": "FEFO",
    # Presupuesto de compras: "warn" (advierte) o "block" (impide aprobar)
    "purchase_budget_control": "warn",
}


class Currency(Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    decimals: Mapped[int] = mapped_column(default=2)


class Company(IdMixin, TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (CheckConstraint("country_code in ('CO','VE')", name="country_supported"),)

    code: Mapped[str] = mapped_column(String(20), unique=True)
    legal_name: Mapped[str] = mapped_column(String(200))
    trade_name: Mapped[str | None] = mapped_column(String(200))
    tax_id: Mapped[str] = mapped_column(String(30))
    tax_id_check_digit: Mapped[str | None] = mapped_column(String(2))
    country_code: Mapped[str] = mapped_column(String(2))
    functional_currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    fiscal_regime: Mapped[str | None] = mapped_column(String(60))
    is_withholding_agent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_special_taxpayer: Mapped[bool] = mapped_column(Boolean, default=False)
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    city_code: Mapped[str | None] = mapped_column(String(10))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(40))
    settings: Mapped[dict] = mapped_column(JsonType, default=lambda: dict(DEFAULT_COMPANY_SETTINGS))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def setting(self, key: str):
        return (self.settings or {}).get(key, DEFAULT_COMPANY_SETTINGS.get(key))


class CompanyModule(Base):
    """Activación de módulos por empresa (p. ej. producción desactivada en comercializadoras)."""

    __tablename__ = "company_modules"

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    module_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Site(IdMixin, TimestampMixin, Base):
    __tablename__ = "sites"
    __table_args__ = (UniqueConstraint("company_id", "code"),)

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BusinessUnit(IdMixin, TimestampMixin, Base):
    __tablename__ = "business_units"
    __table_args__ = (UniqueConstraint("company_id", "code"),)

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CostCenter(IdMixin, TimestampMixin, Base):
    __tablename__ = "cost_centers"
    __table_args__ = (UniqueConstraint("company_id", "code"),)

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"))
    business_unit_id: Mapped[int | None] = mapped_column(ForeignKey("business_units.id"))
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExchangeRate(IdMixin, TimestampMixin, Base):
    """Tasa oficial por fecha y fuente (p. ej. TRM Banco de la República, BCV)."""

    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("from_currency", "to_currency", "rate_date", "source"),
        CheckConstraint("rate > 0", name="rate_positive"),
    )

    from_currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    to_currency: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    rate_date: Mapped[date] = mapped_column(Date, index=True)
    rate: Mapped[Decimal] = mapped_column(Rate)
    source: Mapped[str] = mapped_column(String(40))


class DocumentSequence(IdMixin, Base):
    """Numeración interna correlativa por empresa y tipo de documento (bloqueo por fila al asignar)."""

    __tablename__ = "document_sequences"
    __table_args__ = (UniqueConstraint("company_id", "doc_type"),)

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    doc_type: Mapped[str] = mapped_column(String(40))
    prefix: Mapped[str] = mapped_column(String(20))
    next_number: Mapped[int] = mapped_column(default=1)
    padding: Mapped[int] = mapped_column(default=6)


class Attachment(IdMixin, Base):
    """Documento adjunto (evidencias de calidad, soportes de entrega, XML fiscales, archivos importados)."""

    __tablename__ = "attachments"

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[int] = mapped_column()
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(400))
    description: Mapped[str | None] = mapped_column(Text)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IntegrationEvent(IdMixin, Base):
    """Bandeja de salida (outbox) para integraciones con reintentos seguros e idempotencia."""

    __tablename__ = "integration_events"
    __table_args__ = (UniqueConstraint("idempotency_key"),)

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JsonType)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=8)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IdempotencyRecord(IdMixin, Base):
    """Respuestas almacenadas por cabecera Idempotency-Key para reintentos de clientes."""

    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("company_id", "scope", "key"),)

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    scope: Mapped[str] = mapped_column(String(80))
    key: Mapped[str] = mapped_column(String(120))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column()
    response_body: Mapped[dict] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
