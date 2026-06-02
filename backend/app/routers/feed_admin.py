"""Verification Feed — admin-facing moderation endpoints.

Route order: ALL static paths before /{post_id} parameterized paths.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_role, require_stepup, TokenData
from app.redis import get_redis
from app.schemas.feed import (
    AdminActionRequest, PromoteToZoneRequest,
    AdminQueueItem, AdminPostReview, SignalCountsResponse,
    AttachmentInfo, TrustBadgeResponse,
)
from app.services import feed_svc, feed_moderation_svc
from app.services.audit import log_event as audit_log
from app.services.device import get_ip
from app.models.feed import ModerationAction, PostScope, PostState, SignalType

router = APIRouter(prefix="/v1/feed/admin", tags=["feed-admin"])

_mod_or_admin = require_role("admin", "moderator")
_admin_only = require_role("admin")


def _tenant_guard(post, token: TokenData) -> None:
    """Raise 404 if moderator tries to access another tenant's campus post."""
    if token.role == "moderator" and token.tenant_id:
        if post.scope == PostScope.campus and post.tenant_id != token.tenant_id:
            raise HTTPException(404, "Post not found")


async def _load_post_or_404(db: AsyncSession, post_id: uuid.UUID, token: TokenData):
    post = await feed_svc.get_post(db, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    _tenant_guard(post, token)
    return post


def _queue_item(post, counts, publisher_trust_tier="none") -> AdminQueueItem:
    sc = SignalCountsResponse(
        corroborate=counts["corroborate"],
        challenge=counts["challenge"],
        flags=counts["flags"],
    )
    return AdminQueueItem(
        id=post.id,
        post_number=post.post_number,
        scope=post.scope.value,
        category=post.category.value,
        title=post.title,
        state=post.state.value,
        admin_confirmed=post.admin_confirmed,
        created_at=post.created_at,
        tenant_id=post.tenant_id,
        signal_counts=sc,
        flag_count=counts["flags"],
        publisher_trust_tier=publisher_trust_tier,
    )


# ─── Static paths ─────────────────────────────────────────────────────────────

@router.get("/queue", response_model=list[AdminQueueItem])
async def get_queue(
    tab: str = "flagged",
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(_mod_or_admin),
):
    if tab not in ("flagged", "pre_publish", "confirmation"):
        raise HTTPException(400, "tab must be one of: flagged, pre_publish, confirmation")

    mod_tenant = token.tenant_id if token.role == "moderator" else None
    posts = await feed_moderation_svc.get_admin_queue(
        db, tab, moderator_tenant_id=mod_tenant, page=page, page_size=page_size
    )

    items = []
    for post in posts:
        counts = await feed_svc.get_signal_counts(db, post.id)
        trust = await feed_svc.get_or_create_trust(db, post.publisher_user_id)
        items.append(_queue_item(post, counts, trust.trust_tier.value))
    await db.commit()
    return items


@router.get("/patterns/signal-rings")
async def pattern_signal_rings(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(_mod_or_admin),
):
    return await feed_moderation_svc.get_signal_ring_patterns(db)


@router.get("/patterns/repeat-fake-publishers")
async def pattern_repeat_fake(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(_mod_or_admin),
):
    return await feed_moderation_svc.get_repeat_fake_publishers(db)


@router.get("/patterns/trust-source-anomalies")
async def pattern_trust_anomalies(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(_mod_or_admin),
):
    return await feed_moderation_svc.get_trust_source_anomalies(db)


@router.get("/patterns/category-misuse")
async def pattern_category_misuse(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(_mod_or_admin),
):
    return await feed_moderation_svc.get_category_misuse(db)


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(_mod_or_admin),
):
    mod_tenant = token.tenant_id if token.role == "moderator" else None
    return await feed_moderation_svc.get_stats(db, tenant_id=mod_tenant)


# ─── Parameterized paths ──────────────────────────────────────────────────────

@router.get("/{post_id}", response_model=AdminPostReview)
async def get_post_review(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(_mod_or_admin),
):
    data = await feed_moderation_svc.get_post_review_data(db, post_id)
    if not data:
        raise HTTPException(404, "Post not found")
    post = data["post"]
    _tenant_guard(post, token)

    counts = await feed_svc.get_signal_counts(db, post.id)
    sc = SignalCountsResponse(
        corroborate=counts["corroborate"],
        challenge=counts["challenge"],
        flags=counts["flags"],
    )

    publisher_trust = data.get("publisher_trust")
    trust_resp = (
        TrustBadgeResponse(
            user_id=publisher_trust.user_id,
            trust_tier=publisher_trust.trust_tier.value,
            confirmed_accurate_count=publisher_trust.confirmed_accurate_count,
            confirmed_fake_count=publisher_trust.confirmed_fake_count,
        )
        if publisher_trust else None
    )

    return AdminPostReview(
        id=post.id,
        post_number=post.post_number,
        publisher_user_id=post.publisher_user_id,
        scope=post.scope.value,
        category=post.category.value,
        title=post.title,
        body=post.body,
        tags=post.tags or [],
        geo_lat=post.geo_lat,
        geo_lng=post.geo_lng,
        geo_address=post.geo_address,
        state=post.state.value,
        admin_confirmed=post.admin_confirmed,
        admin_confirmed_at=post.admin_confirmed_at,
        zone_id=post.zone_id,
        expires_at=post.expires_at,
        created_at=post.created_at,
        updated_at=post.updated_at,
        tenant_id=post.tenant_id,
        signal_counts=sc,
        attachments=[
            AttachmentInfo(
                id=a.id,
                file_hash_sha256=a.file_hash_sha256,
                content_type=a.content_type,
                file_size_bytes=a.file_size_bytes,
                uploaded_at=a.uploaded_at,
            )
            for a in (post.attachments or [])
        ],
        flags=[
            {"flag_reason": f.flag_reason.value, "note": f.note, "created_at": str(f.created_at)}
            for f in data.get("flags", [])
        ],
        moderation_history=[
            {
                "action": m.action.value,
                "internal_note": m.internal_note,
                "public_note": m.public_note,
                "created_at": str(m.created_at),
                "moderator_user_id": str(m.moderator_user_id) if m.moderator_user_id else None,
            }
            for m in data.get("moderation_history", [])
        ],
        publisher_trust=trust_resp,
    )


@router.post("/{post_id}/confirm")
async def confirm_post(
    post_id: uuid.UUID,
    body: AdminActionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_stepup),
    _role: TokenData = Depends(_mod_or_admin),
):
    post = await _load_post_or_404(db, post_id, token)

    if post.publisher_user_id == token.user_id:
        raise HTTPException(400, "Cannot confirm your own post")

    await feed_moderation_svc.record_moderation(
        db, post, token.user_id, ModerationAction.confirm,
        internal_note=body.internal_note,
    )
    await audit_log(db, "feed_confirm", token.user_id, get_ip(request), {"post_id": str(post_id)})
    await db.commit()
    return {"message": "Post confirmed as accurate"}


@router.post("/{post_id}/mark-fake")
async def mark_fake(
    post_id: uuid.UUID,
    body: AdminActionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_stepup),
    _role: TokenData = Depends(_mod_or_admin),
):
    if not body.public_note or len(body.public_note) < 30:
        raise HTTPException(400, "public_note must be at least 30 characters")

    post = await _load_post_or_404(db, post_id, token)
    await feed_moderation_svc.record_moderation(
        db, post, token.user_id, ModerationAction.mark_fake,
        internal_note=body.internal_note,
        public_note=body.public_note,
    )
    await audit_log(db, "feed_mark_fake", token.user_id, get_ip(request), {"post_id": str(post_id)})
    await db.commit()
    return {"message": "Post marked as fake and removed from feed"}


@router.post("/{post_id}/take-down")
async def take_down(
    post_id: uuid.UUID,
    body: AdminActionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_stepup),
    _role: TokenData = Depends(_mod_or_admin),
):
    if not body.public_note or len(body.public_note) < 30:
        raise HTTPException(400, "public_note must be at least 30 characters")

    post = await _load_post_or_404(db, post_id, token)
    await feed_moderation_svc.record_moderation(
        db, post, token.user_id, ModerationAction.take_down,
        internal_note=body.internal_note,
        public_note=body.public_note,
    )
    await audit_log(db, "feed_take_down", token.user_id, get_ip(request), {"post_id": str(post_id)})
    await db.commit()
    return {"message": "Post taken down"}


@router.post("/{post_id}/no-action")
async def no_action(
    post_id: uuid.UUID,
    body: AdminActionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(_mod_or_admin),
):
    post = await _load_post_or_404(db, post_id, token)
    # Return to live if it was under_review
    if post.state == PostState.under_review:
        post.state = PostState.live
    await feed_moderation_svc.record_moderation(
        db, post, token.user_id, ModerationAction.no_action,
        internal_note=body.internal_note,
    )
    await audit_log(db, "feed_no_action", token.user_id, get_ip(request), {"post_id": str(post_id)})
    await db.commit()
    return {"message": "Post cleared — no action taken"}


@router.post("/{post_id}/defer")
async def defer_post(
    post_id: uuid.UUID,
    body: AdminActionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(_mod_or_admin),
):
    post = await _load_post_or_404(db, post_id, token)
    await feed_moderation_svc.record_moderation(
        db, post, token.user_id, ModerationAction.defer,
        internal_note=body.internal_note,
    )
    await audit_log(db, "feed_defer", token.user_id, get_ip(request), {"post_id": str(post_id)})
    await db.commit()
    return {"message": "Post deferred for 24 hours"}


@router.post("/{post_id}/restore")
async def restore_post(
    post_id: uuid.UUID,
    body: AdminActionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_stepup),
    _role: TokenData = Depends(_admin_only),
):
    post = await _load_post_or_404(db, post_id, token)
    await feed_moderation_svc.record_moderation(
        db, post, token.user_id, ModerationAction.restore,
        internal_note=body.internal_note,
    )
    await audit_log(db, "feed_restore", token.user_id, get_ip(request), {"post_id": str(post_id)})
    await db.commit()
    return {"message": "Post restored to live feed"}


@router.post("/{post_id}/promote-to-zone")
async def promote_to_zone(
    post_id: uuid.UUID,
    body: PromoteToZoneRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_stepup),
    _role: TokenData = Depends(_admin_only),
):
    post = await _load_post_or_404(db, post_id, token)

    from app.models.feed import PostCategory
    if post.category not in (PostCategory.incident, PostCategory.safety):
        raise HTTPException(400, "Only Incident and Safety posts can be promoted to a zone")

    await feed_moderation_svc.record_moderation(
        db, post, token.user_id, ModerationAction.promote_to_zone,
        internal_note=body.internal_note,
        zone_id=body.zone_id,
    )
    await audit_log(
        db, "feed_promote_to_zone", token.user_id, get_ip(request),
        {"post_id": str(post_id), "zone_id": str(body.zone_id)},
    )
    await db.commit()
    return {"message": "Post promoted to Red Zone Map", "zone_id": str(body.zone_id)}
