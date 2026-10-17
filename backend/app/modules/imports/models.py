"""Importación controlada de datos reales y lotes de saldos iniciales con aprobación."""
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, CompanyMixin, IdMixin, JsonType


class ImportJob(IdMixin, CompanyMixin, Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        CheckConstraint(
            "status in ('uploaded','validated','partially_imported','imported','failed','cancelled')",
            name="status_valid",
        ),
    )

    entity: Mapped[str] = mapped_column(String(40))
    filename: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    column_mapping: Mapped[dict] = mapped_column(JsonType, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    total_rows: Mapped[int] = mapped_column(default=0)
    valid_rows: Mapped[int] = mapped_column(default=0)
    invalid_rows: Mapped[int] = mapped_column(default=0)
    imported_rows: Mapped[int] = mapped_column(default=0)
    opening_batch_id: Mapped[int | None] = mapped_column(ForeignKey("opening_balance_batches.id"))
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rows: Mapped[list["ImportRow"]] = relationship(cascade="all, delete-orphan", order_by="ImportRow.row_number")


class ImportRow(IdMixin, Base):
    __tablename__ = "import_rows"
    __table_args__ = (
        CheckConstraint("status in ('pending','valid','invalid','imported','rejected')", name="status_valid"),
        Index("ix_import_rows_job_status", "job_id", "status"),
    )

    job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id", ondelete="CASCADE"))
    row_number: Mapped[int] = mapped_column()
    data: Mapped[dict] = mapped_column(JsonType)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    errors: Mapped[list] = mapped_column(JsonType, default=list)
    created_entity_id: Mapped[int | None] = mapped_column()


class OpeningBalanceBatch(IdMixin, CompanyMixin, Base):
    """Saldos iniciales: documentan fecha de corte, origen y aprobación responsable antes de contabilizarse."""

    __tablename__ = "opening_balance_batches"
    __table_args__ = (
        CheckConstraint("kind in ('stock','receivables','payables','gl')", name="kind_valid"),
        CheckConstraint("status in ('draft','approved','posted','cancelled')", name="status_valid"),
    )

    kind: Mapped[str] = mapped_column(String(12))
    cutoff_date: Mapped[date] = mapped_column(Date)
    source_description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="draft")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
