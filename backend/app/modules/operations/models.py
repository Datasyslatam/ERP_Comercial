"""Operaciones: órdenes de trabajo de producción o de servicio, listas de materiales, consumos, tiempos e incidencias.

Para empresas comerciales el módulo puede desactivarse (company_modules). Para servicios, wo_type='service'
permite registrar proyecto, actividades, horas y entregables sin exigir producto de salida.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, CompanyMixin, IdMixin, Qty, TimestampMixin, UnitCost


class BillOfMaterials(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "boms"
    __table_args__ = (UniqueConstraint("company_id", "code"), CheckConstraint("base_quantity > 0", name="base_pos"))

    code: Mapped[str] = mapped_column(String(30))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    base_quantity: Mapped[Decimal] = mapped_column(Qty, default=Decimal("1"))
    is_active: Mapped[bool] = mapped_column(default=True)

    lines: Mapped[list["BomLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class BomLine(IdMixin, Base):
    __tablename__ = "bom_lines"
    __table_args__ = (CheckConstraint("quantity > 0 and scrap_pct >= 0", name="values_valid"),)

    bom_id: Mapped[int] = mapped_column(ForeignKey("boms.id", ondelete="CASCADE"), index=True)
    component_item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    scrap_pct: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))


class WorkOrder(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        CheckConstraint("wo_type in ('production','service','maintenance')", name="type_valid"),
        CheckConstraint(
            "status in ('draft','released','in_progress','completed','closed','cancelled')", name="status_valid"
        ),
        CheckConstraint("planned_qty >= 0 and produced_qty >= 0 and scrap_qty >= 0 and rework_qty >= 0",
                        name="qty_nonneg"),
    )

    number: Mapped[str] = mapped_column(String(30))
    wo_type: Mapped[str] = mapped_column(String(12))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    bom_id: Mapped[int | None] = mapped_column(ForeignKey("boms.id"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    project_name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    deliverables: Mapped[str | None] = mapped_column(Text)
    production_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    output_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    planned_qty: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    produced_qty: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    scrap_qty: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    rework_qty: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    planned_hours: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    estimated_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(12), default="draft")
    planned_start: Mapped[date | None] = mapped_column(Date)
    planned_end: Mapped[date | None] = mapped_column(Date)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    progress_pct: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    responsible_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    materials: Mapped[list["WorkOrderMaterial"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    time_logs: Mapped[list["WorkOrderTimeLog"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    incidents: Mapped[list["WorkOrderIncident"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class WorkOrderMaterial(IdMixin, Base):
    __tablename__ = "work_order_materials"
    __table_args__ = (CheckConstraint("planned_qty >= 0 and issued_qty >= 0", name="qty_nonneg"),)

    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    planned_qty: Mapped[Decimal] = mapped_column(Qty)
    issued_qty: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    issued_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    estimated_unit_cost: Mapped[Decimal] = mapped_column(UnitCost, default=Decimal("0"))


class WorkOrderTimeLog(IdMixin, Base):
    __tablename__ = "work_order_time_logs"
    __table_args__ = (CheckConstraint("hours > 0 and cost_per_hour >= 0", name="values_valid"),)

    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id", ondelete="CASCADE"), index=True)
    log_date: Mapped[date] = mapped_column(Date)
    resource_name: Mapped[str] = mapped_column(String(120))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    activity: Mapped[str] = mapped_column(String(200))
    hours: Mapped[Decimal] = mapped_column(Qty)
    cost_per_hour: Mapped[Decimal] = mapped_column(UnitCost, default=Decimal("0"))


class WorkOrderIncident(IdMixin, Base):
    __tablename__ = "work_order_incidents"

    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id", ondelete="CASCADE"), index=True)
    incident_type: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    downtime_minutes: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
