"""fir_gd_and_officer_scorecards

National-mode features: police report (GD/FIR) drafting + officer scorecard
(police station / officer directory with moderated public ratings).

All status/type fields are plain String columns (no PG enums) — no ALTER TYPE
needed and the SQLite test path works unchanged.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-06-23 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── police_reports (GD / FIR drafting) ────────────────────────────────────
    op.create_table(
        "police_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("report_type", sa.String(length=8), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("reference_no", sa.String(length=40), nullable=True),
        sa.Column("complainant_name", sa.String(length=200), nullable=True),
        sa.Column("guardian_name", sa.String(length=200), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("nid", sa.String(length=40), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("subject", sa.String(length=300), nullable=True),
        sa.Column("incident_type", sa.String(length=40), nullable=True),
        sa.Column("incident_datetime", sa.String(length=120), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("thana", sa.String(length=200), nullable=True),
        sa.Column("district", sa.String(length=100), nullable=True),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("accused_details", sa.Text(), nullable=True),
        sa.Column("witnesses", sa.Text(), nullable=True),
        sa.Column("property_details", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=2), nullable=False, server_default="en"),
        sa.Column("ai_assisted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_police_reports_user_id", "police_reports", ["user_id"])
    op.create_index("ix_police_reports_state", "police_reports", ["state"])
    op.create_index("ix_police_reports_reference_no", "police_reports", ["reference_no"])

    # ── police_stations (thana directory) ─────────────────────────────────────
    op.create_table(
        "police_stations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=False),
        sa.Column("division", sa.String(length=100), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "district", name="uq_police_station_name_district"),
    )
    op.create_index("ix_police_stations_name", "police_stations", ["name"])
    op.create_index("ix_police_stations_district", "police_stations", ["district"])

    # ── officers ──────────────────────────────────────────────────────────────
    op.create_table(
        "officers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("station_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("rank", sa.String(length=100), nullable=True),
        sa.Column("badge_no", sa.String(length=60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["station_id"], ["police_stations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_officers_station_id", "officers", ["station_id"])

    # ── officer_ratings (moderated public ratings) ────────────────────────────
    op.create_table(
        "officer_ratings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rater_user_id", sa.Uuid(), nullable=False),
        sa.Column("station_id", sa.Uuid(), nullable=False),
        sa.Column("officer_id", sa.Uuid(), nullable=True),
        sa.Column("responsiveness", sa.Integer(), nullable=False),
        sa.Column("conduct", sa.Integer(), nullable=False),
        sa.Column("integrity", sa.Integer(), nullable=False),
        sa.Column("overall", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("anonymous", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moderated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["rater_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["station_id"], ["police_stations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["officer_id"], ["officers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["moderated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rater_user_id", "station_id", "officer_id", name="uq_officer_rating_per_user"),
    )
    op.create_index("ix_officer_ratings_rater_user_id", "officer_ratings", ["rater_user_id"])
    op.create_index("ix_officer_ratings_station_id", "officer_ratings", ["station_id"])
    op.create_index("ix_officer_ratings_officer_id", "officer_ratings", ["officer_id"])
    op.create_index("ix_officer_ratings_status", "officer_ratings", ["status"])


def downgrade() -> None:
    op.drop_index("ix_officer_ratings_status", "officer_ratings")
    op.drop_index("ix_officer_ratings_officer_id", "officer_ratings")
    op.drop_index("ix_officer_ratings_station_id", "officer_ratings")
    op.drop_index("ix_officer_ratings_rater_user_id", "officer_ratings")
    op.drop_table("officer_ratings")

    op.drop_index("ix_officers_station_id", "officers")
    op.drop_table("officers")

    op.drop_index("ix_police_stations_district", "police_stations")
    op.drop_index("ix_police_stations_name", "police_stations")
    op.drop_table("police_stations")

    op.drop_index("ix_police_reports_reference_no", "police_reports")
    op.drop_index("ix_police_reports_state", "police_reports")
    op.drop_index("ix_police_reports_user_id", "police_reports")
    op.drop_table("police_reports")
