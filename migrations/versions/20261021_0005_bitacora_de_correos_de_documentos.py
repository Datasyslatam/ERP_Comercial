"""bitacora de correos de documentos

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-21 15:53:45.836471+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table('document_emails',
    sa.Column('doc_type', sa.String(length=30), nullable=False),
    sa.Column('doc_id', sa.BigInteger(), nullable=False),
    sa.Column('doc_number', sa.String(length=60), nullable=False),
    sa.Column('to_addresses', sa.String(length=1000), nullable=False),
    sa.Column('cc_addresses', sa.String(length=1000), nullable=True),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('attempts', sa.BigInteger(), nullable=False),
    sa.Column('message_id', sa.String(length=255), nullable=True),
    sa.Column('created_by_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('company_id', sa.BigInteger(), nullable=False),
    sa.CheckConstraint("status in ('queued','sent','failed')", name=op.f('ck_document_emails_status_valid')),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('fk_document_emails_company_id_companies')),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_document_emails_created_by_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_emails'))
    )
    op.create_index(op.f('ix_document_emails_company_id'), 'document_emails', ['company_id'], unique=False)
    op.create_index('ix_document_emails_doc', 'document_emails', ['doc_type', 'doc_id'], unique=False)



def downgrade() -> None:

    op.drop_index('ix_document_emails_doc', table_name='document_emails')
    op.drop_index(op.f('ix_document_emails_company_id'), table_name='document_emails')
    op.drop_table('document_emails')

