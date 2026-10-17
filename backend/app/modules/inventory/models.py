"""Inventario transaccional: bodegas, ubicaciones, lotes, movimientos (libro), saldos, costos y reservas.

Fuente de verdad: stock_moves (append-only). stock_balances e item_costs son proyecciones que se
actualizan en la misma transacción y pueden reconstruirse desde los movimientos.
"""
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
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, CompanyMixin, IdMixin, Qty, TimestampMixin, UnitCost

MOVE_TYPES = (
    "receipt", "supplier_return", "dispatch", "customer_return", "transfer", "adjustment_in", "adjustment_out",
    "production_issue", "production_output", "scrap", "opening", "count_in", "count_out", "consumption",
)


class Warehouse(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "warehouses"
    __table_args__ = (UniqueConstraint("company_id", "code"),)

    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    locations: Mapped[list["Location"]] = relationship(back_populates="warehouse")


class Location(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "code"),
        CheckConstraint(
            "location_type in ('receiving','storage','quality','dispatch','production','scrap','transit')",
            name="type_valid",
        ),
    )

    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(120))
    zone: Mapped[str | None] = mapped_column(String(40))
    location_type: Mapped[str] = mapped_column(String(20), default="storage")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    warehouse: Mapped[Warehouse] = relationship(back_populates="locations")


class Lot(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "lots"
    __table_args__ = (
        UniqueConstraint("company_id", "item_id", "lot_number"),
        CheckConstraint("status in ('quarantine','released','blocked')", name="status_valid"),
    )

    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    lot_number: Mapped[str] = mapped_column(String(60))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    manufactured_date: Mapped[date | None] = mapped_column(Date)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    status: Mapped[str] = mapped_column(String(12), default="released")
    status_reason: Mapped[str | None] = mapped_column(String(255))


class StockBalance(IdMixin, CompanyMixin, Base):
    __tablename__ = "stock_balances"
    __table_args__ = (
        Index("uq_stock_balance_key", "item_id", "location_id", func.coalesce(text("lot_id"), 0),
              unique=True),
        CheckConstraint("qty_on_hand >= 0", name="no_negative_stock"),
        CheckConstraint("qty_reserved >= 0 and qty_reserved <= qty_on_hand", name="reserved_within_onhand"),
    )

    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lots.id"))
    qty_on_hand: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    qty_reserved: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ItemCost(CompanyMixin, Base):
    """Costo promedio ponderado perpetuo por empresa y artículo."""

    __tablename__ = "item_costs"
    __table_args__ = (
        CheckConstraint("qty_total >= 0", name="qty_nonneg"),
        CheckConstraint("avg_cost >= 0", name="cost_nonneg"),
    )

    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    avg_cost: Mapped[Decimal] = mapped_column(UnitCost, default=Decimal("0"))
    qty_total: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StockMove(IdMixin, CompanyMixin, Base):
    """Movimiento de inventario inmutable. Todo movimiento tiene fecha, responsable, motivo y documento origen."""

    __tablename__ = "stock_moves"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="qty_positive"),
        CheckConstraint("from_location_id is not null or to_location_id is not null", name="has_location"),
        Index("ix_stock_moves_item_date", "company_id", "item_id", "move_date"),
        Index("ix_stock_moves_source", "source_type", "source_id"),
    )

    move_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    move_type: Mapped[str] = mapped_column(String(24))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lots.id"))
    from_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    to_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    unit_cost: Mapped[Decimal] = mapped_column(UnitCost)
    total_cost: Mapped[Decimal]
    source_type: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[int] = mapped_column()
    source_line_id: Mapped[int | None] = mapped_column()
    reference: Mapped[str | None] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StockReservation(IdMixin, CompanyMixin, Base):
    __tablename__ = "stock_reservations"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="qty_positive"),
        CheckConstraint("quantity_consumed >= 0 and quantity_consumed <= quantity", name="consumed_within"),
        CheckConstraint("status in ('active','consumed','released')", name="status_valid"),
        Index("ix_reservations_source", "source_type", "source_line_id"),
    )

    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lots.id"))
    quantity: Mapped[Decimal] = mapped_column(Qty)
    quantity_consumed: Mapped[Decimal] = mapped_column(Qty, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(10), default="active")
    source_type: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[int] = mapped_column()
    source_line_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InventoryDocument(IdMixin, CompanyMixin, TimestampMixin, Base):
    """Transferencias, ajustes, consumos internos y bajas. Los ajustes requieren aprobación."""

    __tablename__ = "inventory_documents"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        CheckConstraint("doc_type in ('transfer','adjustment','consumption','scrap')", name="type_valid"),
        CheckConstraint("status in ('draft','approved','posted','cancelled')", name="status_valid"),
    )

    number: Mapped[str] = mapped_column(String(30))
    doc_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(12), default="draft")
    doc_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(255))
    cost_center_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centers.id"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lines: Mapped[list["InventoryDocumentLine"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="InventoryDocumentLine.id"
    )


class InventoryDocumentLine(IdMixin, Base):
    __tablename__ = "inventory_document_lines"
    __table_args__ = (CheckConstraint("quantity <> 0", name="qty_nonzero"),)

    document_id: Mapped[int] = mapped_column(ForeignKey("inventory_documents.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lots.id"))
    from_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    to_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    # En ajustes: positivo = entrada, negativo = salida.
    quantity: Mapped[Decimal] = mapped_column(Qty)
    unit_cost: Mapped[Decimal | None] = mapped_column(UnitCost)

    document: Mapped[InventoryDocument] = relationship(back_populates="lines")


class PhysicalCount(IdMixin, CompanyMixin, TimestampMixin, Base):
    __tablename__ = "physical_counts"
    __table_args__ = (
        UniqueConstraint("company_id", "number"),
        CheckConstraint("status in ('open','counted','posted','cancelled')", name="status_valid"),
    )

    number: Mapped[str] = mapped_column(String(30))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    count_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12), default="open")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    lines: Mapped[list["PhysicalCountLine"]] = relationship(
        back_populates="count", cascade="all, delete-orphan", order_by="PhysicalCountLine.id"
    )


class PhysicalCountLine(IdMixin, Base):
    __tablename__ = "physical_count_lines"

    count_id: Mapped[int] = mapped_column(ForeignKey("physical_counts.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lots.id"))
    system_qty: Mapped[Decimal] = mapped_column(Qty)
    counted_qty: Mapped[Decimal | None] = mapped_column(Qty)

    count: Mapped[PhysicalCount] = relationship(back_populates="lines")

    @property
    def difference(self) -> Decimal | None:
        return None if self.counted_qty is None else self.counted_qty - self.system_qty
