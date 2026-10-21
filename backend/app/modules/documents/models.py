"""Bitácora de envíos de documentos comerciales por correo."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, CompanyMixin, IdMixin


class DocumentEmail(IdMixin, CompanyMixin, Base):
    """Cada envío queda registrado con destinatarios, asunto, estado y error; el PDF se genera al enviar."""

    __tablename__ = "document_emails"
    __table_args__ = (
        CheckConstraint("status in ('queued','sent','failed')", name="status_valid"),
        Index("ix_document_emails_doc", "doc_type", "doc_id"),
    )

    doc_type: Mapped[str] = mapped_column(String(30))
    doc_id: Mapped[int] = mapped_column()
    doc_number: Mapped[str] = mapped_column(String(60))
    to_addresses: Mapped[str] = mapped_column(String(1000))
    cc_addresses: Mapped[str | None] = mapped_column(String(1000))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0)
    message_id: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
