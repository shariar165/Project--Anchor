"""
Alert system business logic.

All public async functions that run as FastAPI background tasks open their own
DB session via AsyncSessionLocal() — they must NOT receive a db: AsyncSession
argument because the request session may already be closed by the time
FastAPI runs the background task.
"""
import hashlib
import hmac
import json
import logging
import secrets
import string
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _today_str() -> str:
    return _now().strftime("%Y-%m-%d")


# ─── Cryptography helpers ────────────────────────────────────────────────────

def compute_anonymous_hash(user_id: uuid.UUID) -> str:
    """HMAC-SHA256 of user_id with alert_actor_hmac_key. Returns 64-char hex."""
    key = get_settings().alert_actor_hmac_key_bytes
    return hmac.new(key, str(user_id).encode(), hashlib.sha256).hexdigest()


def encrypt_actor_link(user_id: uuid.UUID) -> bytes:
    """AES-256-GCM encryption of user_id string. Returns nonce(12) + ciphertext+tag."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = get_settings().alert_encryption_key_bytes
    nonce = secrets.token_bytes(12)
    ct = AESGCM(key).encrypt(nonce, str(user_id).encode(), None)
    return nonce + ct


def encrypt_payload(data: bytes) -> bytes:
    """AES-256-GCM encryption of arbitrary bytes. Returns nonce(12) + ciphertext+tag."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = get_settings().alert_encryption_key_bytes
    nonce = secrets.token_bytes(12)
    ct = AESGCM(key).encrypt(nonce, data, None)
    return nonce + ct


def decrypt_payload(ciphertext: bytes) -> bytes:
    """Decrypt bytes produced by encrypt_payload."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = get_settings().alert_encryption_key_bytes
    nonce, ct = ciphertext[:12], ciphertext[12:]
    return AESGCM(key).decrypt(nonce, ct, None)


# ─── Rate limiting (Redis, atomic INCR-first) ────────────────────────────────

async def check_and_increment_rate_limit(redis, user_id_hash: str) -> bool:
    """
    Returns True if the alert is allowed (and increments the counter atomically).
    Returns False if the daily limit has already been reached.
    """
    key = f"alert_daily:{user_id_hash}:{_today_str()}"
    count = await redis.incr(key)
    if count == 1:
        # First alert today — set TTL to end of UTC day
        now = _now()
        midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        ttl = int((midnight - now).total_seconds()) + 1
        await redis.expire(key, ttl)

    limit = get_settings().alert_daily_limit_per_user
    if count > limit:
        # Already over limit — decrement so honest future checks work
        await redis.decr(key)
        return False
    return True


async def store_last_alert_time(redis, user_id_hash: str, event_id: uuid.UUID) -> None:
    await redis.set(
        f"alert_last:{user_id_hash}",
        json.dumps({"time": _now().isoformat(), "event_id": str(event_id)}),
        ex=86400,
    )


async def get_last_alert_info(redis, user_id_hash: str) -> dict | None:
    raw = await redis.get(f"alert_last:{user_id_hash}")
    return json.loads(raw) if raw else None


# ─── Claim tokens (unauthenticated → authenticated linking) ──────────────────

def generate_claim_token() -> str:
    """12-char base32 token shown to unauthenticated users after panic."""
    alphabet = string.ascii_uppercase + "234567"  # base32 alphabet
    return "".join(secrets.choice(alphabet) for _ in range(12))


async def store_claim_token(redis, token: str, event_id: uuid.UUID) -> None:
    await redis.set(f"claim:{token}", str(event_id), ex=7 * 86400)


async def get_claim_event_id(redis, token: str) -> uuid.UUID | None:
    val = await redis.get(f"claim:{token}")
    return uuid.UUID(val) if val else None


async def delete_claim_token(redis, token: str) -> None:
    await redis.delete(f"claim:{token}")


# ─── Fan-out pause/resume ────────────────────────────────────────────────────

async def pause_fanout(redis, event_id: uuid.UUID) -> None:
    await redis.set(f"fanout_paused:{event_id}", "1", ex=86400)


async def resume_fanout(redis, event_id: uuid.UUID) -> None:
    await redis.delete(f"fanout_paused:{event_id}")


async def is_fanout_paused(redis, event_id: uuid.UUID) -> bool:
    return bool(await redis.get(f"fanout_paused:{event_id}"))


# ─── Ban checking ────────────────────────────────────────────────────────────

async def check_ban(
    db: AsyncSession,
    user_id_hash: str,
    device_fp_hash: str,
) -> bool:
    """Return True if user or device is currently banned."""
    from app.models.alert import AlertBan

    now = _now()
    result = await db.execute(
        select(AlertBan).where(
            and_(
                AlertBan.expires_at > now,
                or_(
                    AlertBan.device_fingerprint_hash == device_fp_hash,
                    # We match bans where the device hash was set to the user hash
                    # (used for unauthenticated bans)
                    AlertBan.device_fingerprint_hash == user_id_hash,
                ),
            )
        ).limit(1)
    )
    return result.scalars().first() is not None


async def apply_ban(
    db: AsyncSession,
    user_id: uuid.UUID | None,
    device_fp_hash: str,
    reason: str,
    days: int | None = None,
) -> "AlertBan":
    from app.models.alert import AlertBan

    if days is None:
        days = get_settings().alert_false_ban_days

    ban = AlertBan(
        user_id=user_id,
        device_fingerprint_hash=device_fp_hash,
        ban_reason=reason,
        banned_at=_now(),
        expires_at=_now() + timedelta(days=days),
    )
    db.add(ban)
    await db.flush()
    return ban


# ─── Phase 1 record (upsert) ─────────────────────────────────────────────────

async def upsert_phase1_record(
    db: AsyncSession,
    user_id: uuid.UUID,
    encrypted_payload: bytes | None,
    encrypted_contacts: bytes | None,
) -> "AlertPhase1Record":
    from app.models.alert import AlertPhase1Record

    result = await db.execute(
        select(AlertPhase1Record).where(AlertPhase1Record.user_id == user_id)
    )
    record = result.scalars().first()
    if record:
        record.encrypted_payload = encrypted_payload
        record.emergency_contacts = encrypted_contacts
        record.updated_at = _now()
    else:
        record = AlertPhase1Record(
            user_id=user_id,
            encrypted_payload=encrypted_payload,
            emergency_contacts=encrypted_contacts,
        )
        db.add(record)
    await db.flush()
    return record


# ─── Event + zone creation ───────────────────────────────────────────────────

async def create_alert_event(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    device_fp_hash: str,
    lat: float | None,
    lng: float | None,
    gps_accuracy_m: int | None,
    gps_status: "GPSStatus",
    tenant_id: uuid.UUID | None,
    phase1_record_id: uuid.UUID | None,
) -> "AlertEvent":
    from app.models.alert import AlertEvent

    actor_hash = (
        compute_anonymous_hash(user_id)
        if user_id else device_fp_hash
    )
    encrypted_link = encrypt_actor_link(user_id) if user_id else None

    event = AlertEvent(
        anonymous_actor_hash=actor_hash,
        encrypted_actor_link=encrypted_link,
        tenant_id=tenant_id,
        lat=lat,
        lng=lng,
        gps_accuracy_m=gps_accuracy_m,
        gps_status=gps_status,
        device_fingerprint_hash=device_fp_hash,
        phase1_record_id=phase1_record_id,
    )
    db.add(event)
    await db.flush()
    return event


async def create_alert_zone(
    db: AsyncSession,
    lat: float,
    lng: float,
    event_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
) -> "Zone":
    from app.models.alert import Zone, ZoneType, ZoneStatus

    settings = get_settings()
    zone = Zone(
        zone_type=ZoneType.alert,
        center_lat=lat,
        center_lng=lng,
        radius_m=settings.alert_zone_radius_m,
        related_alert_id=event_id,
        status=ZoneStatus.active,
        expires_at=_now() + timedelta(hours=settings.alert_autoclose_hours),
        label="Active alert zone",
        tenant_id=tenant_id,
        description_public="Emergency alert triggered nearby.",
    )
    db.add(zone)
    await db.flush()
    return zone


# ─── Notification background tasks ───────────────────────────────────────────
# These open their own DB sessions — do not accept db: AsyncSession.

async def notify_proctor(event_id: uuid.UUID) -> None:
    """Notify the tenant proctor (moderator/admin) via FCM push + email."""
    from app.database import AsyncSessionLocal
    from app.models.alert import AlertEvent, AlertNotification, RecipientType, NotifChannel, NotifStatus
    from app.models.user import User, Role
    from app.services import fcm as fcm_svc
    from app.services.email import send_email

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AlertEvent).where(AlertEvent.event_id == event_id)
            )
            event = result.scalars().first()
            if not event:
                return

            # Find proctor: moderators in the same tenant, fall back to admins
            q = select(User).where(
                and_(
                    User.tenant_id == event.tenant_id,
                    User.role.in_([Role.moderator, Role.admin]),
                )
            )
            proctors = (await db.execute(q)).scalars().all()
            if not proctors and event.tenant_id:
                q2 = select(User).where(User.role == Role.admin)
                proctors = (await db.execute(q2)).scalars().all()

            ts = event.created_at.strftime("%H:%M UTC") if event.created_at else "unknown time"
            lat_str = f"{event.lat:.4f}" if event.lat else "N/A"
            lng_str = f"{event.lng:.4f}" if event.lng else "N/A"

            from app.models.alert import UserFCMToken
            for proctor in proctors:
                # FCM push
                tok_result = await db.execute(
                    select(UserFCMToken).where(
                        and_(
                            UserFCMToken.user_id == proctor.id,
                            UserFCMToken.disabled_at.is_(None),
                        )
                    )
                )
                for tok in tok_result.scalars().all():
                    res = await fcm_svc.send_to_token(
                        tok.fcm_token,
                        title="Anchor: Active alert — your campus",
                        body=f"An active alert has been triggered on campus at {ts}.",
                        data={
                            "event_id": str(event.event_id),
                            "category": "campus_alert",
                            "deep_link": f"/?alert={event.event_id}",
                            "lat": lat_str,
                            "lng": lng_str,
                        },
                    )
                    msg_id = res["message_id"]
                    # Permanently-invalid token → disable so future fan-outs skip it
                    if res["error"] in fcm_svc.PERMANENT_ERRORS:
                        tok.disabled_at = _now()
                    notif = AlertNotification(
                        event_id=event.id,
                        recipient_type=RecipientType.proctor,
                        recipient_ref=str(proctor.id),
                        channel=NotifChannel.push,
                        fcm_message_id=msg_id,
                        status=NotifStatus.sent if msg_id else NotifStatus.failed,
                        attempts=1,
                        last_attempt_at=_now(),
                        sent_at=_now() if msg_id else None,
                    )
                    db.add(notif)

                # Email
                if proctor.email:
                    subject = "Anchor AI — Active campus alert"
                    frontend_url = get_settings().frontend_url.rstrip("/")
                    open_link = (
                        f"<p><a href='{frontend_url}/?alert={event.event_id}'>Open in Anchor</a></p>"
                        if frontend_url else ""
                    )
                    html = (
                        f"<p>An emergency alert has been triggered on campus at <b>{ts}</b>.</p>"
                        f"<p>Approximate location: {lat_str}, {lng_str}</p>"
                        f"<p>Event ID: <code>{event.event_id}</code></p>"
                        f"{open_link}"
                    )
                    await send_email(proctor.email, subject, html)
                    notif = AlertNotification(
                        event_id=event.id,
                        recipient_type=RecipientType.proctor,
                        recipient_ref=proctor.email,
                        channel=NotifChannel.email,
                        status=NotifStatus.sent,
                        attempts=1,
                        last_attempt_at=_now(),
                        sent_at=_now(),
                    )
                    db.add(notif)

            await db.commit()
    except Exception as exc:
        logger.exception("[ALERT] notify_proctor failed for event %s: %s", event_id, exc)


async def notify_nearby_users(event_id: uuid.UUID, zone_id: uuid.UUID) -> None:
    """Fan out FCM pushes to consenting users inside the alert zone."""
    from app.database import AsyncSessionLocal
    from app.redis import get_redis
    from app.models.alert import AlertEvent, Zone, AlertNotification, RecipientType, NotifChannel, NotifStatus
    from app.services import fcm as fcm_svc
    from app.services.geofence import get_nearby_users

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AlertEvent).where(AlertEvent.event_id == event_id)
            )
            event = result.scalars().first()
            if not event or not event.lat or not event.lng:
                return

            zone_result = await db.execute(select(Zone).where(Zone.id == zone_id))
            zone = zone_result.scalars().first()
            radius_m = zone.radius_m if zone else get_settings().alert_zone_radius_m

            nearby = await get_nearby_users(
                db, event.lat, event.lng, radius_m, event.anonymous_actor_hash
            )

            settings = get_settings()
            redis = get_redis()
            lat_str = f"{event.lat:.4f}"
            lng_str = f"{event.lng:.4f}"

            for i in range(0, len(nearby), settings.alert_nearby_batch_size):
                if await is_fanout_paused(redis, event.event_id):
                    logger.info("[ALERT] Fan-out paused for event %s (enough responders)", event_id)
                    break

                batch = nearby[i : i + settings.alert_nearby_batch_size]
                all_tokens = []
                token_to_hash: dict[str, str] = {}
                for user in batch:
                    for tok in user["fcm_tokens"]:
                        all_tokens.append(tok)
                        token_to_hash[tok] = user["user_id_hash"]

                if all_tokens:
                    results = await fcm_svc.send_batch(
                        all_tokens,
                        title="Anchor: Someone nearby needs help",
                        body="An emergency alert was just triggered near you. Tap to see how you can help.",
                        data={
                            "event_id": str(event.event_id),
                            "category": "nearby_alert",
                            "deep_link": f"/?alert={event.event_id}",
                            "lat": lat_str,
                            "lng": lng_str,
                        },
                    )
                    dead_tokens: list[str] = []
                    for tok, res in results.items():
                        msg_id = res["message_id"]
                        if res["error"] in fcm_svc.PERMANENT_ERRORS:
                            dead_tokens.append(tok)
                        notif = AlertNotification(
                            event_id=event.id,
                            recipient_type=RecipientType.nearby_user,
                            recipient_ref=token_to_hash.get(tok, tok[:20]),
                            channel=NotifChannel.push,
                            fcm_message_id=msg_id,
                            status=NotifStatus.sent if msg_id else NotifStatus.failed,
                            attempts=1,
                            last_attempt_at=_now(),
                            sent_at=_now() if msg_id else None,
                        )
                        db.add(notif)

                    # Self-heal: disable permanently-invalid tokens so they are
                    # excluded from get_nearby_users on subsequent fan-outs.
                    if dead_tokens:
                        from app.models.alert import UserFCMToken
                        await db.execute(
                            update(UserFCMToken)
                            .where(
                                and_(
                                    UserFCMToken.fcm_token.in_(dead_tokens),
                                    UserFCMToken.disabled_at.is_(None),
                                )
                            )
                            .values(disabled_at=_now())
                        )

            await db.commit()
    except Exception as exc:
        logger.exception("[ALERT] notify_nearby_users failed for event %s: %s", event_id, exc)


async def notify_contacts(event_id: uuid.UUID) -> None:
    """Send SMS to emergency contacts stored in the Phase 1 record."""
    from app.database import AsyncSessionLocal
    from app.models.alert import AlertEvent, AlertPhase1Record, AlertNotification, RecipientType, NotifChannel, NotifStatus
    from app.services.sms import send_sms

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AlertEvent).where(AlertEvent.event_id == event_id)
            )
            event = result.scalars().first()
            if not event or not event.phase1_record_id:
                return

            p1_result = await db.execute(
                select(AlertPhase1Record).where(AlertPhase1Record.id == event.phase1_record_id)
            )
            p1 = p1_result.scalars().first()
            if not p1 or not p1.emergency_contacts:
                return

            try:
                contacts = json.loads(decrypt_payload(p1.emergency_contacts).decode())
            except Exception:
                logger.warning("[ALERT] Could not decrypt contacts for event %s", event_id)
                return

            ts = event.created_at.strftime("%H:%M") if event.created_at else "unknown time"
            for contact in contacts:
                phone = contact.get("phone", "")
                name  = contact.get("name", "Someone")
                if not phone:
                    continue
                msg = (
                    f"[Anchor] {name} triggered an emergency alert at {ts}. "
                    f"Event: {event.event_id}. "
                    f"If you can help, open Anchor AI for their location."
                )
                ok = await send_sms(phone, msg)
                notif = AlertNotification(
                    event_id=event.id,
                    recipient_type=RecipientType.contact_sms,
                    recipient_ref=phone[-4:].ljust(len(phone), "•"),
                    channel=NotifChannel.sms,
                    status=NotifStatus.sent if ok else NotifStatus.failed,
                    attempts=1,
                    last_attempt_at=_now(),
                    sent_at=_now() if ok else None,
                )
                db.add(notif)

            await db.commit()
    except Exception as exc:
        logger.exception("[ALERT] notify_contacts failed for event %s: %s", event_id, exc)


# ─── State transitions ───────────────────────────────────────────────────────

async def mark_event_safe(
    db: AsyncSession,
    event_id: uuid.UUID,
    actor_hash: str,
) -> "AlertEvent":
    """Transition active → user_safe. Raises ValueError if not authorized."""
    from app.models.alert import AlertEvent, AlertState, Zone, ZoneStatus

    result = await db.execute(
        select(AlertEvent).where(AlertEvent.event_id == event_id)
    )
    event = result.scalars().first()
    if not event:
        raise ValueError("Event not found")
    if event.anonymous_actor_hash != actor_hash:
        raise PermissionError("Not authorized for this alert")
    if event.state != AlertState.active:
        raise ValueError(f"Cannot mark safe — current state is {event.state.value}")

    event.state = AlertState.user_safe
    event.closed_at = _now()
    event.closed_by = "user"

    # Archive the linked zone
    if event.alert_zone_id:
        z_result = await db.execute(select(Zone).where(Zone.id == event.alert_zone_id))
        zone = z_result.scalars().first()
        if zone:
            zone.status = ZoneStatus.archived

    await db.flush()
    return event


async def auto_close_event_if_expired(
    db: AsyncSession,
    event: "AlertEvent",
) -> bool:
    """Close the event if it has passed the 24-hour autoclose window. Returns True if closed."""
    from app.models.alert import AlertState, Zone, ZoneStatus

    settings = get_settings()
    if event.state != AlertState.active:
        return False

    # SQLite returns naive datetimes; make timezone-aware before comparison
    created_at = event.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_hours = (_now() - created_at).total_seconds() / 3600
    if age_hours < settings.alert_autoclose_hours:
        return False

    event.state = AlertState.closed
    event.closed_at = _now()
    event.closed_by = "timeout"

    if event.alert_zone_id:
        z_result = await db.execute(select(Zone).where(Zone.id == event.alert_zone_id))
        zone = z_result.scalars().first()
        if zone:
            zone.status = ZoneStatus.archived

    await db.flush()
    return True
