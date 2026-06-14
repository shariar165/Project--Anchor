"""add super_admin role

Revision ID: f0a1b2c3d4e5
Revises: e5f6a7b8c9d0
Create Date: 2026-06-04 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f0a1b2c3d4e5'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text("ALTER TYPE role ADD VALUE IF NOT EXISTS 'super_admin'"))


def downgrade() -> None:
    # PostgreSQL cannot remove enum values without dropping and recreating the type.
    # Downgrade is intentionally left as a no-op.
    pass
