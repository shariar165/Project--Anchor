"""tenant admin fields

Revision ID: f1a2b3c4d5e6
Revises: 2c2d3bac39c1
Create Date: 2026-06-20 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = '2c2d3bac39c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column('tier', sa.String(length=20), server_default='active', nullable=False))
    op.add_column('tenants', sa.Column('country', sa.String(length=100), server_default='Bangladesh', nullable=True))
    op.add_column('tenants', sa.Column('contact_name', sa.String(length=200), nullable=True))
    op.add_column('tenants', sa.Column('vector_namespace', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('tenants', 'vector_namespace')
    op.drop_column('tenants', 'contact_name')
    op.drop_column('tenants', 'country')
    op.drop_column('tenants', 'tier')
