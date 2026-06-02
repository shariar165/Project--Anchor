import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    String, DateTime, Enum, ForeignKey, Integer, Boolean,
    Text, Uuid, Numeric, BigInteger, JSON, UniqueConstraint, func, Double,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class PostScope(str, PyEnum):
    campus   = "campus"
    national = "national"


class PostCategory(str, PyEnum):
    incident       = "incident"
    missing_person = "missing_person"
    road           = "road"
    safety         = "safety"
    civic_event    = "civic_event"


class PostState(str, PyEnum):
    pending_ai        = "pending_ai"
    live              = "live"
    under_review      = "under_review"
    taken_down        = "taken_down"
    marked_fake       = "marked_fake"
    deleted_by_author = "deleted_by_author"


class AIPrescreenVerdict(str, PyEnum):
    pass_         = "pass"           # Python attr pass_ → DB value "pass"
    block         = "block"
    manual_review = "manual_review"


class SignalType(str, PyEnum):
    corroborate = "corroborate"
    challenge   = "challenge"


class FlagReason(str, PyEnum):
    harassment      = "harassment"
    off_topic       = "off_topic"
    wrong_category  = "wrong_category"
    illegal_content = "illegal_content"
    spam            = "spam"
    other           = "other"


class ModerationAction(str, PyEnum):
    confirm         = "confirm"
    mark_fake       = "mark_fake"
    take_down       = "take_down"
    no_action       = "no_action"
    defer           = "defer"
    restore         = "restore"
    promote_to_zone = "promote_to_zone"


class TrustTier(str, PyEnum):
    none   = "none"
    bronze = "bronze"
    silver = "silver"
    gold   = "gold"


class VerificationFeedPost(Base, TimestampMixin):
    __tablename__ = "verification_feed_posts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    post_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    publisher_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope: Mapped[PostScope] = mapped_column(Enum(PostScope), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[PostCategory] = mapped_column(Enum(PostCategory), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON list[str] — sa.ARRAY not used so SQLite tests work
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    geo_lat: Mapped[float | None] = mapped_column(Double, nullable=True)
    geo_lng: Mapped[float | None] = mapped_column(Double, nullable=True)
    geo_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[PostState] = mapped_column(
        Enum(PostState), nullable=False, default=PostState.pending_ai, index=True
    )
    ai_prescreen_verdict: Mapped[AIPrescreenVerdict | None] = mapped_column(
        Enum(AIPrescreenVerdict), nullable=True
    )
    ai_prescreen_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    admin_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    admin_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("zones.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    signals: Mapped[list["VerificationFeedSignal"]] = relationship(
        "VerificationFeedSignal", back_populates="post", cascade="all, delete-orphan"
    )
    flags: Mapped[list["VerificationFeedFlag"]] = relationship(
        "VerificationFeedFlag", back_populates="post", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["VerificationFeedAttachment"]] = relationship(
        "VerificationFeedAttachment", back_populates="post", cascade="all, delete-orphan"
    )
    moderation_log: Mapped[list["VerificationFeedModeration"]] = relationship(
        "VerificationFeedModeration", back_populates="post", cascade="all, delete-orphan"
    )
    versions: Mapped[list["VerificationFeedPostVersion"]] = relationship(
        "VerificationFeedPostVersion", back_populates="post", cascade="all, delete-orphan"
    )


class VerificationFeedPostVersion(Base):
    __tablename__ = "verification_feed_post_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_feed_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    geo_lat: Mapped[float | None] = mapped_column(Double, nullable=True)
    geo_lng: Mapped[float | None] = mapped_column(Double, nullable=True)
    edited_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    post: Mapped["VerificationFeedPost"] = relationship("VerificationFeedPost", back_populates="versions")


class VerificationFeedAttachment(Base):
    __tablename__ = "verification_feed_attachments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_feed_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_ref: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    explain_cache: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    post: Mapped["VerificationFeedPost"] = relationship("VerificationFeedPost", back_populates="attachments")


class VerificationFeedSignal(Base):
    __tablename__ = "verification_feed_signals"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_feed_signal_per_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_feed_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    signal_type: Mapped[SignalType] = mapped_column(Enum(SignalType), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    weight: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    post: Mapped["VerificationFeedPost"] = relationship("VerificationFeedPost", back_populates="signals")


class VerificationFeedFlag(Base):
    __tablename__ = "verification_feed_flags"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_feed_flag_per_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_feed_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    flag_reason: Mapped[FlagReason] = mapped_column(Enum(FlagReason), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    post: Mapped["VerificationFeedPost"] = relationship("VerificationFeedPost", back_populates="flags")


class VerificationFeedModeration(Base):
    __tablename__ = "verification_feed_moderation"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_feed_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    moderator_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[ModerationAction] = mapped_column(Enum(ModerationAction), nullable=False)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    post: Mapped["VerificationFeedPost"] = relationship("VerificationFeedPost", back_populates="moderation_log")


class UserFeedTrust(Base):
    __tablename__ = "user_feed_trust"

    # user_id is the primary key — one row per user
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    confirmed_accurate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confirmed_fake_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trust_tier: Mapped[TrustTier] = mapped_column(Enum(TrustTier), default=TrustTier.none, nullable=False)
    last_recalculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
