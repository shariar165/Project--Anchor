import uuid
from sqlalchemy import String, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class UserE2EEKey(Base, TimestampMixin):
    """Stores user-submitted public keys only. Server never sees private keys."""
    __tablename__ = "user_e2ee_keys"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    public_key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    key_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
