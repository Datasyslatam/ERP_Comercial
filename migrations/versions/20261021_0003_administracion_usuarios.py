"""Administración de usuarios y roles: roles propios por empresa, vigencia y trazabilidad de asignaciones,
cambio obligatorio de contraseña y datos de contacto del usuario.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("job_title", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(length=40), nullable=True))
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), server_default=sa.text("false"),
                                     nullable=False))

    op.add_column("roles", sa.Column("company_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(op.f("fk_roles_company_id_companies"), "roles", "companies", ["company_id"], ["id"])
    op.create_index(op.f("ix_roles_company_id"), "roles", ["company_id"])
    op.drop_constraint("uq_roles_code", "roles", type_="unique")
    op.create_index("uq_roles_system_code", "roles", ["code"], unique=True,
                    postgresql_where=sa.text("company_id is null"))
    op.create_index("uq_roles_company_code", "roles", ["company_id", "code"], unique=True,
                    postgresql_where=sa.text("company_id is not null"))

    op.add_column("user_company_roles", sa.Column("expires_on", sa.Date(), nullable=True))
    op.add_column("user_company_roles", sa.Column("granted_by_id", sa.BigInteger(), nullable=True))
    op.add_column("user_company_roles", sa.Column("granted_at", sa.DateTime(timezone=True),
                                                  server_default=sa.text("now()"), nullable=True))
    op.add_column("user_company_roles", sa.Column("note", sa.String(length=255), nullable=True))
    # Las asignaciones previas no tienen fecha ni autor conocidos: no se les atribuye la fecha de la migración.
    op.execute("update user_company_roles set granted_at = null")
    op.create_foreign_key(op.f("fk_user_company_roles_granted_by_id_users"), "user_company_roles", "users",
                          ["granted_by_id"], ["id"])
    # La restricción única original no evita duplicados sin sede (NULL es distinto de NULL en PostgreSQL).
    op.create_index("uq_user_company_roles_no_site", "user_company_roles", ["user_id", "company_id", "role_id"],
                    unique=True, postgresql_where=sa.text("site_id is null"))


def downgrade() -> None:
    op.drop_index("uq_user_company_roles_no_site", table_name="user_company_roles")
    op.drop_constraint(op.f("fk_user_company_roles_granted_by_id_users"), "user_company_roles", type_="foreignkey")
    for col in ("note", "granted_at", "granted_by_id", "expires_on"):
        op.drop_column("user_company_roles", col)
    custom = "(select id from roles where company_id is not null)"
    for table in ("user_company_roles", "approval_limits", "role_permissions"):
        op.execute(f"delete from {table} where role_id in {custom}")
    op.execute("delete from roles where company_id is not null")
    op.drop_index("uq_roles_company_code", table_name="roles")
    op.drop_index("uq_roles_system_code", table_name="roles")
    op.create_unique_constraint("uq_roles_code", "roles", ["code"])
    op.drop_index(op.f("ix_roles_company_id"), table_name="roles")
    op.drop_constraint(op.f("fk_roles_company_id_companies"), "roles", type_="foreignkey")
    op.drop_column("roles", "company_id")
    for col in ("must_change_password", "phone", "job_title"):
        op.drop_column("users", col)
