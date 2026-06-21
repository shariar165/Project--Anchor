"""deanonymization requests

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-06-21 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'deanonymization_requests',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('request_number', sa.String(length=30), nullable=False),
        sa.Column('target_type', sa.String(length=20), nullable=False),
        sa.Column('target_id', sa.Uuid(), nullable=False),
        sa.Column('target_ref', sa.String(length=50), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=True),
        sa.Column('requester_user_id', sa.Uuid(), nullable=True),
        sa.Column('requester_label', sa.String(length=200), server_default='', nullable=False),
        sa.Column('legal_basis', sa.String(length=200), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('formal_letter_ref', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='pending_review', nullable=False),
        sa.Column('first_approver_user_id', sa.Uuid(), nullable=True),
        sa.Column('first_approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('second_approver_user_id', sa.Uuid(), nullable=True),
        sa.Column('second_approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('denied_by_user_id', sa.Uuid(), nullable=True),
        sa.Column('denied_reason', sa.Text(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('access_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['requester_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['first_approver_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['second_approver_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['denied_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_deanonymization_requests_request_number'), 'deanonymization_requests', ['request_number'], unique=True)
    op.create_index(op.f('ix_deanonymization_requests_target_id'), 'deanonymization_requests', ['target_id'], unique=False)
    op.create_index(op.f('ix_deanonymization_requests_tenant_id'), 'deanonymization_requests', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_deanonymization_requests_requester_user_id'), 'deanonymization_requests', ['requester_user_id'], unique=False)
    op.create_index(op.f('ix_deanonymization_requests_status'), 'deanonymization_requests', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_deanonymization_requests_status'), table_name='deanonymization_requests')
    op.drop_index(op.f('ix_deanonymization_requests_requester_user_id'), table_name='deanonymization_requests')
    op.drop_index(op.f('ix_deanonymization_requests_tenant_id'), table_name='deanonymization_requests')
    op.drop_index(op.f('ix_deanonymization_requests_target_id'), table_name='deanonymization_requests')
    op.drop_index(op.f('ix_deanonymization_requests_request_number'), table_name='deanonymization_requests')
    op.drop_table('deanonymization_requests')
