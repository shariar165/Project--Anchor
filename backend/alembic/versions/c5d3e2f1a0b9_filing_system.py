"""filing_system

Revision ID: c5d3e2f1a0b9
Revises: b9f2a1c3d4e5
Create Date: 2026-06-02 12:00:00.000000
"""
import uuid
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c5d3e2f1a0b9'
down_revision: Union[str, None] = 'b9f2a1c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TEMPLATES = [
    # key, name, name_bn, category, anonymity_mode, routing_target, stepup, modq, proof_req, proof_hint, resp_window, esc_days
    ("academic_rank1",    "Normal feedback",                         "সাধারণ মতামত",                        "complaint",  "attributed", "dept_head", False, False, False, None,                                                              7, 7),
    ("academic_rank2",    "Professional conduct",                    "পেশাদার আচরণের অভিযোগ",               "complaint",  "attributed", "dept_head", False, False, False, "Describe specific incidents with dates.",                           7, 7),
    ("academic_rank3",    "Serious academic concern",                "গুরুতর শিক্ষা-সংক্রান্ত উদ্বেগ",       "complaint",  "anonymous",  "dean",      True,  True,  False, "Attach evidence if available — your identity stays protected.",    3, 3),
    ("dept_c1",           "Incident-based grievance",                "ঘটনা-ভিত্তিক অভিযোগ",                 "grievance",  "attributed", "dept_head", False, False, True,  "Attach a photo or document showing the issue.",                    7, 7),
    ("dept_c2",           "Semester rating",                         "সেমিস্টার রেটিং",                      "grievance",  "aggregated", "dept_head", False, False, False, None,                                                              7, 7),
    ("dept_c3",           "Department culture",                      "বিভাগীয় পরিবেশ",                      "grievance",  "anonymous",  "dean",      True,  True,  False, None,                                                              7, 7),
    ("classroom",         "Classroom condition",                     "শ্রেণীকক্ষের অবস্থা",                  "report",     "attributed", "dept_head", False, False, False, "A photo of the issue is helpful.",                                 7, 7),
    ("hall_tutor",        "Hall tutor report",                       "হল টিউটর রিপোর্ট",                    "report",     "attributed", "provost",   False, False, False, None,                                                              7, 7),
    ("hostel_incident",   "Hostel — seat / curfew / roommate",       "হোস্টেল অভিযোগ",                      "report",     "attributed", "provost",   False, False, False, None,                                                              7, 7),
    ("warden_misconduct", "Warden misconduct",                       "ওয়ার্ডেনের অসদাচরণ",                  "report",     "anonymous",  "provost",   True,  True,  False, "Anonymous report — your identity will be protected.",             7, 7),
]


def upgrade() -> None:
    op.create_table(
        "filing_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_bn", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("anonymity_mode", sa.String(length=20), nullable=False, server_default="attributed"),
        sa.Column("routing_target", sa.String(length=30), nullable=False, server_default="dept_head"),
        sa.Column("requires_stepup", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("goes_to_moderation_queue", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("proof_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("proof_hint", sa.String(length=500), nullable=True),
        sa.Column("subject_response_window_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("default_escalation_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_filing_templates_key"), "filing_templates", ["key"], unique=True)
    op.create_index(op.f("ix_filing_templates_category"), "filing_templates", ["category"], unique=False)

    op.create_table(
        "filings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filing_number", sa.String(length=30), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("complainant_user_id", sa.Uuid(), nullable=True),
        sa.Column("encrypted_actor_link", sa.LargeBinary(), nullable=True),
        sa.Column("anonymous_tracking_code", sa.String(length=20), nullable=True),
        sa.Column("subject_user_id", sa.Uuid(), nullable=True),
        sa.Column("subject_descriptor", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=2), nullable=False, server_default="en"),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("field_values", sa.JSON(), nullable=False),
        sa.Column("ai_assisted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("state", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("priority", sa.String(length=10), nullable=False, server_default="normal"),
        sa.Column("current_reviewer_user_id", sa.Uuid(), nullable=True),
        sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state_entered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_outcome_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["complainant_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["current_reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["template_id"], ["filing_templates.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("filing_number", name="uq_filing_number"),
        sa.UniqueConstraint("anonymous_tracking_code", name="uq_anonymous_tracking_code"),
    )
    op.create_index(op.f("ix_filings_complainant_user_id"), "filings", ["complainant_user_id"], unique=False)
    op.create_index(op.f("ix_filings_tenant_id"), "filings", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_filings_state"), "filings", ["state"], unique=False)
    op.create_index(op.f("ix_filings_category"), "filings", ["category"], unique=False)
    op.create_index(op.f("ix_filings_filing_number"), "filings", ["filing_number"], unique=True)
    op.create_index(op.f("ix_filings_anonymous_tracking_code"), "filings", ["anonymous_tracking_code"], unique=True)

    op.create_table(
        "filing_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filing_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("file_ref", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("explain_cache", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_filing_attachments_filing_id"), "filing_attachments", ["filing_id"], unique=False)

    op.create_table(
        "filing_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filing_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("reviewer_role", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("internal_note", sa.Text(), nullable=True),
        sa.Column("public_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_filing_reviews_filing_id"), "filing_reviews", ["filing_id"], unique=False)

    op.create_table(
        "subject_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filing_id", sa.Uuid(), nullable=False),
        sa.Column("subject_user_id", sa.Uuid(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_window_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_subject_responses_filing_id"), "subject_responses", ["filing_id"], unique=False)

    op.create_table(
        "classroom_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("classroom_ref", sa.String(length=100), nullable=False),
        sa.Column("issue_type", sa.String(length=20), nullable=False),
        sa.Column("reporter_user_id", sa.Uuid(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "classroom_ref", "issue_type", "reporter_user_id",
            name="uq_classroom_report_per_user",
        ),
    )
    op.create_index(op.f("ix_classroom_reports_tenant_id"), "classroom_reports", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_classroom_reports_classroom_ref"), "classroom_reports", ["classroom_ref"], unique=False)

    # Seed filing templates
    conn = op.get_bind()
    for (key, name, name_bn, category, anon, routing, stepup, modq, proof_req, proof_hint, resp_window, esc_days) in _TEMPLATES:
        conn.execute(sa.text(
            "INSERT INTO filing_templates "
            "(id, key, name, name_bn, category, anonymity_mode, routing_target, "
            "requires_stepup, goes_to_moderation_queue, proof_required, proof_hint, "
            "subject_response_window_days, default_escalation_days, active, created_at, updated_at) "
            "VALUES (:id, :key, :name, :name_bn, :category, :anon, :routing, "
            ":stepup, :modq, :proof_req, :proof_hint, :resp_window, :esc_days, true, now(), now())"
        ), {
            "id": str(uuid.uuid4()),
            "key": key,
            "name": name,
            "name_bn": name_bn,
            "category": category,
            "anon": anon,
            "routing": routing,
            "stepup": stepup,
            "modq": modq,
            "proof_req": proof_req,
            "proof_hint": proof_hint,
            "resp_window": resp_window,
            "esc_days": esc_days,
        })


def downgrade() -> None:
    op.drop_index(op.f("ix_classroom_reports_classroom_ref"), table_name="classroom_reports")
    op.drop_index(op.f("ix_classroom_reports_tenant_id"), table_name="classroom_reports")
    op.drop_table("classroom_reports")
    op.drop_index(op.f("ix_subject_responses_filing_id"), table_name="subject_responses")
    op.drop_table("subject_responses")
    op.drop_index(op.f("ix_filing_reviews_filing_id"), table_name="filing_reviews")
    op.drop_table("filing_reviews")
    op.drop_index(op.f("ix_filing_attachments_filing_id"), table_name="filing_attachments")
    op.drop_table("filing_attachments")
    op.drop_index(op.f("ix_filings_anonymous_tracking_code"), table_name="filings")
    op.drop_index(op.f("ix_filings_filing_number"), table_name="filings")
    op.drop_index(op.f("ix_filings_category"), table_name="filings")
    op.drop_index(op.f("ix_filings_state"), table_name="filings")
    op.drop_index(op.f("ix_filings_tenant_id"), table_name="filings")
    op.drop_index(op.f("ix_filings_complainant_user_id"), table_name="filings")
    op.drop_table("filings")
    op.drop_index(op.f("ix_filing_templates_category"), table_name="filing_templates")
    op.drop_index(op.f("ix_filing_templates_key"), table_name="filing_templates")
    op.drop_table("filing_templates")
