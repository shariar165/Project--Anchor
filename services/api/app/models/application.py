import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class ApplicationState(str, PyEnum):
    draft = "draft"
    submitted = "submitted"
    in_review = "in_review"
    changes_requested = "changes_requested"
    approved = "approved"
    rejected = "rejected"
    withdrawn = "withdrawn"
    escalated = "escalated"


class ApplicationTemplate(Base, TimestampMixin):
    __tablename__ = "application_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_bn: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    skill_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    default_escalation_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="7")
    requires_accounts_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    proof_hint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Application(Base, TimestampMixin):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=True, index=True
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("application_templates.id"), nullable=False
    )
    field_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    letter_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(2), nullable=False, server_default="en")
    state: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft", index=True)
    first_approver_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    current_approver_level: Mapped[str | None] = mapped_column(String(30), nullable=True)
    current_approver_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    round_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pdf_ref: Mapped[str | None] = mapped_column(Text, nullable=True)

    attachments: Mapped[list["ApplicationAttachment"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", lazy="selectin"
    )
    reviews: Mapped[list["ApplicationReview"]] = relationship(
        back_populates="application", cascade="all, delete-orphan",
        order_by="ApplicationReview.reviewed_at", lazy="selectin"
    )
    template: Mapped["ApplicationTemplate"] = relationship(lazy="selectin")


class ApplicationAttachment(Base):
    __tablename__ = "application_attachments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_ref: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    explain_cache: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    application: Mapped["Application"] = relationship(back_populates="attachments")


class ApplicationReview(Base):
    __tablename__ = "application_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_role: Mapped[str] = mapped_column(String(30), nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    application: Mapped["Application"] = relationship(back_populates="reviews")


class StudentCampusSettings(Base):
    __tablename__ = "student_campus_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mentor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    department_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
