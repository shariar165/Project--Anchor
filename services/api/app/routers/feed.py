"""Verification Feed — user-facing endpoints.

Route order: ALL static paths before /{post_id} parameterized paths.
"""
import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_stepup, TokenData
from app.limiter import limiter
from app.redis import get_redis
from app.schemas.feed import (
    PostCreate, PostEdit, SignalRequest, FlagRequest,
    PostDetail, PostListItem, PublishResponse, SignalResponse,
    SignalCountsResponse, AttachmentInfo, FeedProfileResponse,
)
from app.services import feed_svc, feed_prescreen, feed_sse, feed_attachment_svc
from app.services.audit import log_event as audit_log
from app.services.device import get_ip
from app.models.feed import SignalType, TrustTier

router = APIRouter(tags=["feed"])


def _optional_bearer():
    """Returns None if no Authorization header, else validates the token."""
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi import Depends as _Depends
    _b = HTTPBearer(auto_error=False)

    async def _dep(
        credentials=_Depends(_b),
        db: AsyncSession = _Depends(get_db),
        redis=_Depends(get_redis),
    ) -> TokenData | None:
        if not credentials:
            return None
        from app.services.token import decode_token, is_blacklisted
        from app.models.user import User, AccountStatus
        from sqlalchemy import select
        try:
            payload = decode_token(credentials.credentials)
        except ValueError:
            return None
        if payload.get("type") != "access":
            return None
        td = TokenData(payload)
        if await is_blacklisted(redis, td.jti):
            return None
        result = await db.execute(select(User).where(User.id == td.user_id))
        user = result.scalars().first()
        if not user or user.status != AccountStatus.active:
            return None
        return td
    return _dep


_optional_user = _optional_bearer()


def _post_to_detail(post, counts: dict, user_signal: str | None) -> PostDetail:
    sc = SignalCountsResponse(
        corroborate=counts["corroborate"],
        challenge=counts["challenge"],
        flags=counts["flags"],
        user_signal=user_signal,
    )
    return PostDetail(
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
    )


# ─── Static paths (must come before /{post_id}) ──────────────────────────────

@router.get("/v1/feed/me/profile", response_model=FeedProfileResponse)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    trust = await feed_svc.get_or_create_trust(db, token.user_id)
    await db.commit()
    return FeedProfileResponse(
        user_id=trust.user_id,
        trust_tier=trust.trust_tier.value,
        confirmed_accurate_count=trust.confirmed_accurate_count,
        confirmed_fake_count=trust.confirmed_fake_count,
        last_recalculated_at=trust.last_recalculated_at,
    )


@router.get("/v1/feed/users/{user_id}/public-profile")
async def get_public_profile(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    trust = await feed_svc.get_or_create_trust(db, user_id)
    await db.commit()
    return {
        "user_id": str(trust.user_id),
        "trust_tier": trust.trust_tier.value,
    }


@router.post("/v1/feed/attachments", response_model=AttachmentInfo)
async def upload_attachment(
    request: Request,
    post_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    content = await file.read()
    content_type = file.content_type or "application/octet-stream"
    try:
        attach = await feed_attachment_svc.save_attachment(
            db,
            post_id=post_id,
            file_bytes=content,
            filename=file.filename or "upload",
            content_type=content_type,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    return AttachmentInfo(
        id=attach.id,
        file_hash_sha256=attach.file_hash_sha256,
        content_type=attach.content_type,
        file_size_bytes=attach.file_size_bytes,
        uploaded_at=attach.uploaded_at,
    )


@router.post("/v1/feed/attachments/{attachment_id}/explain")
async def explain_attachment(
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    attach = await feed_attachment_svc.get_attachment(db, attachment_id)
    if not attach:
        raise HTTPException(404, "Attachment not found")
    explanation = await feed_attachment_svc.explain_attachment(db, attach)
    await db.commit()
    return {"attachment_id": str(attachment_id), "explanation": explanation}


@router.get("/v1/feed", response_model=list[PostListItem])
@limiter.limit("60/minute")
async def list_feed(
    request: Request,
    scope: str = "national",
    category: Optional[str] = None,
    sort: str = "recent",
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    settings = get_settings()
    page_size = min(page_size, 50)

    # Campus scope works even when the account has no tenant association (single-tenant
    # deployment): list_posts only narrows by tenant_id when one is present, so a null
    # tenant_id returns the shared campus edition.
    posts = await feed_svc.list_posts(
        db,
        scope=scope,
        category=category,
        sort=sort,
        page=page,
        page_size=page_size,
        tenant_id=token.tenant_id if scope == "campus" else None,
    )

    items = []
    for post in posts:
        counts = await feed_svc.get_signal_counts(db, post.id)
        user_sig = await feed_svc.get_user_signal(db, post.id, token.user_id)
        sc = SignalCountsResponse(
            corroborate=counts["corroborate"],
            challenge=counts["challenge"],
            flags=counts["flags"],
            user_signal=user_sig,
        )
        items.append(PostListItem(
            id=post.id,
            post_number=post.post_number,
            scope=post.scope.value,
            category=post.category.value,
            title=post.title,
            state=post.state.value,
            admin_confirmed=post.admin_confirmed,
            created_at=post.created_at,
            signal_counts=sc,
        ))
    return items


@router.post("/v1/feed", response_model=PublishResponse)
@limiter.limit("3/minute")
async def publish_post(
    request: Request,
    body: PostCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_stepup),
):
    settings = get_settings()
    # Campus posts are allowed without a tenant association (single-tenant deployment);
    # the post is stored with the publisher's tenant_id, which may be null.

    # AI pre-screen (synchronous gate)
    try:
        prescreen = await asyncio.wait_for(
            feed_prescreen.run_prescreen(body.title, body.body, body.category),
            timeout=settings.ai_prescreen_timeout_seconds,
        )
    except asyncio.TimeoutError:
        prescreen = {"verdict": "manual_review", "reason": "timeout", "flags": []}

    if prescreen["verdict"] == "block":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": (
                    "This post could not be published because it appears to violate our "
                    "content policy."
                ),
                "reason": prescreen.get("reason", "content_policy_violation"),
            },
        )

    post = await feed_svc.create_post(
        db,
        publisher_user_id=token.user_id,
        tenant_id=token.tenant_id,
        scope=body.scope,
        category=body.category,
        title=body.title,
        body=body.body,
        tags=body.tags,
        geo_lat=body.geo_lat,
        geo_lng=body.geo_lng,
        geo_address=body.geo_address,
        prescreen=prescreen,
    )
    await audit_log(db, "feed_post_created", token.user_id, get_ip(request), {"post_number": post.post_number})
    await db.commit()

    if prescreen["verdict"] == "pass":
        background_tasks.add_task(feed_svc.activate_post, post.id)
        msg = "Post is being published."
    else:
        msg = "Post is under review and will be visible once approved."

    return PublishResponse(
        post_id=post.id,
        post_number=post.post_number,
        state=post.state.value,
        ai_verdict=prescreen["verdict"],
        message=msg,
    )


# ─── Parameterized paths (/v1/feed/{post_id}/...) ────────────────────────────

@router.get("/v1/feed/{post_id}", response_model=PostDetail)
async def get_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    post = await feed_svc.get_post(db, post_id, requesting_tenant_id=token.tenant_id)
    if not post:
        raise HTTPException(404, "Post not found")

    counts = await feed_svc.get_signal_counts(db, post.id)
    user_sig = await feed_svc.get_user_signal(db, post.id, token.user_id)
    return _post_to_detail(post, counts, user_sig)


@router.get("/v1/feed/{post_id}/stream")
async def stream_signals(
    post_id: uuid.UUID,
    redis=Depends(get_redis),
):
    from sse_starlette.sse import EventSourceResponse

    async def _gen():
        async for msg in feed_sse.subscribe_signal_updates(redis, post_id):
            yield {"data": msg}

    return EventSourceResponse(_gen())


@router.patch("/v1/feed/{post_id}", response_model=PostDetail)
async def edit_post(
    post_id: uuid.UUID,
    body: PostEdit,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_stepup),
):
    post = await feed_svc.get_post(db, post_id)
    if not post or post.publisher_user_id != token.user_id:
        raise HTTPException(404, "Post not found")

    from app.models.feed import PostState
    if post.state in (PostState.marked_fake, PostState.taken_down):
        raise HTTPException(409, "This post has been moderated and cannot be edited.")

    post = await feed_svc.edit_post(
        db, post,
        editor_id=token.user_id,
        title=body.title,
        body=body.body,
        tags=body.tags,
        geo_lat=body.geo_lat,
        geo_lng=body.geo_lng,
        geo_address=body.geo_address,
    )
    await audit_log(db, "feed_post_edited", token.user_id, get_ip(request), {"post_id": str(post_id)})
    await db.commit()

    # Re-fetch after commit to get server-generated updated_at
    post = await feed_svc.get_post(db, post_id)
    counts = await feed_svc.get_signal_counts(db, post_id)
    return _post_to_detail(post, counts, None)


@router.delete("/v1/feed/{post_id}", status_code=204)
async def delete_post(
    post_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_stepup),
):
    post = await feed_svc.get_post(db, post_id)
    if not post or post.publisher_user_id != token.user_id:
        raise HTTPException(404, "Post not found")

    await feed_svc.soft_delete_post(db, post)
    await audit_log(db, "feed_post_deleted", token.user_id, get_ip(request), {"post_id": str(post_id)})
    await db.commit()


async def _signal_endpoint(
    post_id: uuid.UUID,
    signal_type: SignalType,
    body: SignalRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
    token: TokenData,
    redis,
) -> SignalResponse:
    post = await feed_svc.get_post(db, post_id, requesting_tenant_id=token.tenant_id)
    if not post:
        raise HTTPException(404, "Post not found")
    if post.publisher_user_id == token.user_id:
        raise HTTPException(400, "Cannot signal on your own post")

    # Get publisher trust tier for weight
    trust = await feed_svc.get_or_create_trust(db, token.user_id)
    result = await feed_svc.upsert_signal(
        db,
        post_id=post_id,
        user_id=token.user_id,
        signal_type=signal_type,
        trust_tier=trust.trust_tier,
        reason=body.reason,
    )
    await db.commit()

    counts = await feed_svc.get_signal_counts(db, post_id)
    background_tasks.add_task(feed_sse.publish_signal_update, redis, post_id, counts)

    return SignalResponse(
        action=result["action"],
        signal_type=result["signal_type"],
        counts=SignalCountsResponse(
            corroborate=counts["corroborate"],
            challenge=counts["challenge"],
            flags=counts["flags"],
            user_signal=result["signal_type"] if result["action"] != "removed" else None,
        ),
    )


@router.post("/v1/feed/{post_id}/corroborate", response_model=SignalResponse)
async def corroborate(
    post_id: uuid.UUID,
    body: SignalRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
    redis=Depends(get_redis),
):
    return await _signal_endpoint(
        post_id, SignalType.corroborate, body, request, background_tasks, db, token, redis
    )


@router.post("/v1/feed/{post_id}/challenge", response_model=SignalResponse)
async def challenge(
    post_id: uuid.UUID,
    body: SignalRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
    redis=Depends(get_redis),
):
    return await _signal_endpoint(
        post_id, SignalType.challenge, body, request, background_tasks, db, token, redis
    )


@router.delete("/v1/feed/{post_id}/signal", status_code=204)
async def remove_signal(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    post = await feed_svc.get_post(db, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    await feed_svc.remove_signal(db, post_id, token.user_id)
    await db.commit()


@router.post("/v1/feed/{post_id}/flag", status_code=200)
async def flag_post(
    post_id: uuid.UUID,
    body: FlagRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    post = await feed_svc.get_post(db, post_id, requesting_tenant_id=token.tenant_id)
    if not post:
        raise HTTPException(404, "Post not found")

    try:
        await feed_svc.add_flag(
            db,
            post_id=post_id,
            user_id=token.user_id,
            flag_reason=body.flag_reason,
            note=body.note,
        )
    except ValueError:
        raise HTTPException(409, "You have already flagged this post")

    await audit_log(db, "feed_post_flagged", token.user_id, get_ip(request), {"post_id": str(post_id)})
    await db.commit()
    return {"message": "Post flagged for review"}
