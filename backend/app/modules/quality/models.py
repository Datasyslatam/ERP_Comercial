"""Control y aseguramiento de la calidad: planes, inspecciones, no conformidades y CAPA."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, CompanyMixin, IdMixin, Qty, TimestampMixin

STAGES = ("receiving", "in_process", "final", "dispatch")


class InspectionPlan(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "inspection_plans"
    __table_args__ = (
        UniqueConstraint("company_id", "code"),
        CheckConstraint("stage in ('receiving','in_process','final','dispatch')", name="stage_valid"),
    )

    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(200))
    stage: Mapped[str] = mapped_column(String(12))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("item_categories.id"))
    sampling_rule: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    characteristics: Mapped[list["InspectionCharacteristic"]] = relationship(
        cascade="all, delete-orphan", order_by="InspectionCharacteristic.id", lazy="selectin"
    )


class InspectionCharacteristic(IdMixin, Base):
    __tablename__ = "inspection_characteristics"
    __table_args__ = (CheckConstraint("kind in ('numeric','boolean','text')", name="kind_valid"),)

    plan_id: Mapped[int] = mapped_column(ForeignKey("inspection_plans.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10))
    target: Mapped[Decimal | None] = mapped_column(Qty)
    lower_limit: Mapped[Decimal | None] = mapped_column(Qty)
    upper_limit: Mapped[Decimal | None] = mapped_column(Qty)
    unit: Mapped[str | None] = mapped_column(String(20))
    acceptance_criteria: Mapped[str | None] = mapped_column(String(255))
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)


class Inspection(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "inspections"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        CheckConstraint("status in ('pending','accepted','rejected','partial','cancelled')", name="status_valid"),
        CheckConstraint("qty_accepted >= 0 and qty_rejected >= 0", name="qty_nonneg"),
        Index("ix_inspections_source", "source_type", "source_id"),
    )

    number: Mapped[str] = mapped_column(String(30))
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("inspection_plans.id"))
    stage: Mapped[str] = mapped_column(String(12))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lots.id"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[int] = mapped_column()
    quantity: Mapped[Decimal] = mapped_column(Qty)
    qty_accepted: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qty_rejected: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(10), default="pending")
    due_date: Mapped[date | None] = mapped_column(Date)
    inspector_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    results: Mapped[list["InspectionResult"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class InspectionResult(IdMixin, Base):
    __tablename__ = "inspection_results"

    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id", ondelete="CASCADE"), index=True)
    characteristic_id: Mapped[int | None] = mapped_column(ForeignKey("inspection_characteristics.id"))
    name: Mapped[str] = mapped_column(String(120))
    numeric_value: Mapped[Decimal | None] = mapped_column(Qty)
    bool_value: Mapped[bool | None] = mapped_column(Boolean)
    text_value: Mapped[str | None] = mapped_column(String(255))
    is_conforming: Mapped[bool] = mapped_column(Boolean)


class NonConformity(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "nonconformities"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        CheckConstraint(
            "source in ('inspection','customer','internal','supplier','delivery','production')", name="source_valid"
        ),
        CheckConstraint("severity in ('minor','major','critical')", name="severity_valid"),
        CheckConstraint("status in ('open','analysis','action','verification','closed')", name="status_valid"),
    )

    number: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(12))
    inspection_id: Mapped[int | None] = mapped_column(ForeignKey("inspections.id"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), index=True)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lots.id"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    category: Mapped[str | None] = mapped_column(String(60))  # para detectar recurrencia
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(10), default="minor")
    quantity_affected: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    cost_impact: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    disposition: Mapped[str | None] = mapped_column(String(20))  # rework, scrap, return_to_supplier, use_as_is
    root_cause: Mapped[str | None] = mapped_column(Text)
    root_cause_method: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(14), default="open")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responsible_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    actions: Mapped[list["CapaAction"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class CapaAction(IdMixin, TimestampMixin, Base):
    __tablename__ = "capa_actions"
    __table_args__ = (
        CheckConstraint("action_type in ('containment','corrective','preventive')", name="type_valid"),
        CheckConstraint("status in ('open','done','verified','cancelled')", name="status_valid"),
    )

    nonconformity_id: Mapped[int] = mapped_column(ForeignKey("nonconformities.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(12))
    description: Mapped[str] = mapped_column(Text)
    responsible_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effectiveness_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="open")
