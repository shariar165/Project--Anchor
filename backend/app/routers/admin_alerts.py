"""
Admin / Proctor dashboard endpoints for the Emergency Alert System.

Access levels:
  moderator — list, detail, ack, resolve (own tenant only)
  admin     — everything above + false-alert (which triggers a 30-day ban)
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.limiter import limiter
from app.models.alert import (
    AlertEvent, AlertNotification, AlertResponse, AlertEvidence,
    Zone, AlertBan, AlertState, ZoneStatus,
)
from app.models.user import Role
from app.redis import get_redis
from app.services import alert_svc
from app.services.audit import log_event as audit_log
from app.services.device import get_ip

router = APIRouter(prefix="/v1/admin", tags=["admin-alerts"])


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ─── List alerts ─────────────────────────────────────────────────────────────

@router.get("/alerts")
@limiter.limit("120/minute")
async def list_alerts(
    request: Request,
    state: str | None = Query(default=None, description="Filter by state: active|user_safe|closed|false_alert|resolved"),
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """
    List alert events for the admin/proctor dashboard.
    Moderators are automatically restricted to their own tenant.
    """
    q = select(AlertEvent).order_by(desc(AlertEvent.created_at))

    # State filter
    if state:
        try:
            q = q.where(AlertEvent.state == AlertState(state))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid state: {state}")

    # Tenant scoping
    if token.role == Role.moderator and token.tenant_id:
        # Moderators only see their own tenant
        q = q.where(AlertEvent.tenant_id == token.tenant_id)
    elif tenant_id:
        try:
            q = q.where(AlertEvent.tenant_id == uuid.UUID(tenant_id))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid tenant_id")

    # Total count (before pagination)
    count_q = select(func.count()).select_from(q.subquery())
    total = await db.scalar(count_q) or 0

    # Paginated results
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    events = result.scalars().all()

    items = []
    for ev in events:
        # Count responders
        resp_count = await db.scalar(
            select(func.count()).select_from(AlertResponse).where(AlertResponse.event_id == ev.id)
        ) or 0
        # Count notifications sent
        notif_count = await db.scalar(
            select(func.count()).select_from(AlertNotification).where(AlertNotification.event_id == ev.id)
        ) or 0
        items.append({
            "event_id": str(ev.event_id),
            "state": ev.state.value,
            "created_at": ev.created_at.isoformat(),
            "closed_at": ev.closed_at.isoformat() if ev.closed_at else None,
            "closed_by": ev.closed_by,
            "lat": ev.lat,
            "lng": ev.lng,
            "gps_status": ev.gps_status.value,
            "tenant_id": str(ev.tenant_id) if ev.tenant_id else None,
            "responder_count": resp_count,
            "notification_count": notif_count,
        })

    return {"items": items, "total": total, "limit": limit, "offset": offset}


# ─── Alert detail ────────────────────────────────────────────────────────────

@router.get("/alerts/{event_id}")
@limiter.limit("120/minute")
async def get_alert_detail(
    event_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Full alert detail including notifications, responses, zone, and evidence count."""
    result = await db.execute(select(AlertEvent).where(AlertEvent.event_id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert not found")

    # Tenant gate for moderators
    if token.role == Role.moderator and token.tenant_id and event.tenant_id != token.tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Alert is outside your tenant")

    # Notifications
    notif_result = await db.execute(
        select(AlertNotification).where(AlertNotification.event_id == event.id)
        .order_by(AlertNotification.created_at)
    )
    notifications = [
        {
            "recipient_type": n.recipient_type.value,
            "channel": n.channel.value,
            "status": n.status.value,
            "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            "attempts": n.attempts,
        }
        for n in notif_result.scalars().all()
    ]

    # Responses
    resp_result = await db.execute(
        select(AlertResponse).where(AlertResponse.event_id == event.id)
        .order_by(AlertResponse.created_at)
    )
    responses = [
        {
            "response_type": r.response_type.value,
            "distance_m": r.distance_m,
            "created_at": r.created_at.isoformat(),
        }
        for r in resp_result.scalars().all()
    ]

    # Zone
    zone_data = None
    if event.alert_zone_id:
        zr = await db.execute(select(Zone).where(Zone.id == event.alert_zone_id))
        zone = zr.scalars().first()
        if zone:
            zone_data = {
                "id": str(zone.id),
                "zone_type": zone.zone_type.value,
                "center_lat": zone.center_lat,
                "center_lng": zone.center_lng,
                "radius_m": zone.radius_m,
                "status": zone.status.value,
                "expires_at": zone.expires_at.isoformat() if zone.expires_at else None,
                "label": zone.label,
            }

    # Evidence count
    ev_count = await db.scalar(
        select(func.count()).select_from(AlertEvidence).where(AlertEvidence.event_id == event.id)
    ) or 0

    return {
        "event_id": str(event.event_id),
        "state": event.state.value,
        "created_at": event.created_at.isoformat(),
        "closed_at": event.closed_at.isoformat() if event.closed_at else None,
        "closed_by": event.closed_by,
        "lat": event.lat,
        "lng": event.lng,
        "gps_status": event.gps_status.value,
        "tenant_id": str(event.tenant_id) if event.tenant_id else None,
        "zone": zone_data,
        "notifications": notifications,
        "responses": responses,
        "evidence_count": ev_count,
    }


# ─── Proctor acknowledges alert ───────────────────────────────────────────────

@router.post("/alerts/{event_id}/ack")
@limiter.limit("30/minute")
async def ack_alert(
    event_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Proctor acknowledges awareness of the alert. Does not change alert state."""
    result = await db.execute(select(AlertEvent).where(AlertEvent.event_id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert not found")

    if token.role == Role.moderator and token.tenant_id and event.tenant_id != token.tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Alert is outside your tenant")

    # Store acknowledgement in Redis (lightweight, no DB state change)
    await redis.set(
        f"alert_acked:{event_id}",
        str(token.user_id),
        ex=86400,
    )
    await audit_log(db, "alert_acked_by_admin", token.user_id, get_ip(request),
                    {"event_id": str(event_id)})
    await db.commit()
    return {"message": "Alert acknowledged", "event_id": str(event_id), "state": event.state.value}


# ─── Resolve alert ────────────────────────────────────────────────────────────

@router.post("/alerts/{event_id}/resolve")
@limiter.limit("30/minute")
async def resolve_alert(
    event_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Mark an alert as formally resolved (e.g. police responded, situation handled)."""
    result = await db.execute(select(AlertEvent).where(AlertEvent.event_id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert not found")

    if token.role == Role.moderator and token.tenant_id and event.tenant_id != token.tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Alert is outside your tenant")

    if event.state not in (AlertState.active, AlertState.user_safe):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resolve alert in state '{event.state.value}'",
        )

    event.state = AlertState.resolved
    event.closed_at = _now()
    event.closed_by = "admin"

    # Archive linked zone
    if event.alert_zone_id:
        zr = await db.execute(select(Zone).where(Zone.id == event.alert_zone_id))
        zone = zr.scalars().first()
        if zone:
            zone.status = ZoneStatus.archived

    await audit_log(db, "alert_resolved_by_admin", token.user_id, get_ip(request),
                    {"event_id": str(event_id)})
    await db.commit()
    return {"message": "Alert resolved", "state": "resolved"}


# ─── Mark as false alert (admin only) ────────────────────────────────────────

@router.post("/alerts/{event_id}/false")
@limiter.limit("20/minute")
async def mark_false_alert(
    event_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin")),  # admin only
):
    """
    Mark an alert as a confirmed false alarm.
    Triggers a 30-day ban on the triggering device fingerprint.
    Requires admin role — moderators cannot apply bans.
    """
    result = await db.execute(select(AlertEvent).where(AlertEvent.event_id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert not found")

    if event.state == AlertState.false_alert:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Alert is already marked as false")

    event.state = AlertState.false_alert
    event.closed_at = _now()
    event.closed_by = "false_alert_finding"

    # Archive linked zone
    if event.alert_zone_id:
        zr = await db.execute(select(Zone).where(Zone.id == event.alert_zone_id))
        zone = zr.scalars().first()
        if zone:
            zone.status = ZoneStatus.archived

    # 30-day ban on the device fingerprint
    await alert_svc.apply_ban(
        db,
        user_id=None,  # preserve anonymity — no plaintext user_id stored on event
        device_fp_hash=event.device_fingerprint_hash,
        reason=f"false_alert confirmed by admin — event {event_id}",
    )

    await audit_log(db, "alert_marked_false_by_admin", token.user_id, get_ip(request),
                    {"event_id": str(event_id), "device_fp": event.device_fingerprint_hash[:8] + "…"})
    await db.commit()
    return {
        "message": "Alert marked as false. 30-day device ban applied.",
        "state": "false_alert",
        "event_id": str(event_id),
    }


# ─── List active zones (admin map view) ──────────────────────────────────────

@router.get("/zones")
@limiter.limit("60/minute")
async def list_zones(
    request: Request,
    zone_type: str | None = Query(default=None, description="Filter: alert|rape|murder|university"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter: active|archived"),
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Return zones for the admin map view (alert zones, static risk zones)."""
    from app.models.alert import ZoneType, ZoneStatus as ZS

    q = select(Zone).order_by(desc(Zone.created_at))

    if zone_type:
        try:
            q = q.where(Zone.zone_type == ZoneType(zone_type))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid zone_type: {zone_type}")

    if status_filter:
        try:
            q = q.where(Zone.status == ZS(status_filter))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid status: {status_filter}")

    if token.role == Role.moderator and token.tenant_id:
        q = q.where(Zone.tenant_id == token.tenant_id)
    elif tenant_id:
        try:
            q = q.where(Zone.tenant_id == uuid.UUID(tenant_id))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid tenant_id")

    q = q.limit(limit)
    result = await db.execute(q)
    zones = result.scalars().all()

    return [
        {
            "id": str(z.id),
            "zone_type": z.zone_type.value,
            "center_lat": z.center_lat,
            "center_lng": z.center_lng,
            "radius_m": z.radius_m,
            "status": z.status.value,
            "label": z.label,
            "description_public": z.description_public,
            "related_alert_id": str(z.related_alert_id) if z.related_alert_id else None,
            "tenant_id": str(z.tenant_id) if z.tenant_id else None,
            "expires_at": z.expires_at.isoformat() if z.expires_at else None,
            "created_at": z.created_at.isoformat(),
        }
        for z in zones
    ]
