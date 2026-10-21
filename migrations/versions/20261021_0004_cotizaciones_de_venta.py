"""cotizaciones de venta

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-21 14:41:08.769470+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table('sales_quotes',
    sa.Column('number', sa.String(length=30), nullable=False),
    sa.Column('site_id', sa.BigInteger(), nullable=False),
    sa.Column('customer_id', sa.BigInteger(), nullable=False),
    sa.Column('quote_date', sa.Date(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('payment_term_id', sa.BigInteger(), nullable=True),
    sa.Column('contact_name', sa.String(length=120), nullable=True),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('tax_total', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('total', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('lost_reason', sa.String(length=255), nullable=True),
    sa.Column('sales_order_id', sa.BigInteger(), nullable=True),
    sa.Column('created_by_id', sa.BigInteger(), nullable=True),
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('company_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status in ('draft','sent','accepted','rejected','cancelled')", name=op.f('ck_sales_quotes_status_valid')),
    sa.CheckConstraint('valid_until >= quote_date', name=op.f('ck_sales_quotes_validity_valid')),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('fk_sales_quotes_company_id_companies')),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_sales_quotes_created_by_id_users')),
    sa.ForeignKeyConstraint(['currency'], ['currencies.code'], name=op.f('fk_sales_quotes_currency_currencies')),
    sa.ForeignKeyConstraint(['customer_id'], ['parties.id'], name=op.f('fk_sales_quotes_customer_id_parties')),
    sa.ForeignKeyConstraint(['payment_term_id'], ['payment_terms.id'], name=op.f('fk_sales_quotes_payment_term_id_payment_terms')),
    sa.ForeignKeyConstraint(['sales_order_id'], ['sales_orders.id'], name=op.f('fk_sales_quotes_sales_order_id_sales_orders')),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_sales_quotes_site_id_sites')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sales_quotes')),
    sa.UniqueConstraint('company_id', 'number', name=op.f('uq_sales_quotes_company_id_number'))
    )
    op.create_index(op.f('ix_sales_quotes_company_id'), 'sales_quotes', ['company_id'], unique=False)
    op.create_index(op.f('ix_sales_quotes_customer_id'), 'sales_quotes', ['customer_id'], unique=False)
    op.create_index(op.f('ix_sales_quotes_sales_order_id'), 'sales_quotes', ['sales_order_id'], unique=False)
    op.create_table('sales_quote_lines',
    sa.Column('quote_id', sa.BigInteger(), nullable=False),
    sa.Column('line_no', sa.BigInteger(), nullable=False),
    sa.Column('item_id', sa.BigInteger(), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('quantity', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('discount_pct', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('tax_id', sa.BigInteger(), nullable=True),
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.CheckConstraint('discount_pct >= 0 and discount_pct <= 100', name=op.f('ck_sales_quote_lines_discount_valid')),
    sa.CheckConstraint('quantity > 0 and unit_price >= 0', name=op.f('ck_sales_quote_lines_values_valid')),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], name=op.f('fk_sales_quote_lines_item_id_items')),
    sa.ForeignKeyConstraint(['quote_id'], ['sales_quotes.id'], name=op.f('fk_sales_quote_lines_quote_id_sales_quotes'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tax_id'], ['taxes.id'], name=op.f('fk_sales_quote_lines_tax_id_taxes')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sales_quote_lines')),
    sa.UniqueConstraint('quote_id', 'line_no', name=op.f('uq_sales_quote_lines_quote_id_line_no'))
    )
    op.create_index(op.f('ix_sales_quote_lines_quote_id'), 'sales_quote_lines', ['quote_id'], unique=False)



def downgrade() -> None:

    op.drop_index(op.f('ix_sales_quote_lines_quote_id'), table_name='sales_quote_lines')
    op.drop_table('sales_quote_lines')
    op.drop_index(op.f('ix_sales_quotes_sales_order_id'), table_name='sales_quotes')
    op.drop_index(op.f('ix_sales_quotes_customer_id'), table_name='sales_quotes')
    op.drop_index(op.f('ix_sales_quotes_company_id'), table_name='sales_quotes')
    op.drop_table('sales_quotes')

