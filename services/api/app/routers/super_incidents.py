"""Super-admin platform incident tracker.

Routes: /v1/super-admin/incidents
Auth: super_admin role only.

A persistent incident log with a severity, a lifecycle status, the affected
component, and an append-only timeline of updates. Every mutation is written to
the SHA-256 audit hash chain.
"""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import require_role, TokenData
from app.limiter import limiter
from app.models.incident import (
    Incident, IncidentUpdate,
    INCIDENT_SEVERITIES, INCIDENT_STATUSES, OPEN_STATUSES,
)
from app.services.audit import log_event as audit_log
from app.services.device import get_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/super-admin/incidents", tags=["super-admin-incidents"])


# ── Schemas ────────────────────────────────────────────────────────────────
class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    severity: str = "sev3"
    component: str | None = Field(default=None, max_length=60)
    status: str = "investigating"
    started_at: datetime | None = None


class IncidentPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    severity: str | None = None
    status: str | None = None
    component: str | None = Field(default=None, max_length=60)
    postmortem: str | None = None
    note: str | None = None  # optional note attached to a status/field change


class IncidentUpdateCreate(BaseModel):
    note: str = Field(min_length=1)
    status: str | None = None


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite returns tz-naive datetimes; normalize to UTC for arithmetic/output."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _validate_severity(sev: str) -> None:
    if sev not in INCIDENT_SEVERITIES:
        raise HTTPException(422, detail=f"severity must be one of {INCIDENT_SEVERITIES}")


def _validate_status(st: str) -> None:
    if st not in INCIDENT_STATUSES:
        raise HTTPException(422, detail=f"status must be one of {INCIDENT_STATUSES}")


def _mttr_seconds(inc: Incident) -> int | None:
    if inc.resolved_at is None:
        return None
    started = _aware(inc.started_at)
    resolved = _aware(inc.resolved_at)
    return int((resolved - started).total_seconds())


def _serialize_update(u: IncidentUpdate) -> dict:
    return {
        "id": str(u.id),
        "status": u.status,
        "note": u.note,
        "created_by": str(u.created_by) if u.created_by else None,
        "created_at": _aware(u.created_at).isoformat() if u.created_at else None,
    }


def _serialize(inc: Incident, with_updates: bool = False) -> dict:
    data = {
        "id": str(inc.id),
        "title": inc.title,
        "description": inc.description,
        "severity": inc.severity,
        "status": inc.status,
        "component": inc.component,
        "tenant_id": str(inc.tenant_id) if inc.tenant_id else None,
        "created_by": str(inc.created_by) if inc.created_by else None,
        "started_at": _aware(inc.started_at).isoformat() if inc.started_at else None,
        "resolved_at": _aware(inc.resolved_at).isoformat() if inc.resolved_at else None,
        "postmortem": inc.postmortem,
        "is_open": inc.status in OPEN_STATUSES,
        "mttr_seconds": _mttr_seconds(inc),
        "created_at": _aware(inc.created_at).isoformat() if inc.created_at else None,
        "updated_at": _aware(inc.updated_at).isoformat() if inc.updated_at else None,
    }
    if with_updates:
        data["updates"] = [_serialize_update(u) for u in inc.updates]
    return data


def _add_update(inc: Incident, actor_id: uuid.UUID, note: str, status: str | None) -> None:
    inc.updates.append(IncidentUpdate(
        status=status,
        note=note,
        created_by=actor_id,
        created_at=_utcnow(),
    ))


# ── Routes ─────────────────────────────────────────────────────────────────
@router.get("")
@limiter.limit("60/minute")
async def list_incidents(
    request: Request,
    status: str | None = Query(default=None),
    open_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """List incidents, newest first. Filter by ?status= or ?open_only=true."""
    stmt = select(Incident)
    if status:
        _validate_status(status)
        stmt = stmt.where(Incident.status == status)
    elif open_only:
        stmt = stmt.where(Incident.status.in_(OPEN_STATUSES))
    stmt = stmt.order_by(desc(Incident.started_at)).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    open_count = sum(1 for r in rows if r.status in OPEN_STATUSES)
    return {
        "items": [_serialize(r) for r in rows],
        "total": len(rows),
        "open_count": open_count,
    }


@router.post("")
@limiter.limit("30/minute")
async def create_incident(
    body: IncidentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Declare a new incident. Seeds the timeline with an opening update."""
    _validate_severity(body.severity)
    _validate_status(body.status)

    inc = Incident(
        title=body.title.strip(),
        description=(body.description or "").strip() or None,
        severity=body.severity,
        status=body.status,
        component=(body.component or "").strip() or None,
        created_by=token.user_id,
        started_at=_aware(body.started_at) or _utcnow(),
        resolved_at=_utcnow() if body.status == "resolved" else None,
    )
    _add_update(inc, token.user_id, f"Incident declared ({body.severity}).", body.status)
    db.add(inc)
    await db.flush()

    await audit_log(db, "incident_created", token.user_id, get_ip(request), {
        "incident_id": str(inc.id),
        "severity": inc.severity,
        "status": inc.status,
        "component": inc.component,
        "title": inc.title,
    })
    await db.commit()
    await db.refresh(inc)
    # Re-load with updates eagerly for the response.
    inc = await _get_with_updates(db, inc.id)
    return _serialize(inc, with_updates=True)


async def _get_with_updates(db: AsyncSession, incident_id: uuid.UUID) -> Incident | None:
    stmt = select(Incident).where(Incident.id == incident_id).options(selectinload(Incident.updates))
    return (await db.execute(stmt)).scalars().first()


@router.get("/{incident_id}")
@limiter.limit("120/minute")
async def get_incident(
    incident_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    inc = await _get_with_updates(db, incident_id)
    if inc is None:
        raise HTTPException(404, detail="Incident not found")
    return _serialize(inc, with_updates=True)


@router.patch("/{incident_id}")
@limiter.limit("60/minute")
async def patch_incident(
    incident_id: uuid.UUID,
    body: IncidentPatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    inc = await _get_with_updates(db, incident_id)
    if inc is None:
        raise HTTPException(404, detail="Incident not found")

    changed: dict = {}

    if body.title is not None:
        inc.title = body.title.strip()
        changed["title"] = inc.title
    if body.description is not None:
        inc.description = body.description.strip() or None
        changed["description"] = True
    if body.component is not None:
        inc.component = body.component.strip() or None
        changed["component"] = inc.component
    if body.severity is not None:
        _validate_severity(body.severity)
        inc.severity = body.severity
        changed["severity"] = inc.severity
    if body.postmortem is not None:
        inc.postmortem = body.postmortem.strip() or None
        changed["postmortem"] = True

    status_changed = False
    if body.status is not None and body.status != inc.status:
        _validate_status(body.status)
        prev = inc.status
        inc.status = body.status
        status_changed = True
        changed["status"] = {"from": prev, "to": body.status}
        # Stamp/clear resolution time as the incident opens or closes.
        if body.status == "resolved":
            inc.resolved_at = inc.resolved_at or _utcnow()
        else:
            inc.resolved_at = None

    if not changed:
        raise HTTPException(422, detail="No fields to update")

    # Record a timeline entry when the status changes or a note is supplied.
    if status_changed or (body.note and body.note.strip()):
        note = (body.note or "").strip()
        if not note:
            note = f"Status → {inc.status}."
        _add_update(inc, token.user_id, note, inc.status if status_changed else None)

    await db.flush()
    await audit_log(db, "incident_updated", token.user_id, get_ip(request), {
        "incident_id": str(inc.id),
        "changes": changed,
    })
    await db.commit()
    inc = await _get_with_updates(db, incident_id)
    return _serialize(inc, with_updates=True)


@router.post("/{incident_id}/updates")
@limiter.limit("60/minute")
async def add_incident_update(
    incident_id: uuid.UUID,
    body: IncidentUpdateCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    inc = await _get_with_updates(db, incident_id)
    if inc is None:
        raise HTTPException(404, detail="Incident not found")

    new_status = None
    if body.status is not None and body.status != inc.status:
        _validate_status(body.status)
        new_status = body.status
        inc.status = body.status
        if body.status == "resolved":
            inc.resolved_at = inc.resolved_at or _utcnow()
        else:
            inc.resolved_at = None

    _add_update(inc, token.user_id, body.note.strip(), new_status)
    await db.flush()
    await audit_log(db, "incident_update_added", token.user_id, get_ip(request), {
        "incident_id": str(inc.id),
        "status": new_status,
    })
    await db.commit()
    inc = await _get_with_updates(db, incident_id)
    return _serialize(inc, with_updates=True)
