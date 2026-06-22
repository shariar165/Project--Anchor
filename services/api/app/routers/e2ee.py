import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, TokenData
from app.models.e2ee import UserE2EEKey
from app.schemas.e2ee import PublicKeyUpsert, PublicKeyResponse

router = APIRouter(prefix="/v1/e2ee", tags=["e2ee"])


def _to_response(key: UserE2EEKey) -> PublicKeyResponse:
    # The model column is named `public_key_pem` for historical reasons; we store a JWK there.
    return PublicKeyResponse(
        user_id=key.user_id,
        public_key_jwk=key.public_key_pem,
        key_fingerprint=key.key_fingerprint,
    )


@router.put("/keys", response_model=PublicKeyResponse)
async def upsert_my_key(
    body: PublicKeyUpsert,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    result = await db.execute(select(UserE2EEKey).where(UserE2EEKey.user_id == token.user_id))
    key = result.scalars().first()
    if key:
        key.public_key_pem = body.public_key_jwk
        key.key_fingerprint = body.key_fingerprint
    else:
        key = UserE2EEKey(
            user_id=token.user_id,
            public_key_pem=body.public_key_jwk,
            key_fingerprint=body.key_fingerprint,
        )
        db.add(key)
    await db.flush()
    return _to_response(key)


@router.get("/keys/{user_id}", response_model=PublicKeyResponse)
async def get_user_key(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    result = await db.execute(select(UserE2EEKey).where(UserE2EEKey.user_id == user_id))
    key = result.scalars().first()
    if not key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No public key for user")
    return _to_response(key)
