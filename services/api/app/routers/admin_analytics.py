"""University-admin analytics (read-only, tenant-scoped aggregates).

Route: GET /v1/admin/analytics
Auth: admin / moderator role (super_admin bypasses the gate via require_role).

Campus-ops focused aggregates for a single university — filings/complaints,
applications, alerts, users, and a 14-day activity time-series for the charts.
Everything is scoped to the caller's ``token.tenant_id`` (mirrors
``filings.py``); super_admin without a tenant sees platform-wide totals.
Anonymized — counts only, no individual records.

Mirrors the structure of ``super_analytics.py`` but tenant-scoped.
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.limiter import limiter
from app.models.user import User
from app.models.alert import AlertEvent, AlertState
from app.models.feed import VerificationFeedPost
from app.models.filing import Filing, FilingState
from app.models.application import Application, ApplicationState
from app.models.notice import Notice

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin/analytics", tags=["admin-analytics"])

# Filing states considered "open" — matches routers/filings.py _OPEN_STATES.
_FILING_OPEN_STATES = (
    FilingState.draft.value,
    FilingState.moderation_queue.value,
    FilingState.routed.value,
    FilingState.subject_notified.value,
    FilingState.subject_responded.value,
    FilingState.under_review.value,
)


def _rate(part: int, whole: int) -> float:
    """Percentage of ``part`` over ``whole``, rounded to 1 dp; 0.0 when empty."""
    return round(part / whole * 100, 1) if whole else 0.0


@router.get("")
@limiter.limit("60/minute")
async def university_analytics(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    now = datetime.now(tz=timezone.utc)
    last_24h = now - timedelta(hours=24)
    last_30d = now - timedelta(days=30)
    tenant_id = token.tenant_id

    def _scoped(stmt, model):
        """Append a tenant filter when the caller is tenant-bound."""
        if tenant_id:
            return stmt.where(model.tenant_id == tenant_id)
        return stmt

    async def _count(stmt, model) -> int:
        return (await db.execute(_scoped(stmt, model))).scalar() or 0

    async def _grouped(model, column) -> dict[str, int]:
        rows = (await db.execute(
            _scoped(select(column, func.count()).select_from(model), model).group_by(column)
        )).all()
        out: dict[str, int] = {}
        for key, n in rows:
            if key is None:
                continue
            out[getattr(key, "value", key)] = n
        return out

    async def _series(model, days: int = 14) -> list[dict]:
        """Daily counts for the last `days` days, oldest→newest, zero-filled."""
        start = (now - timedelta(days=days - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day = func.date(model.created_at)
        rows = (await db.execute(
            _scoped(
                select(day, func.count()).select_from(model).where(model.created_at >= start),
                model,
            ).group_by(day)
        )).all()
        counts = {str(d): n for d, n in rows}
        return [
            {"date": (di := (start + timedelta(days=i)).date().isoformat()),
             "count": counts.get(di, 0)}
            for i in range(days)
        ]

    # ── Filings / complaints ──────────────────────────────────────────────
    fbase = select(func.count()).select_from(Filing)
    f_total = await _count(fbase, Filing)
    f_open = await _count(fbase.where(Filing.state.in_(_FILING_OPEN_STATES)), Filing)
    f_under_review = await _count(fbase.where(Filing.state == FilingState.under_review.value), Filing)
    f_resolved = await _count(fbase.where(Filing.state == FilingState.resolved.value), Filing)
    f_escalated = await _count(
        fbase.where(Filing.escalation_level > 0, Filing.finalized_at.is_(None)), Filing
    )

    # Average resolution time (submit → finalise) over resolved filings — computed
    # in Python to stay portable across SQLite (tests) and PostgreSQL (prod).
    resolved_rows = (await db.execute(_scoped(
        select(Filing.submitted_at, Filing.finalized_at).where(
            Filing.state == FilingState.resolved.value,
            Filing.submitted_at.is_not(None),
            Filing.finalized_at.is_not(None),
        ),
        Filing,
    ))).all()
    durations = [
        (fin - sub).total_seconds()
        for sub, fin in resolved_rows
        if fin and sub and fin >= sub
    ]
    avg_resolution_secs = round(sum(durations) / len(durations), 1) if durations else None

    # ── Applications ──────────────────────────────────────────────────────
    abase = select(func.count()).select_from(Application)
    a_total = await _count(abase, Application)
    a_approved = await _count(abase.where(Application.state == ApplicationState.approved.value), Application)
    a_rejected = await _count(abase.where(Application.state == ApplicationState.rejected.value), Application)
    a_in_review = await _count(abase.where(Application.state == ApplicationState.in_review.value), Application)

    stage_rows = (await db.execute(_scoped(
        select(Application.current_approver_level, func.count())
        .select_from(Application)
        .where(Application.state == ApplicationState.in_review.value),
        Application,
    ).group_by(Application.current_approver_level))).all()
    by_stage_raw = {lvl: cnt for lvl, cnt in stage_rows if lvl}
    by_stage = {
        "mentor": by_stage_raw.get("mentor", 0),
        "department_head": by_stage_raw.get("department_head", 0),
        "dean": by_stage_raw.get("dean", 0),
        "accounts": by_stage_raw.get("accounts", 0),
    }
    a_decided = a_approved + a_rejected

    # ── Alerts ────────────────────────────────────────────────────────────
    al_total = await _count(select(func.count()).select_from(AlertEvent), AlertEvent)
    al_active = await _count(
        select(func.count()).select_from(AlertEvent).where(AlertEvent.state == AlertState.active),
        AlertEvent,
    )
    al_resolved_24h = await _count(
        select(func.count()).select_from(AlertEvent).where(
            AlertEvent.state.in_([AlertState.resolved, AlertState.closed, AlertState.user_safe]),
            AlertEvent.created_at >= last_24h,
        ),
        AlertEvent,
    )
    al_false_30d = await _count(
        select(func.count()).select_from(AlertEvent).where(
            AlertEvent.state == AlertState.false_alert, AlertEvent.created_at >= last_30d,
        ),
        AlertEvent,
    )

    # ── Users & content ───────────────────────────────────────────────────
    users_total = await _count(select(func.count()).select_from(User), User)
    users_by_role = await _grouped(User, User.role)
    notices_total = await _count(select(func.count()).select_from(Notice), Notice)
    feed_total = await _count(select(func.count()).select_from(VerificationFeedPost), VerificationFeedPost)

    return {
        "filings": {
            "total": f_total,
            "open": f_open,
            "under_review": f_under_review,
            "resolved": f_resolved,
            "escalated": f_escalated,
            "resolution_rate": _rate(f_resolved, f_total),
            "escalation_rate": _rate(f_escalated, f_total),
            "avg_resolution_secs": avg_resolution_secs,
            "by_category": await _grouped(Filing, Filing.category),
            "by_state": await _grouped(Filing, Filing.state),
            "by_priority": await _grouped(Filing, Filing.priority),
        },
        "applications": {
            "total": a_total,
            "approved": a_approved,
            "rejected": a_rejected,
            "in_review": a_in_review,
            "decided": a_decided,
            "approval_rate": _rate(a_approved, a_decided),
            "by_stage": by_stage,
        },
        "alerts": {
            "total": al_total,
            "active": al_active,
            "resolved_24h": al_resolved_24h,
            "false_alarm_30d": al_false_30d,
        },
        "users": {
            "total": users_total,
            "by_role": users_by_role,
        },
        "content": {
            "notices": notices_total,
            "feed_posts": feed_total,
        },
        "series": {
            "filings_14d": await _series(Filing),
            "applications_14d": await _series(Application),
            "alerts_14d": await _series(AlertEvent),
        },
        "generated_at": now.isoformat(),
    }
