"""comprobante de retencion en pagos

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-22 16:46:56.872304+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.add_column('payment_withholdings', sa.Column('certificate_number', sa.String(length=30), nullable=True))



def downgrade() -> None:

    op.drop_column('payment_withholdings', 'certificate_number')

