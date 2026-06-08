"""notices_and_lawyers

Revision ID: d4e5f6a7b8c9
Revises: c5d3e2f1a0b9
Create Date: 2026-06-03 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c5d3e2f1a0b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column(
            "scope",
            sa.Enum("university", "dept", "batch", name="noticescope"),
            nullable=False,
        ),
        sa.Column("dept", sa.String(length=100), nullable=True),
        sa.Column("batch", sa.String(length=20), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notices_tenant_id"), "notices", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_notices_scope"), "notices", ["scope"], unique=False)
    op.create_index(op.f("ix_notices_dept"), "notices", ["dept"], unique=False)
    op.create_index(op.f("ix_notices_batch"), "notices", ["batch"], unique=False)

    op.create_table(
        "lawyers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("bar_number", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("district", sa.String(length=100), nullable=True),
        sa.Column("specializations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lawyers_bar_number"), "lawyers", ["bar_number"], unique=True)
    op.create_index(op.f("ix_lawyers_district"), "lawyers", ["district"], unique=False)
    op.create_index(op.f("ix_lawyers_verified"), "lawyers", ["verified"], unique=False)
    op.create_index(op.f("ix_lawyers_tenant_id"), "lawyers", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_lawyers_tenant_id"), "lawyers")
    op.drop_index(op.f("ix_lawyers_verified"), "lawyers")
    op.drop_index(op.f("ix_lawyers_district"), "lawyers")
    op.drop_index(op.f("ix_lawyers_bar_number"), "lawyers")
    op.drop_table("lawyers")

    op.drop_index(op.f("ix_notices_batch"), "notices")
    op.drop_index(op.f("ix_notices_dept"), "notices")
    op.drop_index(op.f("ix_notices_scope"), "notices")
    op.drop_index(op.f("ix_notices_tenant_id"), "notices")
    op.drop_table("notices")
    op.execute("DROP TYPE IF EXISTS noticescope")
