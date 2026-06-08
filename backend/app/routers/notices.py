import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.redis import get_redis
from app.deps import get_current_user, require_role, TokenData
from app.models.notice import NoticeScope, NoticeStatus
from app.models.user import User, AccountStatus
from app.schemas.notices import NoticeCreate, NoticeUpdate, NoticeResponse
from app.services import notice_svc
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


@router.post("", response_model=NoticeResponse, status_code=status.HTTP_201_CREATED)
async def create_notice(
    body: NoticeCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await notice_svc.create_notice(db, body, published_by=token.user_id)


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
