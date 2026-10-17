"""Logística: despachos (picking, packing, envío, entrega), rutas, seguimiento, incidencias y devoluciones."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, CompanyMixin, IdMixin, Qty, TimestampMixin

DISPATCH_STATUSES = ("draft", "picking", "picked", "packed", "shipped", "delivered", "partially_delivered", "cancelled")


class DeliveryRoute(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "delivery_routes"
    __table_args__ = (UniqueConstraint("company_id", "code"),)

    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"))
    standard_lead_days: Mapped[int] = mapped_column(default=1)


class DispatchOrder(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "dispatch_orders"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        CheckConstraint(
            "status in ('draft','picking','picked','packed','shipped','delivered','partially_delivered','cancelled')",
            name="status_valid",
        ),
        CheckConstraint("freight_cost >= 0", name="freight_nonneg"),
    )

    number: Mapped[str] = mapped_column(String(30))
    sales_order_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    promised_date: Mapped[date | None] = mapped_column(Date)
    delivery_address: Mapped[str | None] = mapped_column(String(255))
    carrier_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    route_id: Mapped[int | None] = mapped_column(ForeignKey("delivery_routes.id"))
    planned_ship_date: Mapped[date | None] = mapped_column(Date)
    vehicle_plate: Mapped[str | None] = mapped_column(String(20))
    driver_name: Mapped[str | None] = mapped_column(String(120))
    tracking_number: Mapped[str | None] = mapped_column(String(60))
    freight_cost: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    packages_count: Mapped[int] = mapped_column(default=0)
    gross_weight_kg: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    picked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    packed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pod_received_by: Mapped[str | None] = mapped_column(String(120))
    pod_notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    lines: Mapped[list["DispatchLine"]] = relationship(cascade="all, delete-orphan", order_by="DispatchLine.id",
                                                        lazy="selectin")


class DispatchLine(IdMixin, Base):
    __tablename__ = "dispatch_lines"
    __table_args__ = (
        CheckConstraint("qty_requested > 0", name="qty_positive"),
        CheckConstraint("qty_picked <= qty_requested", name="picked_within_requested"),
        CheckConstraint("qty_shipped <= qty_picked", name="shipped_within_picked"),
        CheckConstraint("qty_delivered <= qty_shipped", name="delivered_within_shipped"),
        CheckConstraint("qty_returned <= qty_shipped", name="returned_within_shipped"),
    )

    dispatch_id: Mapped[int] = mapped_column(ForeignKey("dispatch_orders.id", ondelete="CASCADE"), index=True)
    so_line_id: Mapped[int] = mapped_column(ForeignKey("sales_order_lines.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    qty_requested: Mapped[Decimal] = mapped_column(Qty)
    qty_picked: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qty_shipped: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qty_delivered: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qty_returned: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qty_invoiced: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    unit_cost: Mapped[Decimal | None] = mapped_column(Qty)


class ShipmentEvent(IdMixin, Base):
    __tablename__ = "shipment_events"

    dispatch_id: Mapped[int] = mapped_column(ForeignKey("dispatch_orders.id", ondelete="CASCADE"), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30))
    location_text: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class DeliveryIncident(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "delivery_incidents"
    __table_args__ = (
        CheckConstraint(
            "incident_type in ('damaged','missing','late','rejected','address','other')", name="type_valid"
        ),
        CheckConstraint("status in ('open','resolved')", name="status_valid"),
    )

    dispatch_id: Mapped[int] = mapped_column(ForeignKey("dispatch_orders.id"), index=True)
    incident_type: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="open")
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class CustomerReturn(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "customer_returns"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        CheckConstraint("status in ('draft','received','cancelled')", name="status_valid"),
    )

    number: Mapped[str] = mapped_column(String(30))
    dispatch_id: Mapped[int] = mapped_column(ForeignKey("dispatch_orders.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("parties.id"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    return_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(10), default="draft")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    lines: Mapped[list["CustomerReturnLine"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class CustomerReturnLine(IdMixin, Base):
    __tablename__ = "customer_return_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="qty_positive"),
        CheckConstraint("condition in ('resellable','damaged')", name="condition_valid"),
    )

    return_id: Mapped[int] = mapped_column(ForeignKey("customer_returns.id", ondelete="CASCADE"), index=True)
    dispatch_line_id: Mapped[int] = mapped_column(ForeignKey("dispatch_lines.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lots.id"))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    condition: Mapped[str] = mapped_column(String(12), default="resellable")
