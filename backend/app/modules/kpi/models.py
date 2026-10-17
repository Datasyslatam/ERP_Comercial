"""Indicadores: metadatos, metas por empresa, instantáneas calculadas y alertas."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CompanyMixin, IdMixin, JsonType, Rate


class KpiTarget(IdMixin, CompanyMixin, Base):
    """Meta y umbrales de un KPI para una empresa (opcionalmente por sede)."""

    __tablename__ = "kpi_targets"
    __table_args__ = (UniqueConstraint("company_id", "kpi_code", "site_id"),)

    kpi_code: Mapped[str] = mapped_column(String(60))
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"))
    target: Mapped[Decimal | None] = mapped_column(Rate)
    warning_threshold: Mapped[Decimal | None] = mapped_column(Rate)
    critical_threshold: Mapped[Decimal | None] = mapped_column(Rate)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    alerts_enabled: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KpiSnapshot(IdMixin, CompanyMixin, Base):
    __tablename__ = "kpi_snapshots"
    __table_args__ = (Index("ix_kpi_snap", "company_id", "kpi_code", "period_end"),)

    kpi_code: Mapped[str] = mapped_column(String(60))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    filters: Mapped[dict] = mapped_column(JsonType, default=dict)
    value: Mapped[Decimal | None] = mapped_column(Rate)
    status: Mapped[str] = mapped_column(String(10))
    confidence: Mapped[str] = mapped_column(String(10))
    details: Mapped[dict] = mapped_column(JsonType, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Alert(IdMixin, CompanyMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("severity in ('info','warning','critical')", name="severity_valid"),
        CheckConstraint("status in ('open','acknowledged','closed')", name="status_valid"),
        Index("ix_alerts_open", "company_id", "status"),
    )

    source: Mapped[str] = mapped_column(String(60))  # kpi:<code>, stock:min, stock:expiry ...
    dedupe_key: Mapped[str] = mapped_column(String(160))
    severity: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(Text)
    value: Mapped[Decimal | None] = mapped_column(Rate)
    threshold: Mapped[Decimal | None] = mapped_column(Rate)
    link: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(14), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    acknowledged_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
