import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.redis import get_redis
from app.deps import get_current_user, require_role, TokenData
from app.models.routine import AcademicRoutine, RoutineStatus
from app.models.user import User, AccountStatus
from app.schemas.routines import RoutineCreate, RoutineUpdate, RoutineResponse
from app.services import routine_svc
from app.services.token import decode_token, is_blacklisted

router = APIRouter(prefix="/v1/routines", tags=["routines"])

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


@router.get("", response_model=list[RoutineResponse])
async def list_routines(
    department: str | None = Query(default=None),
    batch: str | None = Query(default=None),
    semester: str | None = Query(default=None),
    status: RoutineStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    token: TokenData | None = Depends(_opt_user),
):
    admin = _is_admin(token)
    return await routine_svc.list_routines(
        db,
        department=department,
        batch=batch,
        semester=semester,
        status_filter=status if admin else None,
        is_admin=admin,
        page=page,
    )


@router.post("", response_model=RoutineResponse, status_code=status.HTTP_201_CREATED)
async def create_routine(
    body: RoutineCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await routine_svc.create_routine(db, body, created_by=token.user_id)


@router.get("/{routine_id}", response_model=RoutineResponse)
async def get_routine(
    routine_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData | None = Depends(_opt_user),
):
    admin = _is_admin(token)
    routine = await routine_svc.get_routine(db, routine_id, is_admin=admin)
    if routine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Routine not found")
    return routine


@router.patch("/{routine_id}", response_model=RoutineResponse)
async def update_routine(
    routine_id: uuid.UUID,
    body: RoutineUpdate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    routine = await routine_svc.get_routine(db, routine_id, is_admin=True)
    if routine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Routine not found")
    return await routine_svc.update_routine(db, routine, body)


@router.post("/{routine_id}/publish", response_model=RoutineResponse)
async def publish_routine(
    routine_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    routine = await routine_svc.get_routine(db, routine_id, is_admin=True)
    if routine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Routine not found")
    try:
        return await routine_svc.publish_routine(db, routine, published_by=token.user_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
