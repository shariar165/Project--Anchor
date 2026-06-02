import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, JSON, LargeBinary,
    String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class FilingCategory(str, PyEnum):
    complaint = "complaint"
    report = "report"
    grievance = "grievance"


class FilingAnonymityMode(str, PyEnum):
    anonymous = "anonymous"
    attributed = "attributed"
    aggregated = "aggregated"


class FilingState(str, PyEnum):
    draft = "draft"
    moderation_queue = "moderation_queue"
    routed = "routed"
    subject_notified = "subject_notified"
    subject_responded = "subject_responded"
    under_review = "under_review"
    resolved = "resolved"
    dismissed = "dismissed"
    withdrawn = "withdrawn"
    spam_rejected = "spam_rejected"


class ClassroomIssueType(str, PyEnum):
    projector = "projector"
    ac = "ac"
    seating = "seating"
    lighting = "lighting"
    door = "door"
    cleanliness = "cleanliness"
    sound = "sound"
    other = "other"


class FilingTemplate(Base, TimestampMixin):
    __tablename__ = "filing_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_bn: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    anonymity_mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default="attributed")
    routing_target: Mapped[str] = mapped_column(String(30), nullable=False, server_default="dept_head")
    requires_stepup: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    goes_to_moderation_queue: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    proof_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    proof_hint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    subject_response_window_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="7")
    default_escalation_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="7")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Filing(Base, TimestampMixin):
    __tablename__ = "filings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filing_number: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True, index=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("filing_templates.id"), nullable=False
    )
    # Complainant — NULL for truly anonymous filings
    complainant_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Fernet-encrypted user_id stored for anonymous filings (only platform admins can decrypt)
    encrypted_actor_link: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    anonymous_tracking_code: Mapped[str | None] = mapped_column(
        String(20), unique=True, nullable=True, index=True
    )
    subject_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    subject_descriptor: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(2), nullable=False, server_default="en")
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ai_assisted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    state: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft", index=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, server_default="normal")
    current_reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    state_entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    template: Mapped["FilingTemplate"] = relationship(lazy="selectin")
    attachments: Mapped[list["FilingAttachment"]] = relationship(
        back_populates="filing", cascade="all, delete-orphan", lazy="selectin"
    )
    reviews: Mapped[list["FilingReview"]] = relationship(
        back_populates="filing", cascade="all, delete-orphan",
        order_by="FilingReview.reviewed_at", lazy="selectin"
    )
    subject_responses: Mapped[list["SubjectResponse"]] = relationship(
        back_populates="filing", cascade="all, delete-orphan", lazy="selectin"
    )


class FilingAttachment(Base):
    __tablename__ = "filing_attachments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("filings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_ref: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    explain_cache: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    filing: Mapped["Filing"] = relationship(back_populates="attachments")


class FilingReview(Base):
    __tablename__ = "filing_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("filings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_role: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    filing: Mapped["Filing"] = relationship(back_populates="reviews")


class SubjectResponse(Base):
    __tablename__ = "subject_responses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("filings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    notified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_window_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    filing: Mapped["Filing"] = relationship(back_populates="subject_responses")


class ClassroomReport(Base, TimestampMixin):
    __tablename__ = "classroom_reports"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "classroom_ref", "issue_type", "reporter_user_id",
            name="uq_classroom_report_per_user",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=True, index=True
    )
    classroom_ref: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
