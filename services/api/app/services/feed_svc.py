"""Verification Feed core business logic.

All public async functions use await db.flush() (not commit) — callers commit.
Background tasks (activate_post) open their own AsyncSessionLocal().
"""
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, delete, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.feed import (
    VerificationFeedPost, VerificationFeedPostVersion,
    VerificationFeedSignal, VerificationFeedFlag, UserFeedTrust,
    PostState, PostScope, PostCategory, AIPrescreenVerdict,
    SignalType, TrustTier,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ─── Trust weights ────────────────────────────────────────────────────────────

def get_trust_weight(trust_tier: TrustTier) -> float:
    settings = get_settings()
    return {
        TrustTier.bronze: settings.trusted_source_bronze_weight,
        TrustTier.silver: settings.trusted_source_silver_weight,
        TrustTier.gold:   settings.trusted_source_gold_weight,
    }.get(trust_tier, 1.0)


def _tier_from_count(count: int) -> TrustTier:
    s = get_settings()
    if count >= s.trust_milestone_gold:
        return TrustTier.gold
    if count >= s.trust_milestone_silver:
        return TrustTier.silver
    if count >= s.trust_milestone_bronze:
        return TrustTier.bronze
    return TrustTier.none


def _compute_expires_at(category: PostCategory) -> datetime | None:
    s = get_settings()
    hours_map = {
        PostCategory.incident:       s.archive_incident_hours,
        PostCategory.road:           s.archive_road_hours,
        PostCategory.safety:         s.archive_safety_hours,
        PostCategory.civic_event:    s.archive_civic_event_hours,
        PostCategory.missing_person: s.archive_missing_person_hours,
    }
    hours = hours_map.get(category)
    return _now() + timedelta(hours=hours) if hours else None


# ─── Post number ─────────────────────────────────────────────────────────────

async def generate_post_number(db: AsyncSession) -> str:
    result = await db.execute(select(func.count()).select_from(VerificationFeedPost))
    count = result.scalar() or 0
    now = _now()
    return f"VFP-{now.year}-{now.month:02d}-{count + 1:05d}"


# ─── Trust table ─────────────────────────────────────────────────────────────

async def get_or_create_trust(db: AsyncSession, user_id: uuid.UUID) -> UserFeedTrust:
    result = await db.execute(select(UserFeedTrust).where(UserFeedTrust.user_id == user_id))
    trust = result.scalars().first()
    if not trust:
        trust = UserFeedTrust(user_id=user_id)
        db.add(trust)
        await db.flush()
    return trust


async def recalculate_trust(db: AsyncSession, user_id: uuid.UUID) -> UserFeedTrust:
    from app.models.feed import VerificationFeedModeration, ModerationAction

    # Count confirmed-accurate posts: live, admin_confirmed, publisher=user
    acc_result = await db.execute(
        select(func.count()).select_from(VerificationFeedPost).where(
            VerificationFeedPost.publisher_user_id == user_id,
            VerificationFeedPost.admin_confirmed == True,  # noqa: E712
            VerificationFeedPost.state == PostState.live,
        )
    )
    accurate_count = acc_result.scalar() or 0

    # Count fake strikes: mark_fake moderation actions against this user's posts
    fake_result = await db.execute(
        select(func.count()).select_from(VerificationFeedModeration).join(
            VerificationFeedPost,
            VerificationFeedModeration.post_id == VerificationFeedPost.id,
        ).where(
            VerificationFeedPost.publisher_user_id == user_id,
            VerificationFeedModeration.action == ModerationAction.mark_fake,
        )
    )
    fake_count = fake_result.scalar() or 0

    tier = _tier_from_count(accurate_count)

    trust = await get_or_create_trust(db, user_id)
    trust.confirmed_accurate_count = accurate_count
    trust.confirmed_fake_count = fake_count
    trust.trust_tier = tier
    trust.last_recalculated_at = _now()
    await db.flush()
    return trust


# ─── CRUD ────────────────────────────────────────────────────────────────────

async def create_post(
    db: AsyncSession,
    *,
    publisher_user_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
    scope: str,
    category: str,
    title: str,
    body: str,
    tags: list[str] | None,
    geo_lat: float | None,
    geo_lng: float | None,
    geo_address: str | None,
    prescreen: dict,
) -> VerificationFeedPost:
    post_number = await generate_post_number(db)
    verdict_str = prescreen.get("verdict", "manual_review")
    # Map string to enum
    verdict_map = {"pass": AIPrescreenVerdict.pass_, "block": AIPrescreenVerdict.block}
    verdict = verdict_map.get(verdict_str, AIPrescreenVerdict.manual_review)

    post = VerificationFeedPost(
        post_number=post_number,
        publisher_user_id=publisher_user_id,
        tenant_id=tenant_id,
        scope=PostScope(scope),
        category=PostCategory(category),
        title=title,
        body=body,
        tags=tags or [],
        geo_lat=geo_lat,
        geo_lng=geo_lng,
        geo_address=geo_address,
        state=PostState.pending_ai,
        ai_prescreen_verdict=verdict,
        ai_prescreen_data=prescreen,
    )
    db.add(post)
    await db.flush()
    return post


async def activate_post(post_id: uuid.UUID) -> None:
    """Background task — opens its own session."""
    from app.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(VerificationFeedPost).where(VerificationFeedPost.id == post_id)
            )
            post = result.scalars().first()
            if post and post.state == PostState.pending_ai:
                post.state = PostState.live
                post.expires_at = _compute_expires_at(post.category)
                await db.commit()
    except Exception as exc:
        logger.exception("[FEED] activate_post failed for %s: %s", post_id, exc)


async def get_post(
    db: AsyncSession,
    post_id: uuid.UUID,
    requesting_tenant_id: uuid.UUID | None = None,
) -> VerificationFeedPost | None:
    result = await db.execute(
        select(VerificationFeedPost)
        .options(selectinload(VerificationFeedPost.attachments))
        .where(VerificationFeedPost.id == post_id)
    )
    post = result.scalars().first()
    if not post:
        return None
    # Cross-tenant campus leak prevention
    if (
        post.scope == PostScope.campus
        and requesting_tenant_id is not None
        and post.tenant_id != requesting_tenant_id
    ):
        return None
    return post


async def list_posts(
    db: AsyncSession,
    *,
    scope: str,
    category: str | None = None,
    sort: str = "recent",
    page: int = 1,
    page_size: int = 20,
    tenant_id: uuid.UUID | None = None,
    confirmed_only: bool = False,
) -> list[VerificationFeedPost]:
    q = (
        select(VerificationFeedPost)
        .options(selectinload(VerificationFeedPost.attachments))
        .where(VerificationFeedPost.state == PostState.live)
    )

    q = q.where(VerificationFeedPost.scope == PostScope(scope))
    if scope == "campus" and tenant_id:
        q = q.where(VerificationFeedPost.tenant_id == tenant_id)

    # Verified-only editions: normal readers only see admin-confirmed stories.
    if confirmed_only:
        q = q.where(VerificationFeedPost.admin_confirmed == True)  # noqa: E712

    if category:
        q = q.where(VerificationFeedPost.category == PostCategory(category))

    if sort == "corroborate":
        corr_sub = (
            select(func.count())
            .select_from(VerificationFeedSignal)
            .where(
                VerificationFeedSignal.post_id == VerificationFeedPost.id,
                VerificationFeedSignal.signal_type == SignalType.corroborate,
            )
            .correlate(VerificationFeedPost)
            .scalar_subquery()
        )
        q = q.order_by(corr_sub.desc(), VerificationFeedPost.created_at.desc())
    else:
        q = q.order_by(VerificationFeedPost.created_at.desc())

    offset = (page - 1) * page_size
    q = q.offset(offset).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all())


async def edit_post(
    db: AsyncSession,
    post: VerificationFeedPost,
    *,
    editor_id: uuid.UUID,
    title: str | None = None,
    body: str | None = None,
    tags: list[str] | None = None,
    geo_lat: float | None = None,
    geo_lng: float | None = None,
    geo_address: str | None = None,
) -> VerificationFeedPost:
    # Get next version number
    ver_result = await db.execute(
        select(func.max(VerificationFeedPostVersion.version)).where(
            VerificationFeedPostVersion.post_id == post.id
        )
    )
    max_ver = ver_result.scalar() or 0

    # Save snapshot of current state
    version = VerificationFeedPostVersion(
        post_id=post.id,
        version=max_ver + 1,
        title=post.title,
        body=post.body,
        tags=post.tags,
        geo_lat=post.geo_lat,
        geo_lng=post.geo_lng,
        edited_by=editor_id,
    )
    db.add(version)

    # Apply changes
    if title is not None:
        post.title = title
    if body is not None:
        post.body = body
    if tags is not None:
        post.tags = tags
    if geo_lat is not None:
        post.geo_lat = geo_lat
    if geo_lng is not None:
        post.geo_lng = geo_lng
    if geo_address is not None:
        post.geo_address = geo_address

    # Reset signals and admin confirmation
    await db.execute(
        delete(VerificationFeedSignal).where(VerificationFeedSignal.post_id == post.id)
    )
    post.admin_confirmed = False
    post.admin_confirmed_at = None
    post.admin_confirmed_by = None

    await db.flush()
    return post


async def soft_delete_post(db: AsyncSession, post: VerificationFeedPost) -> None:
    post.state = PostState.deleted_by_author
    await db.flush()


# ─── Signal counts ────────────────────────────────────────────────────────────

async def get_signal_counts(db: AsyncSession, post_id: uuid.UUID) -> dict[str, Any]:
    result = await db.execute(
        select(
            VerificationFeedSignal.signal_type,
            func.count().label("cnt"),
            func.sum(VerificationFeedSignal.weight).label("weighted"),
        )
        .where(VerificationFeedSignal.post_id == post_id)
        .group_by(VerificationFeedSignal.signal_type)
    )
    rows = result.all()

    corr_count = 0
    corr_weighted = 0.0
    chal_count = 0
    chal_weighted = 0.0
    for row in rows:
        if row.signal_type == SignalType.corroborate:
            corr_count = row.cnt
            corr_weighted = float(row.weighted or 0)
        elif row.signal_type == SignalType.challenge:
            chal_count = row.cnt
            chal_weighted = float(row.weighted or 0)

    flag_result = await db.execute(
        select(func.count()).select_from(VerificationFeedFlag).where(
            VerificationFeedFlag.post_id == post_id
        )
    )
    flag_count = flag_result.scalar() or 0

    return {
        "corroborate": corr_count,
        "challenge": chal_count,
        "weighted_corroborate": corr_weighted,
        "weighted_challenge": chal_weighted,
        "flags": flag_count,
    }


async def get_user_signal(
    db: AsyncSession, post_id: uuid.UUID, user_id: uuid.UUID
) -> str | None:
    result = await db.execute(
        select(VerificationFeedSignal).where(
            VerificationFeedSignal.post_id == post_id,
            VerificationFeedSignal.user_id == user_id,
        )
    )
    sig = result.scalars().first()
    return sig.signal_type.value if sig else None


# ─── Signals ─────────────────────────────────────────────────────────────────

async def upsert_signal(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    user_id: uuid.UUID,
    signal_type: SignalType,
    trust_tier: TrustTier,
    reason: str | None = None,
) -> dict:
    weight = get_trust_weight(trust_tier)
    result = await db.execute(
        select(VerificationFeedSignal).where(
            VerificationFeedSignal.post_id == post_id,
            VerificationFeedSignal.user_id == user_id,
        )
    )
    existing = result.scalars().first()

    if existing is None:
        sig = VerificationFeedSignal(
            post_id=post_id, user_id=user_id,
            signal_type=signal_type, reason=reason, weight=weight,
        )
        db.add(sig)
        action = "added"
    elif existing.signal_type == signal_type:
        # Same type — toggle off (remove)
        await db.delete(existing)
        action = "removed"
    else:
        # Different type — switch
        existing.signal_type = signal_type
        existing.reason = reason
        existing.weight = weight
        action = "changed"

    await db.flush()

    # Check if post should enter under_review
    post_result = await db.execute(
        select(VerificationFeedPost).where(VerificationFeedPost.id == post_id)
    )
    post = post_result.scalars().first()
    if post and post.state == PostState.live:
        await _check_auto_review_threshold(db, post)

    return {"action": action, "signal_type": signal_type.value}


async def remove_signal(db: AsyncSession, post_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await db.execute(
        delete(VerificationFeedSignal).where(
            VerificationFeedSignal.post_id == post_id,
            VerificationFeedSignal.user_id == user_id,
        )
    )
    await db.flush()


async def add_flag(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    user_id: uuid.UUID,
    flag_reason: str,
    note: str | None = None,
) -> VerificationFeedFlag:
    from app.models.feed import FlagReason
    from sqlalchemy.exc import IntegrityError

    flag = VerificationFeedFlag(
        post_id=post_id,
        user_id=user_id,
        flag_reason=FlagReason(flag_reason),
        note=note,
    )
    db.add(flag)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ValueError("already_flagged")

    # Check flag threshold
    post_result = await db.execute(
        select(VerificationFeedPost).where(VerificationFeedPost.id == post_id)
    )
    post = post_result.scalars().first()
    if post:
        await _check_flag_threshold(db, post)

    return flag


# ─── Auto-routing thresholds ─────────────────────────────────────────────────

async def _check_auto_review_threshold(db: AsyncSession, post: VerificationFeedPost) -> None:
    settings = get_settings()
    counts = await get_signal_counts(db, post.id)
    wc = counts["weighted_corroborate"]
    wh = counts["weighted_challenge"]
    total = counts["corroborate"] + counts["challenge"]

    if total >= 3 and wh > 0 and wc > 0:
        ratio = wh / (wh + wc)
        if ratio >= settings.challenge_review_ratio:
            post.state = PostState.under_review
            await db.flush()


async def _check_flag_threshold(db: AsyncSession, post: VerificationFeedPost) -> None:
    settings = get_settings()
    result = await db.execute(
        select(func.count()).select_from(VerificationFeedFlag).where(
            VerificationFeedFlag.post_id == post.id
        )
    )
    count = result.scalar() or 0
    if count >= settings.flag_to_queue_threshold and post.state == PostState.live:
        post.state = PostState.under_review
        await db.flush()
