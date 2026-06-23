import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.limiter import limiter
from app.redis import get_redis
from app.deps import get_current_user, require_role, TokenData
from app.models.notice import NoticeScope, NoticeStatus
from app.models.user import User, AccountStatus
from app.schemas.notices import (
    NoticeCreate,
    NoticeUpdate,
    NoticeResponse,
    NoticeGenerateRequest,
    NoticeGenerateResponse,
)
from app.services import notice_svc, notice_ai_svc, export_svc
from app.services.token import decode_token, is_blacklisted

router = APIRouter(prefix="/v1/notices", tags=["notices"])

_opt_bearer = HTTPBearer(auto_error=False)


async def _opt_user(
    creds: HTTPAuthorizationCredentials | None = Security(_opt_bearer),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> TokenData | None:
    if creds is None:
        return None
    try:
        payload = decode_token(creds.credentials)
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
    except Exception:
        return None


def _is_admin(token: TokenData | None) -> bool:
    return token is not None and token.role in ("admin", "moderator")


@router.get("", response_model=list[NoticeResponse])
async def list_notices(
    scope: NoticeScope | None = Query(default=None),
    dept: str | None = Query(default=None),
    batch: str | None = Query(default=None),
    status: NoticeStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    token: TokenData | None = Depends(_opt_user),
):
    admin = _is_admin(token)
    return await notice_svc.list_notices(
        db,
        scope=scope,
        dept=dept,
        batch=batch,
        status_filter=status if admin else None,
        is_admin=admin,
        page=page,
    )


@router.post("/generate", response_model=NoticeGenerateResponse)
@limiter.limit("20/minute")
async def generate_notice(
    request: Request,
    body: NoticeGenerateRequest,
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Draft a DIU notice with Ollama. Falls back to a template when AI is offline."""
    result = await notice_ai_svc.generate_notice(
        prompt=body.prompt,
        language=body.language,
        tone=body.tone,
        audience=body.audience,
        subject=body.subject,
    )
    return result


@router.post("", response_model=NoticeResponse, status_code=status.HTTP_201_CREATED)
async def create_notice(
    body: NoticeCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await notice_svc.create_notice(db, body, published_by=token.user_id)


@router.get("/{notice_id}/export")
async def export_notice(
    notice_id: uuid.UUID,
    format: str = Query(default="pdf"),
    db: AsyncSession = Depends(get_db),
    token: TokenData | None = Depends(_opt_user),
):
    """Download a single notice as PDF / DOCX / CSV. Students can only export
    published notices; admins/moderators can export any."""
    notice = await notice_svc.get_notice(db, notice_id)
    if notice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notice not found")
    if not _is_admin(token) and notice.status != NoticeStatus.published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notice not found")

    meta = [("Scope", str(notice.scope).replace("_", " ").title())]
    if notice.dept:
        meta.append(("Department", notice.dept))
    if notice.batch:
        meta.append(("Batch", notice.batch))
    when = notice.published_at or notice.created_at
    if when:
        meta.append(("Published", when.strftime("%d %b %Y")))

    doc = export_svc.ExportDoc(
        title=notice.title,
        subtitle="Campus Notice",
        meta=meta,
        body=notice.body or "",
    )
    return export_svc.export_response(doc, format, f"notice-{str(notice.id)[:8]}")


@router.patch("/{notice_id}", response_model=NoticeResponse)
async def update_notice(
    notice_id: uuid.UUID,
    body: NoticeUpdate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    notice = await notice_svc.get_notice(db, notice_id)
    if notice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notice not found")
    return await notice_svc.update_notice(db, notice, body)


@router.post("/{notice_id}/publish", response_model=NoticeResponse)
async def publish_notice(
    notice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    notice = await notice_svc.get_notice(db, notice_id)
    if notice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notice not found")
    try:
        return await notice_svc.publish_notice(db, notice)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
