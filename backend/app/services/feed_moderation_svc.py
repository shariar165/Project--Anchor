"""Verification Feed admin moderation logic."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feed import (
    VerificationFeedPost, VerificationFeedModeration, VerificationFeedSignal,
    VerificationFeedFlag, UserFeedTrust,
    PostState, ModerationAction, SignalType, TrustTier,
)
from app.config import get_settings
from app.services import feed_svc


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


async def record_moderation(
    db: AsyncSession,
    post: VerificationFeedPost,
    moderator_id: uuid.UUID,
    action: ModerationAction,
    *,
    internal_note: str | None = None,
    public_note: str | None = None,
    zone_id: uuid.UUID | None = None,
) -> VerificationFeedModeration:
    record = VerificationFeedModeration(
        post_id=post.id,
        moderator_user_id=moderator_id,
        action=action,
        internal_note=internal_note,
        public_note=public_note,
    )
    db.add(record)

    if action == ModerationAction.confirm:
        post.admin_confirmed = True
        post.admin_confirmed_at = _now()
        post.admin_confirmed_by = moderator_id
    elif action == ModerationAction.mark_fake:
        post.state = PostState.marked_fake
        post.admin_confirmed = False
    elif action == ModerationAction.take_down:
        post.state = PostState.taken_down
    elif action == ModerationAction.restore:
        post.state = PostState.live
    elif action == ModerationAction.promote_to_zone and zone_id:
        post.zone_id = zone_id

    await db.flush()
    await feed_svc.recalculate_trust(db, post.publisher_user_id)
    return record


async def get_admin_queue(
    db: AsyncSession,
    tab: str,
    *,
    moderator_tenant_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[VerificationFeedPost]:
    settings = get_settings()

    _eager = selectinload(VerificationFeedPost.attachments)
    if tab == "flagged":
        q = select(VerificationFeedPost).options(_eager).where(
            VerificationFeedPost.state == PostState.under_review
        )
    elif tab == "pre_publish":
        q = select(VerificationFeedPost).options(_eager).where(
            VerificationFeedPost.state == PostState.pending_ai
        ).order_by(VerificationFeedPost.created_at.asc())
    else:  # confirmation
        # Find posts with enough weighted corroborate signals
        corr_sub = (
            select(func.sum(VerificationFeedSignal.weight))
            .where(
                VerificationFeedSignal.post_id == VerificationFeedPost.id,
                VerificationFeedSignal.signal_type == SignalType.corroborate,
            )
            .correlate(VerificationFeedPost)
            .scalar_subquery()
        )
        q = select(VerificationFeedPost).options(_eager).where(
            VerificationFeedPost.state == PostState.live,
            VerificationFeedPost.admin_confirmed == False,  # noqa: E712
            corr_sub >= settings.confirmation_eligibility_min,
        ).order_by(VerificationFeedPost.created_at.asc())

    if tab == "flagged":
        flag_sub = (
            select(func.count())
            .select_from(VerificationFeedFlag)
            .where(VerificationFeedFlag.post_id == VerificationFeedPost.id)
            .correlate(VerificationFeedPost)
            .scalar_subquery()
        )
        q = q.order_by(flag_sub.desc(), VerificationFeedPost.created_at.asc())

    if moderator_tenant_id:
        from app.models.feed import PostScope
        q = q.where(
            (VerificationFeedPost.scope == PostScope.national)
            | (VerificationFeedPost.tenant_id == moderator_tenant_id)
        )

    offset = (page - 1) * page_size
    q = q.offset(offset).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_post_review_data(db: AsyncSession, post_id: uuid.UUID) -> dict:
    post_result = await db.execute(
        select(VerificationFeedPost)
        .options(selectinload(VerificationFeedPost.attachments))
        .where(VerificationFeedPost.id == post_id)
    )
    post = post_result.scalars().first()
    if not post:
        return {}

    signals_result = await db.execute(
        select(VerificationFeedSignal).where(VerificationFeedSignal.post_id == post_id)
    )
    signals = signals_result.scalars().all()

    flags_result = await db.execute(
        select(VerificationFeedFlag).where(VerificationFeedFlag.post_id == post_id)
    )
    flags = flags_result.scalars().all()

    mod_result = await db.execute(
        select(VerificationFeedModeration)
        .where(VerificationFeedModeration.post_id == post_id)
        .order_by(VerificationFeedModeration.created_at.desc())
    )
    mod_log = mod_result.scalars().all()

    trust_result = await db.execute(
        select(UserFeedTrust).where(UserFeedTrust.user_id == post.publisher_user_id)
    )
    publisher_trust = trust_result.scalars().first()

    return {
        "post": post,
        "signals": signals,
        "flags": flags,
        "moderation_history": mod_log,
        "publisher_trust": publisher_trust,
    }


async def get_signal_ring_patterns(db: AsyncSession) -> list[dict]:
    """Detect clusters: posts where ≥3 common users all corroborated."""
    from sqlalchemy import text
    result = await db.execute(
        text(
            """
            SELECT post_id, COUNT(user_id) as user_count
            FROM verification_feed_signals
            WHERE signal_type = 'corroborate'
            GROUP BY post_id
            HAVING COUNT(user_id) >= 3
            ORDER BY user_count DESC
            LIMIT 20
            """
        )
    )
    return [{"post_id": str(r.post_id), "corroborate_count": r.user_count} for r in result]


async def get_repeat_fake_publishers(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(UserFeedTrust).where(UserFeedTrust.confirmed_fake_count >= 2)
        .order_by(UserFeedTrust.confirmed_fake_count.desc())
    )
    rows = result.scalars().all()
    return [
        {
            "user_id": str(r.user_id),
            "confirmed_fake_count": r.confirmed_fake_count,
            "trust_tier": r.trust_tier.value,
        }
        for r in rows
    ]


async def get_trust_source_anomalies(db: AsyncSession) -> list[dict]:
    """Trusted users (silver/gold) who challenged posts later admin-confirmed accurate."""
    result = await db.execute(
        select(VerificationFeedSignal.user_id, func.count().label("anomaly_count"))
        .join(VerificationFeedPost, VerificationFeedSignal.post_id == VerificationFeedPost.id)
        .where(
            VerificationFeedSignal.signal_type == SignalType.challenge,
            VerificationFeedPost.admin_confirmed == True,  # noqa: E712
        )
        .group_by(VerificationFeedSignal.user_id)
        .having(func.count() >= 2)
        .order_by(func.count().desc())
    )
    rows = result.all()
    return [{"user_id": str(r.user_id), "anomaly_count": r.anomaly_count} for r in rows]


async def get_category_misuse(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(VerificationFeedPost.category, func.count().label("fake_count"))
        .join(
            VerificationFeedModeration,
            VerificationFeedModeration.post_id == VerificationFeedPost.id,
        )
        .where(VerificationFeedModeration.action == ModerationAction.mark_fake)
        .group_by(VerificationFeedPost.category)
        .order_by(func.count().desc())
    )
    return [{"category": r.category.value, "fake_count": r.fake_count} for r in result]


async def get_stats(db: AsyncSession, tenant_id: uuid.UUID | None = None) -> dict:
    from app.models.feed import PostScope

    q = select(VerificationFeedPost.state, func.count().label("cnt")).group_by(
        VerificationFeedPost.state
    )
    if tenant_id:
        q = q.where(
            (VerificationFeedPost.scope == PostScope.national)
            | (VerificationFeedPost.tenant_id == tenant_id)
        )
    result = await db.execute(q)
    by_state = {r.state.value: r.cnt for r in result}

    tier_result = await db.execute(
        select(UserFeedTrust.trust_tier, func.count().label("cnt")).group_by(
            UserFeedTrust.trust_tier
        )
    )
    by_tier = {r.trust_tier.value: r.cnt for r in tier_result}

    return {"by_state": by_state, "by_trust_tier": by_tier}
