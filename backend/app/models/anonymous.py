import uuid
from sqlalchemy import String, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class AnonymousIdentityMapping(Base, TimestampMixin):
    """Maps anonymous complaint codes to real user IDs.
    Stored in a restricted schema accessible only to auditors.
    """
    __tablename__ = "anonymous_identity_mappings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    anonymous_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    complaint_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="received")
    status_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
