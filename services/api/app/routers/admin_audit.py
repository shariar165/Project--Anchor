"""
Super-Admin audit-log explorer.

The platform writes an append-only, SHA-256 hash-chained `audit_logs` row on
every sensitive action (see services/audit.py::log_event). This router is the
read side: list/filter/verify/export. Super-Admin only — the audit trail is
platform-wide and must not be tenant-scoped to a single university admin.
"""
import csv
import io
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.limiter import limiter
from app.models.audit import AuditLog
from app.models.user import User, Role
from app.services.audit import mask_email, verify_chain

router = APIRouter(prefix="/v1/admin", tags=["admin-audit"])

MAX_LIMIT = 200
MAX_VERIFY = 5000


def _parse_dt(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        # Accept trailing 'Z' as UTC
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid {field}: expected ISO 8601")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _build_filters(
    *,
    event_type: str | None,
    prefix: str | None,
    user_id: str | None,
    role: str | None,
    tenant_id: str | None,
    q: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
):
    """Return a list of SQLAlchemy filter clauses; raises 400 on malformed input."""
    clauses = []
    if event_type:
        clauses.append(AuditLog.event_type == event_type)
    if prefix:
        clauses.append(AuditLog.event_type.like(f"{prefix}%"))
    if user_id:
        try:
            clauses.append(AuditLog.user_id == uuid.UUID(user_id))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid user_id")
    if role:
        try:
            role_enum = Role(role)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {role}")
        clauses.append(User.role == role_enum)
    if tenant_id:
        try:
            clauses.append(User.tenant_id == uuid.UUID(tenant_id))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid tenant_id")
    if q:
        like = f"%{q}%"
        clauses.append(or_(
            AuditLog.event_type.ilike(like),
            cast(AuditLog.metadata_, String).ilike(like),
        ))
    if date_from:
        clauses.append(AuditLog.created_at >= date_from)
    if date_to:
        clauses.append(AuditLog.created_at <= date_to)
    return clauses


async def _query_rows(db: AsyncSession, clauses, limit: int, offset: int):
    """Run the filtered, paginated audit query joined to the actor user."""
    base = select(AuditLog, User).outerjoin(User, AuditLog.user_id == User.id)
    for c in clauses:
        base = base.where(c)

    count_q = select(func.count()).select_from(base.subquery())
    total = await db.scalar(count_q) or 0

    page_q = base.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).offset(offset)
    rows = (await db.execute(page_q)).all()
    return rows, total


def _serialize(audit: AuditLog, user: User | None) -> dict:
    return {
        "id": str(audit.id),
        "created_at": audit.created_at.isoformat(),
        "event_type": audit.event_type,
        "actor": {
            "user_id": str(audit.user_id) if audit.user_id else None,
            "masked_email": mask_email(user.email if user else None),
            "role": (user.role.value if user else None),
            "tenant_id": (str(user.tenant_id) if user and user.tenant_id else None),
        },
        "ip_address": audit.ip_address,
        "metadata": audit.metadata_ or {},
        "row_hash": audit.row_hash.hex(),
    }


@router.get("/audit")
@limiter.limit("60/minute")
async def list_audit(
    request: Request,
    event_type: str | None = Query(default=None),
    prefix: str | None = Query(default=None, description="event_type prefix, e.g. 'alert_'"),
    user_id: str | None = Query(default=None),
    role: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    q: str | None = Query(default=None, description="substring over event_type + metadata"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Filtered, paginated audit-log read. Super-Admin only."""
    clauses = _build_filters(
        event_type=event_type, prefix=prefix, user_id=user_id, role=role,
        tenant_id=tenant_id, q=q,
        date_from=_parse_dt(date_from, "date_from"),
        date_to=_parse_dt(date_to, "date_to"),
    )
    rows, total = await _query_rows(db, clauses, limit, offset)
    items = [_serialize(a, u) for a, u in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/audit/verify")
@limiter.limit("20/minute")
async def verify_audit(
    request: Request,
    limit: int = Query(default=1000, ge=1, le=MAX_VERIFY),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Recompute the SHA-256 hash chain over the most recent `limit` rows."""
    return await verify_chain(db, limit=limit)


@router.get("/audit/export")
@limiter.limit("10/minute")
async def export_audit(
    request: Request,
    event_type: str | None = Query(default=None),
    prefix: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    role: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=50000),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Export the filtered audit log as a watermarked CSV. Super-Admin only."""
    clauses = _build_filters(
        event_type=event_type, prefix=prefix, user_id=user_id, role=role,
        tenant_id=tenant_id, q=q,
        date_from=_parse_dt(date_from, "date_from"),
        date_to=_parse_dt(date_to, "date_to"),
    )
    rows, _ = await _query_rows(db, clauses, limit, offset=0)

    buf = io.StringIO()
    now = datetime.now(tz=timezone.utc).isoformat()
    buf.write(f"# Anchor AI audit export — exported_by={token.user_id} at {now}\n")
    writer = csv.writer(buf)
    writer.writerow(["timestamp", "event_type", "actor_user_id", "actor_role", "ip_address", "row_hash", "metadata"])
    for audit, user in rows:
        writer.writerow([
            audit.created_at.isoformat(),
            audit.event_type,
            str(audit.user_id) if audit.user_id else "",
            (user.role.value if user else ""),
            audit.ip_address or "",
            audit.row_hash.hex(),
            json.dumps(audit.metadata_ or {}, sort_keys=True),
        ])

    filename = f"anchor-audit-{datetime.now(tz=timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
