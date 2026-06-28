"""Admin notification bell — a read-only, derived live-ops aggregate.

No dedicated table: each item is recomputed per request from existing data, scoped to
the caller's tenant where the underlying model carries one. Every count is best-effort
(wrapped) so one failing source never blanks the bell.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.models.alert import AlertEvent, AlertState
from app.models.lawyer import Lawyer
from app.models.feed import VerificationFeedPost, PostState
from app.models.deanonymization import DeanonymizationRequest
from app.models.application import Application, ApplicationState
from app.models.filing import Filing, FilingState
from app.services import notification_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin/notifications", tags=["admin-notifications"])

_OPEN_FILING_STATES = (
    FilingState.moderation_queue.value,
    FilingState.routed.value,
    FilingState.subject_notified.value,
    FilingState.subject_responded.value,
    FilingState.under_review.value,
)
_OPEN_DEANON = ("pending_review", "awaiting_second_approval")


async def _count(db: AsyncSession, query) -> int:
    try:
        return int(await db.scalar(query) or 0)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[admin-notif] count failed: %s", exc)
        return 0


@router.get("")
async def admin_notifications(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    is_super = token.role == "super_admin"
    tenant_id = token.tenant_id
    scoped = (not is_super) and tenant_id is not None
    items: list[dict] = []

    # Active emergency alerts
    alert_q = select(func.count(AlertEvent.id)).where(AlertEvent.state == AlertState.active)
    if scoped:
        alert_q = alert_q.where(AlertEvent.tenant_id == tenant_id)
    n_alerts = await _count(db, alert_q)
    if n_alerts:
        items.append({
            "type": "alert",
            "title": "Active emergency alert" + ("s" if n_alerts != 1 else ""),
            "count": n_alerts,
            "route": "/super/alerts" if is_super else "/university/alerts",
        })

    # Verification-feed posts awaiting moderation
    feed_q = select(func.count(VerificationFeedPost.id)).where(
        VerificationFeedPost.state == PostState.under_review
    )
    if scoped:
        feed_q = feed_q.where(VerificationFeedPost.tenant_id == tenant_id)
    n_feed = await _count(db, feed_q)
    if n_feed:
        items.append({
            "type": "feed",
            "title": "Feed post" + ("s" if n_feed != 1 else "") + " awaiting review",
            "count": n_feed,
            "route": "/super/moderation" if is_super else "/university/verification-feed",
        })

    if is_super:
        # Pending lawyer verification applications (super-admin only)
        n_lawyers = await _count(
            db, select(func.count(Lawyer.id)).where(Lawyer.status == "pending")
        )
        if n_lawyers:
            items.append({
                "type": "lawyer",
                "title": "Lawyer application" + ("s" if n_lawyers != 1 else "") + " pending",
                "count": n_lawyers,
                "route": "/super/verify-lawyers",
            })

        # Pending de-anonymization requests
        n_deanon = await _count(
            db, select(func.count(DeanonymizationRequest.id)).where(
                DeanonymizationRequest.status.in_(_OPEN_DEANON)
            )
        )
        if n_deanon:
            items.append({
                "type": "deanon",
                "title": "De-anonymization request" + ("s" if n_deanon != 1 else "") + " pending",
                "count": n_deanon,
                "route": "/super/deanonymization",
            })
    else:
        # University admin queue: applications awaiting review
        app_q = select(func.count(Application.id)).where(
            Application.state == ApplicationState.in_review
        )
        if scoped:
            app_q = app_q.where(Application.tenant_id == tenant_id)
        n_apps = await _count(db, app_q)
        if n_apps:
            items.append({
                "type": "case",
                "title": "Application" + ("s" if n_apps != 1 else "") + " awaiting review",
                "count": n_apps,
                "route": "/university/applications",
            })

        # Open complaints / grievances
        filing_q = select(func.count(Filing.id)).where(Filing.state.in_(_OPEN_FILING_STATES))
        if scoped:
            filing_q = filing_q.where(Filing.tenant_id == tenant_id)
        n_filings = await _count(db, filing_q)
        if n_filings:
            items.append({
                "type": "case",
                "title": "Open complaint" + ("s" if n_filings != 1 else ""),
                "count": n_filings,
                "route": "/university/complaints",
            })

    unread = sum(i["count"] for i in items)
    return {"items": items, "unread_count": unread}


# ── Admin channel preferences (settings panel) ────────────────────────────────
# push/email/sms toggles + quiet hours, persisted as a free-form JSON blob.
# Stored-but-inert where no delivery channel exists yet (there is no email/SMS sender).

@router.get("/preferences")
async def get_admin_prefs(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return {"channels": await notification_svc.get_channels(db, token.user_id)}


@router.patch("/preferences")
async def update_admin_prefs(
    body: dict,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    channels = body.get("channels", body) if isinstance(body, dict) else {}
    if not isinstance(channels, dict):
        channels = {}
    saved = await notification_svc.set_channels(db, token.user_id, channels)
    return {"channels": saved}
