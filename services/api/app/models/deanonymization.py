import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class DeanonymizationRequest(Base, TimestampMixin):
    """A request to release the real identity behind an anonymous filing or alert.

    Releasing identity requires strict two-person control: two *distinct*
    super admins must each approve. The first approval moves the request to
    ``awaiting_second_approval``; a second, different super admin's approval
    flips it to ``approved`` and opens a time-limited reveal window.

    The decrypted identity is never persisted — it is decrypted on demand from
    the target's ``encrypted_actor_link`` only while the request is approved and
    inside ``access_expires_at``.
    """
    __tablename__ = "deanonymization_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)

    # Target of the request — an anonymous filing or alert event.
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)  # filing | alert
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    target_ref: Mapped[str] = mapped_column(String(50), nullable=False)  # filing_number / alert event_id for display

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=True, index=True
    )

    # Who asked for the disclosure.
    requester_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    requester_label: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")

    legal_basis: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    formal_letter_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # pending_review | awaiting_second_approval | approved | denied | expired
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="pending_review", index=True
    )

    # Two-person control trail.
    first_approver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    first_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    second_approver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    second_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Denial trail.
    denied_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    denied_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Reveal window — set to now()+4h on final approval.
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
