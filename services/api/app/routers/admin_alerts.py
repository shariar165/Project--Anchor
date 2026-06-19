"""
Admin / Proctor dashboard endpoints for the Emergency Alert System.

Access levels:
  moderator — list, detail, ack, resolve (own tenant only)
  admin     — everything above + false-alert (which triggers a 30-day ban)
"""
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.limiter import limiter
from app.models.alert import (
    AlertEvent, AlertNotification, AlertResponse, AlertEvidence,
    AlertAdminAction, Zone, AlertBan, AlertState, ZoneStatus, ResponseType,
    AlertActionType,
)
from app.models.user import Role, User
from app.redis import get_redis
from app.services import alert_svc
from app.services.audit import log_event as audit_log, mask_email
from app.services.device import get_ip

router = APIRouter(prefix="/v1/admin", tags=["admin-alerts"])


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ─── Push / fan-out health ───────────────────────────────────────────────────
# Registered before /alerts/{event_id} so "push-health" isn't parsed as a UUID.

@router.get("/alerts/push-health")
@limiter.limit("60/minute")
async def push_health(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "super_admin")),
):
    """
    Push-notification + fan-out health for operators (aggregates only, no PII).
    Secure, admin-gated replacement for the temporary unauthenticated _diag
    endpoints used during deployment bring-up.
    """
    from app.config import get_settings
    from app.models.alert import (
        UserFCMToken, UserLocationSnapshot, NotifChannel, NotifStatus,
    )
    from app.services import fcm as fcm_svc

    settings = get_settings()
    fcm_app = fcm_svc._get_app()
    # The project the Admin SDK is actually authenticated for (from the
    # service-account JSON) — this must match the client's Firebase project or
    # every push fails as SenderIdMismatch.
    EXPECTED_CLIENT_PROJECT = "project-anchor-e008b"
    credential_project_id = fcm_svc.get_credential_project_id()
    project_match = bool(credential_project_id) and credential_project_id == EXPECTED_CLIENT_PROJECT
    cutoff = _now() - timedelta(minutes=settings.alert_location_staleness_minutes)
    day_ago = _now() - timedelta(hours=24)

    active_tokens = await db.scalar(
        select(func.count()).select_from(UserFCMToken).where(UserFCMToken.disabled_at.is_(None))
    )
    disabled_tokens = await db.scalar(
        select(func.count()).select_from(UserFCMToken).where(UserFCMToken.disabled_at.is_not(None))
    )
    consenting_recent = await db.scalar(
        select(func.count()).select_from(UserLocationSnapshot).where(
            and_(
                UserLocationSnapshot.geofence_consent == True,  # noqa: E712
                UserLocationSnapshot.last_seen_at >= cutoff,
            )
        )
    )
    sent_24h = await db.scalar(
        select(func.count()).select_from(AlertNotification).where(
            and_(
                AlertNotification.channel == NotifChannel.push,
                AlertNotification.status == NotifStatus.sent,
                AlertNotification.last_attempt_at >= day_ago,
            )
        )
    )
    failed_24h = await db.scalar(
        select(func.count()).select_from(AlertNotification).where(
            and_(
                AlertNotification.channel == NotifChannel.push,
                AlertNotification.status == NotifStatus.failed,
                AlertNotification.last_attempt_at >= day_ago,
            )
        )
    )
    return {
        "fcm_configured": fcm_app is not None,
        "fcm_project_id": settings.fcm_project_id or None,
        "credential_project_id": credential_project_id,
        "expected_client_project": EXPECTED_CLIENT_PROJECT,
        "project_match": project_match,
        "active_tokens": active_tokens or 0,
        "disabled_tokens": disabled_tokens or 0,
        "consenting_recent_devices": consenting_recent or 0,
        "staleness_minutes": settings.alert_location_staleness_minutes,
        "recent_push": {"sent": sent_24h or 0, "failed": failed_24h or 0},
    }


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


# ─── Alert stats / KPIs ──────────────────────────────────────────────────────

@router.get("/alerts/stats")
@limiter.limit("60/minute")
async def get_alert_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Aggregated KPI and analytics data for the admin alerts dashboard."""
    now = _now()
    cutoff_24h = now - timedelta(hours=24)
    cutoff_30d = now - timedelta(days=30)

    def _scope(q):
        if token.role == Role.moderator and token.tenant_id:
            return q.where(AlertEvent.tenant_id == token.tenant_id)
        return q

    # active_count
    active_count = await db.scalar(
        _scope(select(func.count()).select_from(AlertEvent).where(AlertEvent.state == AlertState.active))
    ) or 0

    # resolved_24h — any terminal state closed in the last 24 h
    resolved_24h = await db.scalar(
        _scope(
            select(func.count()).select_from(AlertEvent).where(
                and_(
                    AlertEvent.closed_at >= cutoff_24h,
                    AlertEvent.state.in_([AlertState.resolved, AlertState.closed, AlertState.false_alert]),
                )
            )
        )
    ) or 0

    # false_alarms_30d
    false_alarms_30d = await db.scalar(
        _scope(
            select(func.count()).select_from(AlertEvent).where(
                and_(
                    AlertEvent.state == AlertState.false_alert,
                    AlertEvent.created_at >= cutoff_30d,
                )
            )
        )
    ) or 0

    # avg_response_secs_24h — Python-side to stay dialect-agnostic (SQLite + PG)
    resp_q = (
        select(AlertEvent.created_at, AlertResponse.created_at.label("responded_at"))
        .join(AlertResponse, AlertResponse.event_id == AlertEvent.id)
        .where(
            and_(
                AlertResponse.response_type == ResponseType.responding,
                AlertResponse.created_at >= cutoff_24h,
            )
        )
    )
    if token.role == Role.moderator and token.tenant_id:
        resp_q = resp_q.where(AlertEvent.tenant_id == token.tenant_id)
    resp_rows = (await db.execute(resp_q)).all()

    avg_response_secs_24h = None
    if resp_rows:
        deltas = []
        for ev_ts, resp_ts in resp_rows:
            if ev_ts.tzinfo is None:
                ev_ts = ev_ts.replace(tzinfo=timezone.utc)
            if resp_ts.tzinfo is None:
                resp_ts = resp_ts.replace(tzinfo=timezone.utc)
            secs = (resp_ts - ev_ts).total_seconds()
            if secs >= 0:
                deltas.append(secs)
        if deltas:
            avg_response_secs_24h = round(sum(deltas) / len(deltas))

    # by_tenant_30d — alert count per tenant in last 30 days
    by_tenant_rows = (await db.execute(
        _scope(
            select(AlertEvent.tenant_id, func.count().label("cnt"))
            .where(AlertEvent.created_at >= cutoff_30d)
            .group_by(AlertEvent.tenant_id)
        )
    )).all()
    by_tenant_30d = [
        {"tenant_id": str(r.tenant_id) if r.tenant_id else None, "count": r.cnt}
        for r in by_tenant_rows
    ]

    # by_zone_type_30d — join alerts → zones, group by zone type
    by_zone_q = (
        select(Zone.zone_type, func.count().label("cnt"))
        .join(AlertEvent, AlertEvent.alert_zone_id == Zone.id)
        .where(AlertEvent.created_at >= cutoff_30d)
        .group_by(Zone.zone_type)
    )
    if token.role == Role.moderator and token.tenant_id:
        by_zone_q = by_zone_q.where(AlertEvent.tenant_id == token.tenant_id)
    by_zone_rows = (await db.execute(by_zone_q)).all()
    by_zone_type_30d = [
        {"zone_type": r.zone_type.value, "count": r.cnt}
        for r in by_zone_rows
    ]

    # resolution_histogram_30d — Python-side bucketing, dialect-agnostic
    hist_rows = (await db.execute(
        _scope(
            select(AlertEvent.created_at, AlertEvent.closed_at)
            .where(
                and_(
                    AlertEvent.closed_at.isnot(None),
                    AlertEvent.created_at >= cutoff_30d,
                )
            )
        )
    )).all()

    BUCKETS = [
        ("<2m",    0,    120),
        ("2–5m",   120,  300),
        ("5–10m",  300,  600),
        ("10–30m", 600,  1800),
        (">30m",   1800, None),
    ]
    counts = {b[0]: 0 for b in BUCKETS}
    for ev_ts, closed_ts in hist_rows:
        if ev_ts.tzinfo is None:
            ev_ts = ev_ts.replace(tzinfo=timezone.utc)
        if closed_ts.tzinfo is None:
            closed_ts = closed_ts.replace(tzinfo=timezone.utc)
        secs = max(0, (closed_ts - ev_ts).total_seconds())
        for label, lo, hi in BUCKETS:
            if hi is None or secs < hi:
                counts[label] += 1
                break

    return {
        "active_count": active_count,
        "resolved_24h": resolved_24h,
        "false_alarms_30d": false_alarms_30d,
        "avg_response_secs_24h": avg_response_secs_24h,
        "by_tenant_30d": by_tenant_30d,
        "by_zone_type_30d": by_zone_type_30d,
        "resolution_histogram_30d": [
            {"bucket": label, "count": counts[label]} for label, _, _ in BUCKETS
        ],
    }


# ─── Export alert log as CSV ──────────────────────────────────────────────────
# NOTE: must be declared BEFORE "/alerts/{event_id}" so "export" is not captured
# as an event_id path param (FastAPI matches in declaration order).

@router.get("/alerts/export")
@limiter.limit("10/minute")
async def export_alerts(
    request: Request,
    window: str = Query(default="24h", description="Time window: 24h|7d|30d"),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Export alert events within a time window as CSV. Moderators are tenant-scoped."""
    import csv
    import io
    from fastapi.responses import Response

    windows = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
    if window not in windows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="window must be one of: 24h, 7d, 30d")
    cutoff = _now() - windows[window]

    q = select(AlertEvent).where(AlertEvent.created_at >= cutoff).order_by(desc(AlertEvent.created_at))
    if token.role == Role.moderator and token.tenant_id:
        q = q.where(AlertEvent.tenant_id == token.tenant_id)
    events = (await db.execute(q)).scalars().all()

    buf = io.StringIO()
    now_iso = _now().isoformat()
    buf.write(f"# Anchor AI alert export — window={window} exported_by={token.user_id} at {now_iso}\n")
    writer = csv.writer(buf)
    writer.writerow(["event_id", "state", "created_at", "closed_at", "closed_by",
                     "lat", "lng", "gps_status", "tenant_id"])
    for ev in events:
        writer.writerow([
            str(ev.event_id), ev.state.value, ev.created_at.isoformat(),
            ev.closed_at.isoformat() if ev.closed_at else "",
            ev.closed_by or "", ev.lat if ev.lat is not None else "",
            ev.lng if ev.lng is not None else "", ev.gps_status.value,
            str(ev.tenant_id) if ev.tenant_id else "",
        ])

    filename = f"anchor-alerts-{window}-{_now().strftime('%Y%m%d-%H%M%S')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Alert detail ────────────────────────────────────────────────────────────

@router.get("/alerts/{event_id}")
@limiter.limit("120/minute")
async def get_alert_detail(
    event_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Full alert detail including notifications, responses, zone, admin actions, and evidence count."""
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

    # Admin/proctor actions (dispatch, notify-university, anonymous-call) with masked actor
    aa_result = await db.execute(
        select(AlertAdminAction, User)
        .outerjoin(User, AlertAdminAction.actor_user_id == User.id)
        .where(AlertAdminAction.event_id == event.id)
        .order_by(AlertAdminAction.created_at)
    )
    admin_actions = [
        {
            "action_type": a.action_type.value,
            "actor": mask_email(u.email if u else None),
            "note": a.note,
            "created_at": a.created_at.isoformat(),
        }
        for a, u in aa_result.all()
    ]

    # Acknowledgement marker (lightweight, stored in Redis by /ack)
    acked = bool(await redis.get(f"alert_acked:{event.event_id}"))

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
        "admin_actions": admin_actions,
        "acked": acked,
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


# ─── Admin/proctor actions on an alert (dispatch / notify / call) ────────────

from pydantic import BaseModel


class AlertActionBody(BaseModel):
    note: str | None = None


async def _load_event_with_tenant_gate(db, event_id: uuid.UUID, token: TokenData) -> AlertEvent:
    result = await db.execute(select(AlertEvent).where(AlertEvent.event_id == event_id))
    event = result.scalars().first()
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if token.role == Role.moderator and token.tenant_id and event.tenant_id != token.tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Alert is outside your tenant")
    return event


async def _record_admin_action(
    db, request: Request, token: TokenData,
    event: AlertEvent, action_type: AlertActionType, note: str | None, audit_event: str,
) -> AlertAdminAction:
    action = AlertAdminAction(
        event_id=event.id,
        action_type=action_type,
        actor_user_id=token.user_id,
        note=note,
    )
    db.add(action)
    await audit_log(db, audit_event, token.user_id, get_ip(request),
                    {"event_id": str(event.event_id), "action": action_type.value})
    await db.commit()
    await db.refresh(action)
    return action


@router.post("/alerts/{event_id}/dispatch")
@limiter.limit("30/minute")
async def dispatch_response(
    event_id: uuid.UUID,
    request: Request,
    body: AlertActionBody | None = None,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Record that a response team was dispatched for this alert. Audit-logged."""
    event = await _load_event_with_tenant_gate(db, event_id, token)
    note = body.note if body else None
    action = await _record_admin_action(
        db, request, token, event, AlertActionType.dispatch, note, "alert_dispatched_by_admin")
    return {
        "message": "Response dispatched",
        "event_id": str(event_id),
        "action_type": action.action_type.value,
        "created_at": action.created_at.isoformat(),
    }


@router.post("/alerts/{event_id}/notify-university")
@limiter.limit("30/minute")
async def notify_university(
    event_id: uuid.UUID,
    request: Request,
    body: AlertActionBody | None = None,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Record that the university (tenant admins) were notified about this alert."""
    event = await _load_event_with_tenant_gate(db, event_id, token)
    note = body.note if body else None
    action = await _record_admin_action(
        db, request, token, event, AlertActionType.notify_university, note, "alert_university_notified")
    return {
        "message": "University notified",
        "event_id": str(event_id),
        "action_type": action.action_type.value,
        "created_at": action.created_at.isoformat(),
    }


@router.post("/alerts/{event_id}/anonymous-call")
@limiter.limit("30/minute")
async def anonymous_call(
    event_id: uuid.UUID,
    request: Request,
    body: AlertActionBody | None = None,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Record that an anonymized call bridge to the reporter was initiated."""
    event = await _load_event_with_tenant_gate(db, event_id, token)
    note = body.note if body else None
    action = await _record_admin_action(
        db, request, token, event, AlertActionType.anonymous_call, note, "alert_anonymous_call_initiated")
    return {
        "message": "Anonymous call initiated",
        "event_id": str(event_id),
        "action_type": action.action_type.value,
        "created_at": action.created_at.isoformat(),
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


# ─── Create zone (super admin / admin) ───────────────────────────────────────

from pydantic import BaseModel, field_validator

class ZoneCreateBody(BaseModel):
    zone_type: str
    center_lat: float
    center_lng: float
    radius_m: int | None = None
    label: str | None = None
    description_public: str | None = None
    expires_at: datetime | None = None
    tenant_id: uuid.UUID | None = None

    @field_validator("zone_type")
    @classmethod
    def _validate_zone_type(cls, v):
        from app.models.alert import ZoneType
        try:
            ZoneType(v)
        except ValueError:
            raise ValueError(f"Invalid zone_type '{v}'. Must be one of: rape, murder, alert, university, red, purple, black")
        return v

    @field_validator("radius_m")
    @classmethod
    def _validate_radius(cls, v):
        if v is not None and not (50 <= v <= 50000):
            raise ValueError("radius_m must be between 50 and 50000")
        return v

    @field_validator("center_lat")
    @classmethod
    def _validate_lat(cls, v):
        if not (-90 <= v <= 90):
            raise ValueError("center_lat must be between -90 and 90")
        return v

    @field_validator("center_lng")
    @classmethod
    def _validate_lng(cls, v):
        if not (-180 <= v <= 180):
            raise ValueError("center_lng must be between -180 and 180")
        return v


@router.post("/zones", status_code=201)
@limiter.limit("30/minute")
async def create_zone(
    body: ZoneCreateBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin")),
):
    """Create a new risk/safety zone. Admin only."""
    from app.models.alert import ZoneType, ZoneStatus as ZS

    zone = Zone(
        zone_type=ZoneType(body.zone_type),
        center_lat=body.center_lat,
        center_lng=body.center_lng,
        radius_m=body.radius_m if body.radius_m else 300,
        label=body.label,
        description_public=body.description_public,
        expires_at=body.expires_at,
        tenant_id=body.tenant_id,
        status=ZS.active,
    )
    db.add(zone)
    await audit_log(db, "zone_created_by_admin", token.user_id, get_ip(request), {
        "zone_type": body.zone_type,
        "label": body.label,
        "center_lat": body.center_lat,
        "center_lng": body.center_lng,
        "radius_m": body.radius_m,
    })
    await db.commit()
    await db.refresh(zone)
    return {
        "id": str(zone.id),
        "zone_type": zone.zone_type.value,
        "center_lat": zone.center_lat,
        "center_lng": zone.center_lng,
        "radius_m": zone.radius_m,
        "status": zone.status.value,
        "label": zone.label,
        "description_public": zone.description_public,
        "tenant_id": str(zone.tenant_id) if zone.tenant_id else None,
        "expires_at": zone.expires_at.isoformat() if zone.expires_at else None,
        "created_at": zone.created_at.isoformat(),
    }


# ─── Update zone ──────────────────────────────────────────────────────────────

class ZonePatchBody(BaseModel):
    label: str | None = None
    description_public: str | None = None
    radius_m: int | None = None
    status: str | None = None
    expires_at: datetime | None = None

    @field_validator("radius_m")
    @classmethod
    def _validate_radius(cls, v):
        if v is not None and not (50 <= v <= 10000):
            raise ValueError("radius_m must be between 50 and 10000")
        return v

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v):
        if v is not None:
            from app.models.alert import ZoneStatus as ZS
            try:
                ZS(v)
            except ValueError:
                raise ValueError(f"Invalid status '{v}'. Must be: active or archived")
        return v


@router.patch("/zones/{zone_id}")
@limiter.limit("30/minute")
async def update_zone(
    zone_id: uuid.UUID,
    body: ZonePatchBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin")),
):
    """Update zone metadata. Admin only."""
    from app.models.alert import ZoneStatus as ZS

    result = await db.execute(select(Zone).where(Zone.id == zone_id))
    zone = result.scalars().first()
    if not zone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Zone not found")

    if body.label is not None:
        zone.label = body.label
    if body.description_public is not None:
        zone.description_public = body.description_public
    if body.radius_m is not None:
        zone.radius_m = body.radius_m
    if body.status is not None:
        zone.status = ZS(body.status)
    if body.expires_at is not None:
        zone.expires_at = body.expires_at

    await audit_log(db, "zone_updated_by_admin", token.user_id, get_ip(request), {
        "zone_id": str(zone_id),
        "changes": body.model_dump(exclude_none=True),
    })
    await db.commit()
    await db.refresh(zone)
    return {
        "id": str(zone.id),
        "zone_type": zone.zone_type.value,
        "center_lat": zone.center_lat,
        "center_lng": zone.center_lng,
        "radius_m": zone.radius_m,
        "status": zone.status.value,
        "label": zone.label,
        "description_public": zone.description_public,
        "tenant_id": str(zone.tenant_id) if zone.tenant_id else None,
        "expires_at": zone.expires_at.isoformat() if zone.expires_at else None,
        "created_at": zone.created_at.isoformat(),
    }


# ─── Archive zone ─────────────────────────────────────────────────────────────

@router.delete("/zones/{zone_id}", status_code=200)
@limiter.limit("30/minute")
async def archive_zone(
    zone_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin")),
):
    """Archive (soft-delete) a zone. Admin only."""
    result = await db.execute(select(Zone).where(Zone.id == zone_id))
    zone = result.scalars().first()
    if not zone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Zone not found")

    if zone.status == ZoneStatus.archived:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Zone is already archived")

    zone.status = ZoneStatus.archived
    await audit_log(db, "zone_archived_by_admin", token.user_id, get_ip(request), {
        "zone_id": str(zone_id),
        "zone_type": zone.zone_type.value,
        "label": zone.label,
    })
    await db.commit()
    return {"message": "Zone archived", "zone_id": str(zone_id)}
