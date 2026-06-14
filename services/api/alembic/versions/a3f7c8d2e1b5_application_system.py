"""application_system

Revision ID: a3f7c8d2e1b5
Revises: 1e240152fca9
Create Date: 2026-06-01 12:00:00.000000
"""
import uuid
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a3f7c8d2e1b5'
down_revision: Union[str, None] = '1e240152fca9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TEMPLATES = [
    ("late-fee-payment",   "Late Fee Payment",              "লেট ফি পেমেন্ট",              "late-fee-payment.md",           True),
    ("fee-installment",    "Fee Installment Request",        "কিস্তিতে ফি পরিশোধ",          "late-fee-payment.md",           True),
    ("scholarship",        "Scholarship Application",        "বৃত্তির আবেদন",               "general-application.md",        False),
    ("medical-leave",      "Medical Leave",                  "মেডিকেল ছুটির আবেদন",        "attendance-leave.md",           False),
    ("personal-leave",     "Personal Leave",                 "ব্যক্তিগত ছুটির আবেদন",      "attendance-leave.md",           False),
    ("course-retake",      "Course Retake / Improvement",   "কোর্স রিটেক",                 "exam-permission.md",            False),
    ("course-withdrawal",  "Course Withdrawal",              "কোর্স উইথড্রয়াল",            "registration-permission.md",    False),
    ("certificate-request","Certificate / Transcript Request","সার্টিফিকেট / ট্রান্সক্রিপ্ট","general-application.md",      False),
    ("exam-overlap",       "Overlap / Clash Exam",           "পরীক্ষার ক্লাশ সমস্যা",      "overlap-exam.md",               False),
    ("id-card",            "ID Card Extension / Renewal",   "আইডি কার্ড নবায়ন",           "id-card-extension.md",          False),
    ("late-degree",        "Late Degree Approval",           "লেট ডিগ্রি অনুমোদন",         "late-degree-approval.md",       False),
    ("exam-permission",    "Mid / Final Exam Permission",   "পরীক্ষার অনুমতি",             "exam-permission.md",            False),
    ("other",              "Other",                          "অন্যান্য",                    "general-application.md",        False),
]


def upgrade() -> None:
    op.create_table(
        "application_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_bn", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("skill_reference", sa.String(length=100), nullable=False),
        sa.Column("default_escalation_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("requires_accounts_approval", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("proof_hint", sa.String(length=500), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_application_templates_key"), "application_templates", ["key"], unique=True)

    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("field_values", sa.JSON(), nullable=False),
        sa.Column("letter_body", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=2), nullable=False, server_default="en"),
        sa.Column("state", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("first_approver_type", sa.String(length=30), nullable=True),
        sa.Column("current_approver_level", sa.String(length=30), nullable=True),
        sa.Column("current_approver_id", sa.Uuid(), nullable=True),
        sa.Column("round_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pdf_ref", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["current_approver_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["application_templates.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_applications_student_id"), "applications", ["student_id"], unique=False)
    op.create_index(op.f("ix_applications_tenant_id"), "applications", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_applications_state"), "applications", ["state"], unique=False)

    op.create_table(
        "application_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("file_ref", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("explain_cache", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_application_attachments_application_id"), "application_attachments", ["application_id"], unique=False)

    op.create_table(
        "application_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("reviewer_role", sa.String(length=30), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_application_reviews_application_id"), "application_reviews", ["application_id"], unique=False)

    op.create_table(
        "student_campus_settings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("department", sa.String(length=200), nullable=True),
        sa.Column("mentor_user_id", sa.Uuid(), nullable=True),
        sa.Column("department_locked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["mentor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # Seed templates
    conn = op.get_bind()
    for key, name, name_bn, skill_ref, req_accounts in _TEMPLATES:
        conn.execute(sa.text(
            "INSERT INTO application_templates (id, key, name, name_bn, skill_reference, "
            "requires_accounts_approval, active, created_at, updated_at) "
            "VALUES (:id, :key, :name, :name_bn, :skill_ref, :req_accounts, true, now(), now())"
        ), {
            "id": str(uuid.uuid4()),
            "key": key,
            "name": name,
            "name_bn": name_bn,
            "skill_ref": skill_ref,
            "req_accounts": req_accounts,
        })


def downgrade() -> None:
    op.drop_table("student_campus_settings")
    op.drop_index(op.f("ix_application_reviews_application_id"), table_name="application_reviews")
    op.drop_table("application_reviews")
    op.drop_index(op.f("ix_application_attachments_application_id"), table_name="application_attachments")
    op.drop_table("application_attachments")
    op.drop_index(op.f("ix_applications_state"), table_name="applications")
    op.drop_index(op.f("ix_applications_tenant_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_student_id"), table_name="applications")
    op.drop_table("applications")
    op.drop_index(op.f("ix_application_templates_key"), table_name="application_templates")
    op.drop_table("application_templates")
