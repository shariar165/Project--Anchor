"""alert_responder_location_and_live_tracking

Adds two-way live location to the alert system:
  - alert_responses.responder_user_id  — real responder identity (FK users, SET NULL)
    so we can push "victim is safe" notifications to responders.
  - alert_responses.responder_lat/lng  — responder's real position, shown on the
    alerting user's live map.
  - alert_events.location_updated_at    — set when the victim's live location is
    refreshed while an alert is active (responders follow a moving victim).

All columns are nullable with no backfill, so existing rows and the SQLite test
path are unaffected.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-06-25 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "alert_responses",
        sa.Column("responder_user_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "alert_responses",
        sa.Column("responder_lat", sa.Float(), nullable=True),
    )
    op.add_column(
        "alert_responses",
        sa.Column("responder_lng", sa.Float(), nullable=True),
    )
    op.create_index(
        "ix_alert_responses_responder_user_id",
        "alert_responses",
        ["responder_user_id"],
    )
    op.create_foreign_key(
        "fk_alert_responses_responder_user_id_users",
        "alert_responses",
        "users",
        ["responder_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "alert_events",
        sa.Column("location_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alert_events", "location_updated_at")
    op.drop_constraint(
        "fk_alert_responses_responder_user_id_users",
        "alert_responses",
        type_="foreignkey",
    )
    op.drop_index("ix_alert_responses_responder_user_id", table_name="alert_responses")
    op.drop_column("alert_responses", "responder_lng")
    op.drop_column("alert_responses", "responder_lat")
    op.drop_column("alert_responses", "responder_user_id")
