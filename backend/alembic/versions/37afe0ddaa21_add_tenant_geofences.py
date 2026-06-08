"""add_tenant_geofences

Revision ID: 37afe0ddaa21
Revises: f0a1b2c3d4e5
Create Date: 2026-06-06 23:34:25.609794
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '37afe0ddaa21'
down_revision: Union[str, None] = 'f0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tenant_geofences',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('vertices_json', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tenant_geofences_tenant_id'), 'tenant_geofences', ['tenant_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_tenant_geofences_tenant_id'), table_name='tenant_geofences')
    op.drop_table('tenant_geofences')
