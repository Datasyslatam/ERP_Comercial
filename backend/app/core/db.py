"""Motor, sesión y clase base del ORM."""
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, MetaData, Numeric, create_engine, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import get_settings

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Tipos numéricos estándar: dinero, cantidades, costos unitarios y tasas.
Money = Numeric(18, 2)
Qty = Numeric(18, 6)
UnitCost = Numeric(18, 6)
Rate = Numeric(20, 8)
JsonType = JSONB


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map = {Decimal: Money, int: BigInteger}


class IdMixin:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CompanyMixin:
    """Todo registro transaccional pertenece a una empresa (aislamiento multiempresa)."""

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)


class AuthorMixin:
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


settings = get_settings()
engine = create_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
