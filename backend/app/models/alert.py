import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    String, DateTime, Enum, ForeignKey, LargeBinary,
    Integer, Boolean, Float, Text, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class GPSStatus(str, PyEnum):
    ok          = "ok"
    stale       = "stale"
    unavailable = "unavailable"


class AlertState(str, PyEnum):
    active      = "active"
    user_safe   = "user_safe"
    closed      = "closed"
    false_alert = "false_alert"
    resolved    = "resolved"


class RecipientType(str, PyEnum):
    proctor       = "proctor"
    nearby_user   = "nearby_user"
    contact_sms   = "contact_sms"
    contact_email = "contact_email"


class NotifChannel(str, PyEnum):
    push  = "push"
    sms   = "sms"
    email = "email"


class NotifStatus(str, PyEnum):
    queued     = "queued"
    sent       = "sent"
    delivered  = "delivered"
    failed     = "failed"
    suppressed = "suppressed"


class ResponseType(str, PyEnum):
    responding    = "responding"
    cannot_help   = "cannot_help"
    flagged_fake  = "flagged_fake"


class MediaType(str, PyEnum):
    photo    = "photo"
    video    = "video"
    audio    = "audio"
    document = "document"


class FCMPlatform(str, PyEnum):
    android = "android"
    ios     = "ios"
    web     = "web"


class ZoneType(str, PyEnum):
    rape       = "rape"
    murder     = "murder"
    alert      = "alert"
    university = "university"


class ZoneStatus(str, PyEnum):
    active   = "active"
    archived = "archived"


# ─── Phase 1 record (one per user, upserted) ────────────────────────────────

class AlertPhase1Record(Base):
    __tablename__ = "alert_phase1_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    encrypted_payload: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    emergency_contacts: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )


# ─── Zone (Alert Zones + static risk zones shown on map) ─────────────────────

class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    zone_type: Mapped[ZoneType] = mapped_column(
        Enum(ZoneType, name="zonetype"), nullable=False,
    )
    center_lat: Mapped[float] = mapped_column(Float, nullable=False)
    center_lng: Mapped[float] = mapped_column(Float, nullable=False)
    radius_m: Mapped[int] = mapped_column(Integer, nullable=False)
    description_public: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Logical reference to alert_events.event_id — no FK in model to avoid circular dep
    related_alert_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    status: Mapped[ZoneStatus] = mapped_column(
        Enum(ZoneStatus, name="zonestatus"), nullable=False, default=ZoneStatus.active,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=True, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


# ─── Core alert event ────────────────────────────────────────────────────────

class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, unique=True, nullable=False, default=uuid.uuid4, index=True,
    )
    # HMAC-SHA256 of user_id — rate-limit & ban enforcement only
    anonymous_actor_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # AES-256-GCM ciphertext of user_id — NULL for unauthenticated alerts
    encrypted_actor_link: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=True, index=True,
    )
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_accuracy_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gps_status: Mapped[GPSStatus] = mapped_column(
        Enum(GPSStatus, name="gpsstatus"), nullable=False, default=GPSStatus.unavailable,
    )
    device_fingerprint_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[AlertState] = mapped_column(
        Enum(AlertState, name="alertstate"), nullable=False,
        default=AlertState.active, index=True,
    )
    phase1_record_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("alert_phase1_records.id"), nullable=True,
    )
    alert_zone_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("zones.id"), nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # user | timeout | admin | false_alert_finding
    closed_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
    )

    notifications: Mapped[list["AlertNotification"]] = relationship(
        "AlertNotification", back_populates="event", cascade="all, delete-orphan",
    )
    responses: Mapped[list["AlertResponse"]] = relationship(
        "AlertResponse", back_populates="event", cascade="all, delete-orphan",
    )
    evidence: Mapped[list["AlertEvidence"]] = relationship(
        "AlertEvidence", back_populates="event", cascade="all, delete-orphan",
    )


# ─── Notification delivery tracking ─────────────────────────────────────────

class AlertNotification(Base):
    __tablename__ = "alert_notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("alert_events.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    recipient_type: Mapped[RecipientType] = mapped_column(
        Enum(RecipientType, name="recipienttype"), nullable=False,
    )
    recipient_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    channel: Mapped[NotifChannel] = mapped_column(
        Enum(NotifChannel, name="notifchannel"), nullable=False,
    )
    fcm_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[NotifStatus] = mapped_column(
        Enum(NotifStatus, name="notifstatus"), nullable=False, default=NotifStatus.queued,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    event: Mapped["AlertEvent"] = relationship("AlertEvent", back_populates="notifications")


# ─── Responder acknowledgements ──────────────────────────────────────────────

class AlertResponse(Base):
    __tablename__ = "alert_responses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("alert_events.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    responder_user_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_type: Mapped[ResponseType] = mapped_column(
        Enum(ResponseType, name="responsetype"), nullable=False,
    )
    distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    event: Mapped["AlertEvent"] = relationship("AlertEvent", back_populates="responses")


# ─── Phase 3 evidence ────────────────────────────────────────────────────────

class AlertEvidence(Base):
    __tablename__ = "alert_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("alert_events.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    # Client-side encrypted reference (e.g. presigned URL path) — server never stores raw file
    encrypted_blob_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    capture_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType, name="mediatype"), nullable=False,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    event: Mapped["AlertEvent"] = relationship("AlertEvent", back_populates="evidence")


# ─── 30-day ban enforcement ──────────────────────────────────────────────────

class AlertBan(Base):
    __tablename__ = "alert_bans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # SET NULL so the ban record persists even if the account is deleted
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    # For unauthenticated bans, only device_fingerprint_hash is set
    device_fingerprint_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ban_reason: Mapped[str] = mapped_column(Text, nullable=False)
    banned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ─── FCM device token registry ───────────────────────────────────────────────

class UserFCMToken(Base):
    __tablename__ = "user_fcm_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    fcm_token: Mapped[str] = mapped_column(String(512), nullable=False)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False)
    platform: Mapped[FCMPlatform] = mapped_column(
        Enum(FCMPlatform, name="fcmplatform"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ─── Location snapshot (one active row per user, upserted) ───────────────────

class UserLocationSnapshot(Base):
    __tablename__ = "user_location_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    user_id_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    geofence_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
    )
