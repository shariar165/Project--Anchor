import uuid
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.redis import get_redis
from app.services.token import decode_token, is_blacklisted
from app.models.user import User, AccountStatus

_bearer = HTTPBearer()


class TokenData:
    def __init__(self, payload: dict):
        self.user_id = uuid.UUID(payload["sub"])
        self.role = payload["role"]
        self.jti = payload["jti"]
        self.tenant_id = uuid.UUID(payload["tenant_id"]) if payload.get("tenant_id") else None
        self.token_type = payload.get("type", "access")
        exp_ts = payload.get("exp")
        self.expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc) if exp_ts else None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> TokenData:
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")

    token_data = TokenData(payload)

    if await is_blacklisted(redis, token_data.jti):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalars().first()
    if not user or user.status != AccountStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not active")

    return token_data


def require_role(*roles: str):
    async def _dep(token: TokenData = Depends(get_current_user)):
        if token.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return token
    return _dep


async def require_stepup(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> TokenData:
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid step-up token")

    if payload.get("type") != "stepup":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Step-up token required")

    if await is_blacklisted(redis, payload["jti"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Step-up token expired or used")

    token_data = TokenData(payload)
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalars().first()
    if not user or user.status != AccountStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not active")
    return token_data
