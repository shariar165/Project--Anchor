"""legal_rights table

Revision ID: 2c2d3bac39c1
Revises: e1f2a3b4c5d6
Create Date: 2026-06-17 03:09:08.375032
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '2c2d3bac39c1'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'legal_rights',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('category', sa.String(length=40), nullable=False),
        sa.Column('title_en', sa.String(length=200), nullable=False),
        sa.Column('title_bn', sa.String(length=200), nullable=True),
        sa.Column('summary_en', sa.Text(), nullable=False),
        sa.Column('summary_bn', sa.Text(), nullable=True),
        sa.Column('full_text_en', sa.Text(), nullable=False),
        sa.Column('full_text_bn', sa.Text(), nullable=True),
        sa.Column('penalty_en', sa.Text(), nullable=True),
        sa.Column('penalty_bn', sa.Text(), nullable=True),
        sa.Column('where_to_invoke_en', sa.Text(), nullable=True),
        sa.Column('where_to_invoke_bn', sa.Text(), nullable=True),
        sa.Column('citation', sa.String(length=200), nullable=False),
        sa.Column('steps', sa.JSON(), nullable=False),
        sa.Column('illustration', sa.String(length=40), nullable=False),
        sa.Column('accent', sa.String(length=9), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('published', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_legal_rights_category'), 'legal_rights', ['category'], unique=False)
    op.create_index(op.f('ix_legal_rights_published'), 'legal_rights', ['published'], unique=False)
    op.create_index(op.f('ix_legal_rights_tenant_id'), 'legal_rights', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_legal_rights_tenant_id'), table_name='legal_rights')
    op.drop_index(op.f('ix_legal_rights_published'), table_name='legal_rights')
    op.drop_index(op.f('ix_legal_rights_category'), table_name='legal_rights')
    op.drop_table('legal_rights')
