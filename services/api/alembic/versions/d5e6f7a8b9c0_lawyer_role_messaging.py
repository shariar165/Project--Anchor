"""lawyer role, lawyer account linkage, and E2EE messaging

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-06-23 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add the `lawyer` value to the Postgres role enum (no-op on SQLite, which
    #    uses the string-based Python enum). Mirrors the super_admin migration.
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text("ALTER TYPE role ADD VALUE IF NOT EXISTS 'lawyer'"))

    # 2. Lawyer account linkage + application workflow columns.
    op.add_column('lawyers', sa.Column('user_id', sa.Uuid(), nullable=True))
    op.add_column('lawyers', sa.Column('status', sa.String(length=20), server_default='pending', nullable=False))
    op.add_column('lawyers', sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('lawyers', sa.Column('verified_by', sa.Uuid(), nullable=True))
    op.add_column('lawyers', sa.Column('rejection_reason', sa.Text(), nullable=True))
    op.create_index(op.f('ix_lawyers_user_id'), 'lawyers', ['user_id'], unique=True)
    op.create_index(op.f('ix_lawyers_status'), 'lawyers', ['status'], unique=False)
    op.create_foreign_key(
        'fk_lawyers_user_id', 'lawyers', 'users', ['user_id'], ['id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_lawyers_verified_by', 'lawyers', 'users', ['verified_by'], ['id'],
    )
    # Existing directory-only rows that were already verified keep status in sync.
    op.execute("UPDATE lawyers SET status = 'verified' WHERE verified = true")

    # 3. E2EE direct-message tables (server stores ciphertext only).
    op.create_table(
        'conversations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('lawyer_user_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lawyer_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'lawyer_user_id', name='uq_conversation_pair'),
    )
    op.create_index(op.f('ix_conversations_user_id'), 'conversations', ['user_id'], unique=False)
    op.create_index(op.f('ix_conversations_lawyer_user_id'), 'conversations', ['lawyer_user_id'], unique=False)

    op.create_table(
        'messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.Column('sender_id', sa.Uuid(), nullable=False),
        sa.Column('ciphertext', sa.Text(), nullable=False),
        sa.Column('iv', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_messages_created_at'), 'messages', ['created_at'], unique=False)
    op.create_index('ix_messages_conversation_created', 'messages', ['conversation_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_messages_conversation_created', table_name='messages')
    op.drop_index(op.f('ix_messages_created_at'), table_name='messages')
    op.drop_index(op.f('ix_messages_conversation_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_conversations_lawyer_user_id'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_user_id'), table_name='conversations')
    op.drop_table('conversations')

    op.drop_constraint('fk_lawyers_verified_by', 'lawyers', type_='foreignkey')
    op.drop_constraint('fk_lawyers_user_id', 'lawyers', type_='foreignkey')
    op.drop_index(op.f('ix_lawyers_status'), table_name='lawyers')
    op.drop_index(op.f('ix_lawyers_user_id'), table_name='lawyers')
    op.drop_column('lawyers', 'rejection_reason')
    op.drop_column('lawyers', 'verified_by')
    op.drop_column('lawyers', 'verified_at')
    op.drop_column('lawyers', 'status')
    op.drop_column('lawyers', 'user_id')
    # The `lawyer` enum value is intentionally left in place (Postgres cannot drop enum values).
