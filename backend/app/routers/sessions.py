import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.redis import get_redis
from app.deps import get_current_user, TokenData
from app.models.session import Session
from app.schemas.auth import SessionInfo

router = APIRouter(prefix="/auth/sessions", tags=["sessions"])


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


@router.get("", response_model=list[SessionInfo])
async def list_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    result = await db.execute(
        select(Session).where(Session.user_id == token.user_id, Session.revoked == False)
        .order_by(Session.created_at.desc())
    )
    sessions = result.scalars().all()
    out = []
    for s in sessions:
        out.append(SessionInfo(
            id=s.id,
            device_fingerprint=s.device_fingerprint,
            user_agent=s.user_agent,
            ip_address=s.ip_address,
            created_at=s.created_at.isoformat(),
            expires_at=s.expires_at.isoformat(),
            current=(s.jti == token.jti),
        ))
    return out


@router.delete("/{session_id}")
async def revoke_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    token: TokenData = Depends(get_current_user),
):
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == token.user_id)
    )
    session = result.scalars().first()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.revoked:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Session already revoked")

    session.revoked = True
    session.revoked_at = _now()
    remaining = max(int((session.expires_at - _now()).total_seconds()), 1)
    from app.services.token import blacklist_jti
    await blacklist_jti(redis, session.jti, remaining)

    return {"message": "Session revoked"}
