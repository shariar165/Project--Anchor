"""faculty profiles standalone: add name/email, make user_id nullable

Faculty become first-class scheduling entities. They carry their own name and
email so a roster can be bulk-imported without every teacher having a login
account; user_id now links an account only when one exists.

Revision ID: b3c4d5e6f7a8
Revises: a9b1c2d3e4f5
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa


revision = "b3c4d5e6f7a8"
down_revision = "a9b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tt_faculty_profiles", sa.Column("name", sa.String(length=120), nullable=True))
    op.add_column("tt_faculty_profiles", sa.Column("email", sa.String(length=255), nullable=True))
    op.create_index("ix_tt_faculty_profiles_email", "tt_faculty_profiles", ["email"])
    op.alter_column("tt_faculty_profiles", "user_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.alter_column("tt_faculty_profiles", "user_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_index("ix_tt_faculty_profiles_email", table_name="tt_faculty_profiles")
    op.drop_column("tt_faculty_profiles", "email")
    op.drop_column("tt_faculty_profiles", "name")
