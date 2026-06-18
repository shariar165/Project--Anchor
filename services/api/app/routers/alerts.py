"""
Emergency Alert System router.

Route order is significant — static paths (/nearby, /panic, /panic/claim,
/phase1, /trigger) MUST be declared before the parameterised /{event_id}
routes to avoid FastAPI matching literal words as UUIDs.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, TokenData
from app.limiter import limiter
from app.models.alert import (
    AlertEvent, AlertPhase1Record, AlertResponse, AlertEvidence,
    AlertNotification, UserFCMToken, UserLocationSnapshot, Zone,
    AlertState, GPSStatus, ResponseType, MediaType, FCMPlatform, ZoneStatus,
)
from app.models.user import User, AccountStatus
from app.redis import get_redis
from app.schemas.alerts import (
    AlertRespondersResponse, AlertStatusResponse, AlertTriggerRequest, AlertTriggerResponse,
    EvidenceUploadRequest, EvidenceUploadResponse,
    FCMTokenRegisterRequest, LocationUpdateRequest,
    NearbyAlertItem, PanicClaimRequest, PanicTriggerRequest,
    Phase1SaveRequest, Phase1SaveResponse, ResponderItem, RespondRequest,
)
from app.services import alert_svc
from app.services.audit import log_event as audit_log
from app.services.device import fingerprint as device_fingerprint, get_ip
from app.services.geofence import haversine

router = APIRouter(tags=["alerts"])

_optional_bearer = HTTPBearer(auto_error=False)


async def _optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> TokenData | None:
    """Return TokenData if a valid bearer token is present, else None."""
    if credentials is None:
        return None
    try:
        from app.services.token import decode_token, is_blacklisted
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        token_data = TokenData(payload)
        if await is_blacklisted(redis, token_data.jti):
            return None
        result = await db.execute(select(User).where(User.id == token_data.user_id))
        user = result.scalars().first()
        if not user or user.status != AccountStatus.active:
            return None
        return token_data
    except Exception:
        return None


def _device_fp_hash(request: Request) -> str:
    """Full SHA-256 hex of the device fingerprint (not truncated)."""
    raw_fp = device_fingerprint(request)
    return hashlib.sha256(raw_fp.encode()).hexdigest()


# ─── Phase 1 — before ────────────────────────────────────────────────────────

@router.post("/v1/alerts/phase1", response_model=Phase1SaveResponse)
@limiter.limit("20/minute")
async def save_phase1(
    body: Phase1SaveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    """Save or update the Phase 1 threat record + emergency contacts for the current user."""
    contacts_json = json.dumps(
        [c.model_dump() for c in body.emergency_contacts],
        ensure_ascii=False,
    ).encode()
    payload_json = json.dumps(
        {"threat_description": body.threat_description}, ensure_ascii=False
    ).encode()

    enc_payload = alert_svc.encrypt_payload(payload_json)
    enc_contacts = alert_svc.encrypt_payload(contacts_json)

    record = await alert_svc.upsert_phase1_record(
        db, token.user_id, enc_payload, enc_contacts
    )
    await audit_log(db, "alert_phase1_saved", token.user_id, get_ip(request))
    await db.commit()
    return record


# ─── Nearby alerts (must be before /{event_id}) ──────────────────────────────

@router.get("/v1/alerts/nearby", response_model=list[NearbyAlertItem])
@limiter.limit("30/minute")
async def get_nearby_alerts(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(default=1000, ge=100, le=10000),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    """Return active alert events within radius_m of the given coordinates."""
    from app.config import get_settings
    import math

    settings = get_settings()
    deg_lat = radius_m / 111_000
    deg_lng = radius_m / (111_000 * math.cos(math.radians(lat)) + 1e-9)

    result = await db.execute(
        select(AlertEvent).where(
            and_(
                AlertEvent.state == AlertState.active,
                AlertEvent.lat.isnot(None),
                AlertEvent.lat.between(lat - deg_lat, lat + deg_lat),
                AlertEvent.lng.between(lng - deg_lng, lng + deg_lng),
            )
        ).order_by(AlertEvent.created_at.desc()).limit(50)
    )
    events = result.scalars().all()

    items = []
    for ev in events:
        dist = int(haversine(lat, lng, ev.lat, ev.lng)) if ev.lat and ev.lng else None
        if dist is None or dist <= radius_m:
            items.append(NearbyAlertItem(
                event_id=ev.event_id,
                lat=ev.lat,
                lng=ev.lng,
                distance_m=dist,
                state=ev.state.value,
                created_at=ev.created_at,
            ))
    return items


# ─── Panic (unauthenticated) ─────────────────────────────────────────────────

@router.post("/v1/alerts/panic", response_model=AlertTriggerResponse)
@limiter.limit("5/minute")
async def panic_unauthenticated(
    body: PanicTriggerRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Unauthenticated emergency alert trigger (life-safety override).
    Rate-limited by device fingerprint.
    """
    device_fp_hash = hashlib.sha256(body.device_fingerprint.encode()).hexdigest()

    if await alert_svc.check_ban(db, device_fp_hash, device_fp_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Device is banned from sending alerts")

    allowed = await alert_svc.check_and_increment_rate_limit(redis, device_fp_hash)
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "This device has already sent an emergency alert today. "
                "If you are in continuing danger, call 999."
            ),
        )

    event = await alert_svc.create_alert_event(
        db,
        user_id=None,
        device_fp_hash=device_fp_hash,
        lat=body.lat, lng=body.lng,
        gps_accuracy_m=body.gps_accuracy_m,
        gps_status=GPSStatus(body.gps_status),
        tenant_id=None,
        phase1_record_id=None,
    )

    zone = None
    if body.lat and body.lng:
        zone = await alert_svc.create_alert_zone(db, body.lat, body.lng, event.event_id, None)
        event.alert_zone_id = zone.id

    claim_token = alert_svc.generate_claim_token()
    await db.commit()

    await alert_svc.store_claim_token(redis, claim_token, event.event_id)
    await alert_svc.store_last_alert_time(redis, device_fp_hash, event.event_id)

    if zone:
        background_tasks.add_task(alert_svc.notify_nearby_users, event.event_id, zone.id)

    return AlertTriggerResponse(
        event_id=event.event_id,
        state=event.state.value,
        claim_token=claim_token,
        message="Alert broadcast. Use your claim token to link this alert to your account.",
    )


@router.post("/v1/alerts/panic/claim")
@limiter.limit("10/minute")
async def claim_panic_alert(
    body: PanicClaimRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    token: TokenData = Depends(get_current_user),
):
    """Link an unauthenticated panic alert to the current user's account."""
    event_id = await alert_svc.get_claim_event_id(redis, body.claim_token)
    if not event_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Claim token not found or expired")

    result = await db.execute(select(AlertEvent).where(AlertEvent.event_id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert event not found")

    user_hash = alert_svc.compute_anonymous_hash(token.user_id)
    event.anonymous_actor_hash = user_hash
    event.encrypted_actor_link = alert_svc.encrypt_actor_link(token.user_id)

    await alert_svc.delete_claim_token(redis, body.claim_token)
    await db.commit()
    return {"message": "Alert linked to your account", "event_id": str(event.event_id)}


# ─── Authenticated trigger ───────────────────────────────────────────────────

@router.post("/v1/alerts/trigger", response_model=AlertTriggerResponse)
@limiter.limit("5/minute")
async def trigger_alert(
    body: AlertTriggerRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    token: TokenData = Depends(get_current_user),
):
    """
    Phase 2 — create an authenticated emergency alert event.
    Returns state='rate_limited' (200) if daily limit already reached.
    """
    user_hash = alert_svc.compute_anonymous_hash(token.user_id)
    fp_hash = _device_fp_hash(request)

    # Ban check
    if await alert_svc.check_ban(db, user_hash, fp_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is banned from triggering alerts")

    # Rate limit (atomic INCR-first)
    allowed = await alert_svc.check_and_increment_rate_limit(redis, user_hash)
    if not allowed:
        last_info = await alert_svc.get_last_alert_info(redis, user_hash)
        last_time = last_info["time"] if last_info else "earlier today"
        return AlertTriggerResponse(
            event_id=uuid.uuid4(),  # placeholder
            state="rate_limited",
            message=(
                f"You triggered an alert at {last_time}. "
                "If this is a continuing emergency, tap RE-NOTIFY or call 999."
            ),
        )

    # Fetch phase1 record (may be None)
    p1_result = await db.execute(
        select(AlertPhase1Record).where(AlertPhase1Record.user_id == token.user_id)
    )
    phase1 = p1_result.scalars().first()

    # Resolve coordinates: prefer the live GPS in the request, but fall back to
    # the user's most recent location snapshot (kept fresh by the background
    # watchPosition) so a momentary getCurrentPosition failure on the panic
    # screen does not prevent zone creation + nearby fan-out.
    eff_lat, eff_lng = body.lat, body.lng
    eff_gps_status = GPSStatus(body.gps_status)
    if eff_lat is None or eff_lng is None:
        snap = await db.scalar(
            select(UserLocationSnapshot).where(UserLocationSnapshot.user_id == token.user_id)
        )
        if snap and snap.lat is not None and snap.lng is not None:
            eff_lat, eff_lng = snap.lat, snap.lng
            if eff_gps_status == GPSStatus.unavailable:
                eff_gps_status = GPSStatus.stale

    event = await alert_svc.create_alert_event(
        db,
        user_id=token.user_id,
        device_fp_hash=fp_hash,
        lat=eff_lat, lng=eff_lng,
        gps_accuracy_m=body.gps_accuracy_m,
        gps_status=eff_gps_status,
        tenant_id=token.tenant_id,
        phase1_record_id=phase1.id if phase1 else None,
    )

    zone = None
    if eff_lat and eff_lng:
        zone = await alert_svc.create_alert_zone(
            db, eff_lat, eff_lng, event.event_id, token.tenant_id
        )
        event.alert_zone_id = zone.id

    await audit_log(
        db, "alert_triggered", token.user_id, get_ip(request),
        {"event_id": str(event.event_id)},
    )
    await db.commit()

    await alert_svc.store_last_alert_time(redis, user_hash, event.event_id)

    # Background notifications — fire-and-return
    background_tasks.add_task(alert_svc.notify_proctor, event.event_id)
    if zone:
        background_tasks.add_task(alert_svc.notify_nearby_users, event.event_id, zone.id)
    if phase1:
        background_tasks.add_task(alert_svc.notify_contacts, event.event_id)

    return AlertTriggerResponse(
        event_id=event.event_id,
        state=event.state.value,
        message="Alert broadcast. Help is on the way.",
    )


# ─── My alerts history (static path — must be before /{event_id}) ────────────

@router.get("/v1/alerts/me")
@limiter.limit("30/minute")
async def list_my_alerts(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    """Return the authenticated user's own past alert events (most recent first)."""
    actor_hash = alert_svc.compute_anonymous_hash(token.user_id)
    result = await db.execute(
        select(AlertEvent)
        .where(AlertEvent.anonymous_actor_hash == actor_hash)
        .order_by(AlertEvent.created_at.desc())
        .limit(20)
    )
    events = result.scalars().all()
    return [
        {
            "event_id": str(ev.event_id),
            "state": ev.state.value if hasattr(ev.state, "value") else ev.state,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
            "closed_at": ev.closed_at.isoformat() if ev.closed_at else None,
            "closed_by": ev.closed_by,
            "lat": ev.lat,
            "lng": ev.lng,
        }
        for ev in events
    ]


# ─── Per-event endpoints (parameterised — must come AFTER static paths) ───────

@router.get("/v1/alerts/{event_id}", response_model=AlertStatusResponse)
@limiter.limit("60/minute")
async def get_alert_status(
    event_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    """Get the current status of an alert event. Lazily auto-closes expired events."""
    result = await db.execute(select(AlertEvent).where(AlertEvent.event_id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert not found")

    # Lazy auto-close after 24h
    closed = await alert_svc.auto_close_event_if_expired(db, event)
    if closed:
        await db.commit()

    resp_count = await db.scalar(
        select(func.count()).select_from(AlertResponse).where(
            and_(
                AlertResponse.event_id == event.id,
                AlertResponse.response_type == ResponseType.responding,
            )
        )
    )
    return AlertStatusResponse(
        event_id=event.event_id,
        state=event.state.value,
        created_at=event.created_at,
        closed_at=event.closed_at,
        responder_count=resp_count or 0,
        lat=event.lat,
        lng=event.lng,
    )


@router.get("/v1/alerts/{event_id}/responders", response_model=AlertRespondersResponse)
@limiter.limit("60/minute")
async def list_alert_responders(
    event_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    """
    List responders for an alert — owner only.

    Returns distance-only data (never responder coordinates) plus the alert
    zone radius, so the client can draw the fan-out ring and place responder
    dots at their real distance with a client-side randomised bearing.
    """
    result = await db.execute(select(AlertEvent).where(AlertEvent.event_id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert not found")

    actor_hash = alert_svc.compute_anonymous_hash(token.user_id)
    if event.anonymous_actor_hash != actor_hash:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authorized for this alert")

    # Zone radius — null-safe (no zone exists if GPS was unavailable at trigger)
    zone_radius_m = None
    if event.alert_zone_id:
        zone = await db.scalar(select(Zone).where(Zone.id == event.alert_zone_id))
        if zone:
            zone_radius_m = zone.radius_m

    rows = await db.execute(
        select(AlertResponse)
        .where(
            and_(
                AlertResponse.event_id == event.id,
                AlertResponse.response_type == ResponseType.responding,
            )
        )
        .order_by(AlertResponse.created_at)
    )
    responders = [
        ResponderItem(
            distance_m=r.distance_m,
            response_type=r.response_type.value,
            created_at=r.created_at,
        )
        for r in rows.scalars().all()
    ]
    return AlertRespondersResponse(
        event_id=event.event_id,
        zone_radius_m=zone_radius_m,
        responder_count=len(responders),
        responders=responders,
    )


@router.post("/v1/alerts/{event_id}/safe")
@limiter.limit("10/minute")
async def mark_safe(
    event_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    token: TokenData = Depends(get_current_user),
):
    """Alerting user marks themselves as safe — transitions state to user_safe."""
    actor_hash = alert_svc.compute_anonymous_hash(token.user_id)
    try:
        event = await alert_svc.mark_event_safe(db, event_id, actor_hash)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await audit_log(db, "alert_marked_safe", token.user_id, get_ip(request),
                    {"event_id": str(event_id)})
    await db.commit()
    return {"message": "Alert closed. Stay safe.", "state": event.state.value}


@router.post("/v1/alerts/{event_id}/need_more_help")
@limiter.limit("10/minute")
async def need_more_help(
    event_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    token: TokenData = Depends(get_current_user),
):
    """Resume the nearby fan-out if it was paused due to enough responders."""
    result = await db.execute(select(AlertEvent).where(AlertEvent.event_id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert not found")

    actor_hash = alert_svc.compute_anonymous_hash(token.user_id)
    if event.anonymous_actor_hash != actor_hash:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authorized for this alert")

    await alert_svc.resume_fanout(redis, event_id)
    if event.alert_zone_id:
        background_tasks.add_task(alert_svc.notify_nearby_users, event.event_id, event.alert_zone_id)

    return {"message": "Notifying more people nearby."}


@router.post("/v1/alerts/{event_id}/respond")
@limiter.limit("30/minute")
async def respond_to_alert(
    event_id: uuid.UUID,
    body: RespondRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    token: TokenData = Depends(get_current_user),
):
    """Record a responder action for an alert event."""
    result = await db.execute(select(AlertEvent).where(AlertEvent.event_id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert not found")

    responder_hash = alert_svc.compute_anonymous_hash(token.user_id)
    response = AlertResponse(
        event_id=event.id,
        responder_user_hash=responder_hash,
        response_type=ResponseType(body.response_type),
        distance_m=body.distance_m,
    )
    db.add(response)

    # Pause fan-out if enough responders
    if body.response_type == "responding":
        from app.config import get_settings
        resp_count = await db.scalar(
            select(func.count()).select_from(AlertResponse).where(
                and_(
                    AlertResponse.event_id == event.id,
                    AlertResponse.response_type == ResponseType.responding,
                )
            )
        )
        total_responding = (resp_count or 0) + 1
        if total_responding >= get_settings().alert_nearby_pause_threshold:
            await alert_svc.pause_fanout(redis, event_id)

    await db.commit()
    return {"message": "Response recorded.", "response_type": body.response_type}


@router.post("/v1/alerts/{event_id}/evidence", response_model=EvidenceUploadResponse)
@limiter.limit("20/minute")
async def upload_evidence(
    event_id: uuid.UUID,
    body: EvidenceUploadRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    """
    Phase 3 — record a reference to an encrypted evidence blob.
    The server stores the reference + SHA-256 hash only; the file itself
    is stored client-side (encrypted) and NOT uploaded here.
    """
    result = await db.execute(select(AlertEvent).where(AlertEvent.event_id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert not found")

    actor_hash = alert_svc.compute_anonymous_hash(token.user_id)
    if event.anonymous_actor_hash != actor_hash:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authorized for this alert")

    evidence = AlertEvidence(
        event_id=event.id,
        encrypted_blob_ref=body.encrypted_blob_ref,
        sha256_hash=body.sha256_hash,
        capture_timestamp=body.capture_timestamp,
        media_type=MediaType(body.media_type),
    )
    db.add(evidence)
    await db.commit()
    return evidence


# ─── User device + location management ───────────────────────────────────────

@router.post("/v1/users/me/fcm-token")
@limiter.limit("10/minute")
async def register_fcm_token(
    body: FCMTokenRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    """Register or refresh an FCM push token for the current user's device."""
    # Disable any existing token for this device_id
    existing = await db.execute(
        select(UserFCMToken).where(
            and_(
                UserFCMToken.user_id == token.user_id,
                UserFCMToken.device_id == body.device_id,
                UserFCMToken.disabled_at.is_(None),
            )
        )
    )
    for old in existing.scalars().all():
        from datetime import datetime, timezone
        old.disabled_at = datetime.now(tz=timezone.utc)

    new_token = UserFCMToken(
        user_id=token.user_id,
        fcm_token=body.fcm_token,
        device_id=body.device_id,
        platform=FCMPlatform(body.platform),
    )
    db.add(new_token)
    await db.commit()
    return {"message": "FCM token registered"}


@router.post("/v1/users/me/location")
@limiter.limit("60/minute")
async def update_location(
    body: LocationUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    """Update the current user's location snapshot for nearby-alert queries."""
    from datetime import datetime, timezone

    user_hash = alert_svc.compute_anonymous_hash(token.user_id)

    existing = await db.execute(
        select(UserLocationSnapshot).where(UserLocationSnapshot.user_id == token.user_id)
    )
    snapshot = existing.scalars().first()
    if snapshot:
        snapshot.lat = body.lat
        snapshot.lng = body.lng
        snapshot.geofence_consent = body.geofence_consent
        snapshot.last_seen_at = datetime.now(tz=timezone.utc)
    else:
        snapshot = UserLocationSnapshot(
            user_id=token.user_id,
            user_id_hash=user_hash,
            lat=body.lat,
            lng=body.lng,
            geofence_consent=body.geofence_consent,
        )
        db.add(snapshot)

    await db.commit()
    return {"message": "Location updated"}
