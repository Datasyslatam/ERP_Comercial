"""Identidad, roles, permisos, sesiones y auditoría."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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

from app.core.db import Base, IdMixin, JsonType, TimestampMixin


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("uq_users_email_lower", func.lower(text("email")), unique=True),)

    email: Mapped[str] = mapped_column(String(254))
    full_name: Mapped[str] = mapped_column(String(200))
    job_title: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    external_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_count: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    assignments: Mapped[list["UserCompanyRole"]] = relationship(back_populates="user", cascade="all, delete-orphan",
                                                                foreign_keys="UserCompanyRole.user_id")


class Permission(IdMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(120), unique=True)
    module: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(255))


class Role(IdMixin, TimestampMixin, Base):
    """Roles del sistema (company_id nulo, comunes a todas las empresas) o propios de una empresa."""

    __tablename__ = "roles"
    __table_args__ = (
        Index("uq_roles_system_code", "code", unique=True, postgresql_where=text("company_id is null")),
        Index("uq_roles_company_code", "company_id", "code", unique=True,
              postgresql_where=text("company_id is not null")),
    )

    code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)

    permissions: Mapped[list[Permission]] = relationship(secondary="role_permissions", lazy="selectin")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class UserCompanyRole(IdMixin, Base):
    """Un usuario recibe roles por empresa; opcionalmente restringidos a una sede y con vigencia hasta una fecha
    (reemplazos por vacaciones, auditorías externas, accesos temporales)."""

    __tablename__ = "user_company_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", "role_id", "site_id"),
        Index("uq_user_company_roles_no_site", "user_id", "company_id", "role_id", unique=True,
              postgresql_where=text("site_id is null")),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"))
    expires_on: Mapped[date | None] = mapped_column(Date)
    granted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[User] = relationship(back_populates="assignments", foreign_keys=[user_id])
    role: Mapped[Role] = relationship(lazy="joined")

    def is_current(self, today: date) -> bool:
        return self.expires_on is None or self.expires_on >= today


class RefreshToken(IdMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))


class LoginAttempt(IdMixin, Base):
    __tablename__ = "login_attempts"

    email: Mapped[str] = mapped_column(String(254), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    ip: Mapped[str | None] = mapped_column(String(64))
    success: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AuditLog(IdMixin, Base):
    """Bitácora inmutable (protegida por trigger) de cambios y acciones sensibles."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"))
    ip: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(40))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    changes: Mapped[dict | None] = mapped_column(JsonType)
    summary: Mapped[str | None] = mapped_column(String(500))


class ApprovalLimit(IdMixin, TimestampMixin, Base):
    """Monto máximo (moneda funcional) que un rol puede aprobar por tipo de documento."""

    __tablename__ = "approval_limits"
    __table_args__ = (UniqueConstraint("company_id", "role_id", "document_type"),)

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    document_type: Mapped[str] = mapped_column(String(40))
    max_amount: Mapped[Decimal]
