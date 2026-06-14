"""unified_zones — extend zone types + polygon support

Revision ID: a8b3c4d5e6f7
Revises: 37afe0ddaa21
Create Date: 2026-06-10 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a8b3c4d5e6f7'
down_revision: Union[str, None] = '37afe0ddaa21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Extend the ZoneType enum in PostgreSQL (no-op for SQLite — strings are unconstrained)
    if conn.dialect.name == 'postgresql':
        for val in ('campus', 'purple', 'black', 'red'):
            conn.execute(sa.text(f"ALTER TYPE zonetype ADD VALUE IF NOT EXISTS '{val}'"))

    # Add new columns to zones table
    # shape_type: 'circle' (default — all existing zones are circles) or 'polygon'
    op.add_column('zones', sa.Column(
        'name', sa.String(200), nullable=True,
    ))
    op.add_column('zones', sa.Column(
        'shape_type', sa.String(20), nullable=False,
        server_default='circle',
    ))
    op.add_column('zones', sa.Column(
        'polygon_coords', sa.JSON(), nullable=True,
    ))
    op.add_column('zones', sa.Column(
        'created_by_id', sa.UUID(), nullable=True,
    ))
    op.add_column('zones', sa.Column(
        'created_by_role', sa.String(20), nullable=True,
    ))
    op.add_column('zones', sa.Column(
        'university_id', sa.UUID(), nullable=True,
    ))

    # Allow radius_m to be NULL for polygon zones (original migration created it NOT NULL)
    op.alter_column('zones', 'radius_m', nullable=True, existing_type=sa.Integer())

    # Indexes for common query patterns
    op.create_index('idx_zones_shape_type', 'zones', ['shape_type'])
    op.create_index('idx_zones_university', 'zones', ['university_id'])


def downgrade() -> None:
    op.drop_index('idx_zones_university', table_name='zones')
    op.drop_index('idx_zones_shape_type', table_name='zones')
    op.drop_column('zones', 'university_id')
    op.drop_column('zones', 'created_by_role')
    op.drop_column('zones', 'created_by_id')
    op.drop_column('zones', 'polygon_coords')
    op.drop_column('zones', 'shape_type')
    op.drop_column('zones', 'name')
    # Note: PostgreSQL enum values cannot be removed via ALTER TYPE DROP VALUE
    # in older Postgres versions. Downgrade leaves the enum values in place.
