"""Super-admin platform-wide analytics (read-only aggregates).

Route: GET /v1/super-admin/analytics
Auth: super_admin role only.

Cross-tenant aggregate counts computed directly from the DB (not the tenant-scoped
admin stats services), a 14-day activity time-series for sparklines, corpus totals
proxied from RAG, and host metrics. Anonymized — no individual records.
"""
import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.limiter import limiter
from app.models.user import User
from app.models.tenant import Tenant
from app.models.alert import AlertEvent, AlertState
from app.models.feed import VerificationFeedPost
from app.models.filing import Filing
from app.models.application import Application
from app.models.deanonymization import DeanonymizationRequest
from app.services.rag_proxy import rag_url, rag_headers
from app.services.sys_metrics import host_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/super-admin/analytics", tags=["super-admin-analytics"])

DEANON_OPEN = ("pending_review", "awaiting_second_approval")


async def _count(db: AsyncSession, stmt) -> int:
    return (await db.execute(stmt)).scalar() or 0


async def _group_counts(db: AsyncSession, column) -> dict:
    rows = (await db.execute(select(column, func.count()).group_by(column))).all()
    out = {}
    for key, n in rows:
        # Enum columns come back as the enum member; use its value.
        out[getattr(key, "value", key) if key is not None else "unknown"] = n
    return out


async def _series(db: AsyncSession, model, days: int = 14) -> list[dict]:
    """Daily counts for the last `days` days, oldest→newest, zero-filled."""
    start = (datetime.now(tz=timezone.utc) - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    day = func.date(model.created_at)
    rows = (await db.execute(
        select(day, func.count()).where(model.created_at >= start).group_by(day)
    )).all()
    counts = {str(d): n for d, n in rows}
    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).date().isoformat()
        out.append({"date": d, "count": counts.get(d, 0)})
    return out


@router.get("")
@limiter.limit("60/minute")
async def platform_analytics(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    now = datetime.now(tz=timezone.utc)
    last_24h = now - timedelta(hours=24)
    last_30d = now - timedelta(days=30)

    # Tenants
    tenants_total = await _count(db, select(func.count()).select_from(Tenant))
    tenants_pilot = await _count(db, select(func.count()).select_from(Tenant).where(Tenant.tier == "pilot"))
    tenants_suspended = await _count(db, select(func.count()).select_from(Tenant).where(Tenant.active.is_(False)))

    # Users
    users_total = await _count(db, select(func.count()).select_from(User))
    users_by_role = await _group_counts(db, User.role)
    users_by_status = await _group_counts(db, User.status)

    # Alerts
    alerts_total = await _count(db, select(func.count()).select_from(AlertEvent))
    alerts_active = await _count(db, select(func.count()).select_from(AlertEvent).where(AlertEvent.state == AlertState.active))
    alerts_resolved_24h = await _count(db, select(func.count()).select_from(AlertEvent).where(
        AlertEvent.state.in_([AlertState.resolved, AlertState.closed, AlertState.user_safe]),
        AlertEvent.created_at >= last_24h,
    ))
    alerts_false_30d = await _count(db, select(func.count()).select_from(AlertEvent).where(
        AlertEvent.state == AlertState.false_alert, AlertEvent.created_at >= last_30d,
    ))

    # Content
    feed_total = await _count(db, select(func.count()).select_from(VerificationFeedPost))
    filings_total = await _count(db, select(func.count()).select_from(Filing))
    applications_total = await _count(db, select(func.count()).select_from(Application))

    # De-anonymization queue
    deanon_total = await _count(db, select(func.count()).select_from(DeanonymizationRequest))
    deanon_open = await _count(db, select(func.count()).select_from(DeanonymizationRequest).where(
        DeanonymizationRequest.status.in_(DEANON_OPEN),
    ))

    # Time-series for sparklines
    series_alerts = await _series(db, AlertEvent)
    series_filings = await _series(db, Filing)
    series_feed = await _series(db, VerificationFeedPost)

    # Corpus totals (best-effort proxy)
    corpus_documents = None
    corpus_chunks = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{rag_url()}/corpus/stats", headers=rag_headers())
            resp.raise_for_status()
            data = resp.json()
        docs = chunks = 0
        for stats in data.values():
            if isinstance(stats, dict):
                docs += stats.get("documents") or 0
                chunks += stats.get("dense_chunks") or 0
        corpus_documents, corpus_chunks = docs, chunks
    except Exception as e:
        logger.warning("Corpus stats unavailable for analytics: %s", e)

    return {
        "tenants": {
            "total": tenants_total,
            "pilot": tenants_pilot,
            "suspended": tenants_suspended,
        },
        "users": {
            "total": users_total,
            "by_role": users_by_role,
            "by_status": users_by_status,
        },
        "alerts": {
            "total": alerts_total,
            "active": alerts_active,
            "resolved_24h": alerts_resolved_24h,
            "false_alarm_30d": alerts_false_30d,
        },
        "content": {
            "feed_posts": feed_total,
            "filings": filings_total,
            "applications": applications_total,
        },
        "deanonymization": {
            "total": deanon_total,
            "open": deanon_open,
        },
        "corpus": {
            "documents": corpus_documents,
            "dense_chunks": corpus_chunks,
        },
        "series": {
            "alerts_14d": series_alerts,
            "filings_14d": series_filings,
            "feed_14d": series_feed,
        },
        "host": host_metrics(),
        "generated_at": now.isoformat(),
    }
