import uuid
from enum import Enum as PyEnum
from sqlalchemy import String, Boolean, Enum, ForeignKey, DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class MFAType(str, PyEnum):
    totp = "totp"
    sms = "sms"


class MFAMethod(Base, TimestampMixin):
    __tablename__ = "mfa_methods"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[MFAType] = mapped_column(Enum(MFAType), nullable=False)
    secret_encrypted: Mapped[str] = mapped_column(String(500), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="mfa_methods")
    recovery_codes = relationship("MFARecoveryCode", back_populates="method", cascade="all, delete-orphan")


class MFARecoveryCode(Base):
    __tablename__ = "mfa_recovery_codes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    method_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("mfa_methods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    method = relationship("MFAMethod", back_populates="recovery_codes")
