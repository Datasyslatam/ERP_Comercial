"""listas de precios y promociones

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-22 15:48:56.498835+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table('price_lists',
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_to', sa.Date(), nullable=True),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('company_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('valid_to is null or valid_to >= valid_from', name=op.f('ck_price_lists_validity_valid')),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('fk_price_lists_company_id_companies')),
    sa.ForeignKeyConstraint(['currency'], ['currencies.code'], name=op.f('fk_price_lists_currency_currencies')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_price_lists')),
    sa.UniqueConstraint('company_id', 'code', name=op.f('uq_price_lists_company_id_code'))
    )
    op.create_index(op.f('ix_price_lists_company_id'), 'price_lists', ['company_id'], unique=False)
    op.create_index('uq_price_lists_default', 'price_lists', ['company_id', 'currency'], unique=True,
                    postgresql_where=sa.text('is_default'))
    op.create_table('price_list_items',
    sa.Column('price_list_id', sa.BigInteger(), nullable=False),
    sa.Column('item_id', sa.BigInteger(), nullable=False),
    sa.Column('min_qty', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.CheckConstraint('unit_price >= 0 and min_qty > 0', name=op.f('ck_price_list_items_values_valid')),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], name=op.f('fk_price_list_items_item_id_items')),
    sa.ForeignKeyConstraint(['price_list_id'], ['price_lists.id'], name=op.f('fk_price_list_items_price_list_id_price_lists'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_price_list_items')),
    sa.UniqueConstraint('price_list_id', 'item_id', 'min_qty', name=op.f('uq_price_list_items_price_list_id_item_id_min_qty'))
    )
    op.create_index(op.f('ix_price_list_items_item_id'), 'price_list_items', ['item_id'], unique=False)
    op.create_index(op.f('ix_price_list_items_price_list_id'), 'price_list_items', ['price_list_id'], unique=False)
    op.create_table('promotions',
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('discount_pct', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_to', sa.Date(), nullable=False),
    sa.Column('item_id', sa.BigInteger(), nullable=True),
    sa.Column('category_id', sa.BigInteger(), nullable=True),
    sa.Column('customer_id', sa.BigInteger(), nullable=True),
    sa.Column('min_qty', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('company_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('discount_pct > 0 and discount_pct <= 100', name=op.f('ck_promotions_discount_valid')),
    sa.CheckConstraint('item_id is null or category_id is null', name=op.f('ck_promotions_single_scope')),
    sa.CheckConstraint('valid_to >= valid_from', name=op.f('ck_promotions_validity_valid')),
    sa.ForeignKeyConstraint(['category_id'], ['item_categories.id'], name=op.f('fk_promotions_category_id_item_categories')),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('fk_promotions_company_id_companies')),
    sa.ForeignKeyConstraint(['customer_id'], ['parties.id'], name=op.f('fk_promotions_customer_id_parties')),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], name=op.f('fk_promotions_item_id_items')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_promotions')),
    sa.UniqueConstraint('company_id', 'code', name=op.f('uq_promotions_company_id_code'))
    )
    op.create_index(op.f('ix_promotions_company_id'), 'promotions', ['company_id'], unique=False)
    op.add_column('parties', sa.Column('price_list_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(op.f('fk_parties_price_list_id_price_lists'), 'parties', 'price_lists', ['price_list_id'], ['id'])
    op.add_column('sales_order_lines', sa.Column('price_source', sa.String(length=12), nullable=True))
    op.add_column('sales_order_lines', sa.Column('promotion_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(op.f('fk_sales_order_lines_promotion_id_promotions'), 'sales_order_lines', 'promotions', ['promotion_id'], ['id'])
    op.add_column('sales_quote_lines', sa.Column('price_source', sa.String(length=12), nullable=True))
    op.add_column('sales_quote_lines', sa.Column('promotion_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(op.f('fk_sales_quote_lines_promotion_id_promotions'), 'sales_quote_lines', 'promotions', ['promotion_id'], ['id'])



def downgrade() -> None:

    op.drop_constraint(op.f('fk_sales_quote_lines_promotion_id_promotions'), 'sales_quote_lines', type_='foreignkey')
    op.drop_column('sales_quote_lines', 'promotion_id')
    op.drop_column('sales_quote_lines', 'price_source')
    op.drop_constraint(op.f('fk_sales_order_lines_promotion_id_promotions'), 'sales_order_lines', type_='foreignkey')
    op.drop_column('sales_order_lines', 'promotion_id')
    op.drop_column('sales_order_lines', 'price_source')
    op.drop_constraint(op.f('fk_parties_price_list_id_price_lists'), 'parties', type_='foreignkey')
    op.drop_column('parties', 'price_list_id')
    op.drop_index(op.f('ix_promotions_company_id'), table_name='promotions')
    op.drop_table('promotions')
    op.drop_index(op.f('ix_price_list_items_price_list_id'), table_name='price_list_items')
    op.drop_index(op.f('ix_price_list_items_item_id'), table_name='price_list_items')
    op.drop_table('price_list_items')
    op.drop_index('uq_price_lists_default', table_name='price_lists')
    op.drop_index(op.f('ix_price_lists_company_id'), table_name='price_lists')
    op.drop_table('price_lists')

