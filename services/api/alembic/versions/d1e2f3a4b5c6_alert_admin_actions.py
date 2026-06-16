"""alert admin actions — dispatch / notify-university / anonymous-call log

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-06-16 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c0d1e2f3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'alert_admin_actions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('event_id', sa.Uuid(),
                  sa.ForeignKey('alert_events.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('action_type',
                  sa.Enum('dispatch', 'notify_university', 'anonymous_call',
                          name='alertactiontype'),
                  nullable=False),
        sa.Column('actor_user_id', sa.Uuid(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'),
                  nullable=True, index=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table('alert_admin_actions')
    # Drop the enum type on PostgreSQL (no-op on SQLite, which has no enum types)
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        sa.Enum(name='alertactiontype').drop(bind, checkfirst=True)
