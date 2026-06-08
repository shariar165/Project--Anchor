"""routine_notice_status_dept_rating

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-03 14:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # op.add_column does NOT auto-create named enum types in PostgreSQL.
    # Create noticestatus explicitly before adding the column.
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            "DO $$ BEGIN "
            "CREATE TYPE noticestatus AS ENUM ('draft', 'published', 'archived'); "
            "EXCEPTION WHEN duplicate_object THEN null; "
            "END $$"
        ))

    # ── notices: add status + published_at columns ────────────────────────────
    op.add_column(
        "notices",
        sa.Column(
            "status",
            sa.Enum("draft", "published", "archived", name="noticestatus", create_type=False),
            server_default="published",
            nullable=False,
        ),
    )
    op.add_column(
        "notices",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notices_status", "notices", ["status"], unique=False)

    # ── academic_routines ─────────────────────────────────────────────────────
    op.create_table(
        "academic_routines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("department", sa.String(length=200), nullable=True),
        sa.Column("batch", sa.String(length=50), nullable=True),
        sa.Column("semester", sa.String(length=100), nullable=True),
        sa.Column("academic_year", sa.String(length=20), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slots", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "status",
            sa.Enum("draft", "published", "archived", name="routinestatus"),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_academic_routines_tenant_id", "academic_routines", ["tenant_id"])
    op.create_index("ix_academic_routines_department", "academic_routines", ["department"])
    op.create_index("ix_academic_routines_batch", "academic_routines", ["batch"])
    op.create_index("ix_academic_routines_status", "academic_routines", ["status"])

    # ── department_ratings ────────────────────────────────────────────────────
    op.create_table(
        "department_ratings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rater_user_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("department", sa.String(length=200), nullable=False),
        sa.Column("period", sa.String(length=50), nullable=False),
        sa.Column("overall", sa.Integer(), nullable=False),
        sa.Column("teaching_quality", sa.Integer(), nullable=True),
        sa.Column("resources", sa.Integer(), nullable=True),
        sa.Column("environment", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("anonymous", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["rater_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rater_user_id", "department", "period", name="uq_dept_rating_per_period"),
    )
    op.create_index("ix_department_ratings_rater_user_id", "department_ratings", ["rater_user_id"])
    op.create_index("ix_department_ratings_tenant_id", "department_ratings", ["tenant_id"])
    op.create_index("ix_department_ratings_department", "department_ratings", ["department"])


def downgrade() -> None:
    op.drop_index("ix_department_ratings_department", "department_ratings")
    op.drop_index("ix_department_ratings_tenant_id", "department_ratings")
    op.drop_index("ix_department_ratings_rater_user_id", "department_ratings")
    op.drop_table("department_ratings")

    op.drop_index("ix_academic_routines_status", "academic_routines")
    op.drop_index("ix_academic_routines_batch", "academic_routines")
    op.drop_index("ix_academic_routines_department", "academic_routines")
    op.drop_index("ix_academic_routines_tenant_id", "academic_routines")
    op.drop_table("academic_routines")
    op.execute("DROP TYPE IF EXISTS routinestatus")

    op.drop_index("ix_notices_status", "notices")
    op.drop_column("notices", "published_at")
    op.drop_column("notices", "status")
    op.execute("DROP TYPE IF EXISTS noticestatus")
