"""datos fiscales de facturas de proveedor

Número de control de la factura del proveedor (Venezuela) y comprobante de retención practicado al causar.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-22 20:30:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('supplier_invoices', sa.Column('supplier_control_number', sa.String(length=40), nullable=True))
    op.add_column('supplier_invoice_taxes', sa.Column('certificate_number', sa.String(length=30), nullable=True))
    op.add_column('supplier_invoice_taxes', sa.Column('certificate_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('supplier_invoice_taxes', 'certificate_date')
    op.drop_column('supplier_invoice_taxes', 'certificate_number')
    op.drop_column('supplier_invoices', 'supplier_control_number')
