"""zones.radius_m — allow NULL for polygon zones

Revision ID: b1c2d3e4f5a6
Revises: a8b3c4d5e6f7
Create Date: 2026-06-10 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a8b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('zones', 'radius_m', nullable=True, existing_type=sa.Integer())


def downgrade() -> None:
    # Only safe if all existing rows have a non-null radius_m
    op.alter_column('zones', 'radius_m', nullable=False, existing_type=sa.Integer())
