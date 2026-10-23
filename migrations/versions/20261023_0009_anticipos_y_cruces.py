"""anticipos y cruces

Cruce de anticipos (saldos a favor del tercero) contra facturas. Las cuentas de anticipos de clientes y a
proveedores se crean en cada empresa al arrancar (python -m app.cli init).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-23 09:00:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'advance_applications',
        sa.Column('advance_item_id', sa.BigInteger(), nullable=False),
        sa.Column('open_item_id', sa.BigInteger(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('application_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=8), nullable=False),
        sa.Column('journal_entry_id', sa.BigInteger(), nullable=True),
        sa.Column('created_by_id', sa.BigInteger(), nullable=True),
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('company_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('amount > 0', name=op.f('ck_advance_applications_amount_positive')),
        sa.CheckConstraint("status in ('posted','voided')", name=op.f('ck_advance_applications_status_valid')),
        sa.ForeignKeyConstraint(['advance_item_id'], ['open_items.id'],
                                name=op.f('fk_advance_applications_advance_item_id_open_items')),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'],
                                name=op.f('fk_advance_applications_company_id_companies')),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_advance_applications_created_by_id_users')),
        sa.ForeignKeyConstraint(['journal_entry_id'], ['journal_entries.id'],
                                name=op.f('fk_advance_applications_journal_entry_id_journal_entries')),
        sa.ForeignKeyConstraint(['open_item_id'], ['open_items.id'],
                                name=op.f('fk_advance_applications_open_item_id_open_items')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_advance_applications')),
    )
    op.create_index(op.f('ix_advance_applications_advance_item_id'), 'advance_applications', ['advance_item_id'])
    op.create_index(op.f('ix_advance_applications_open_item_id'), 'advance_applications', ['open_item_id'])
    op.create_index(op.f('ix_advance_applications_company_id'), 'advance_applications', ['company_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_advance_applications_company_id'), table_name='advance_applications')
    op.drop_index(op.f('ix_advance_applications_open_item_id'), table_name='advance_applications')
    op.drop_index(op.f('ix_advance_applications_advance_item_id'), table_name='advance_applications')
    op.drop_table('advance_applications')
