import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.redis import get_redis
from app.deps import get_current_user, TokenData
from app.models.e2ee import UserE2EEKey
from app.models.user import User, AccountStatus
from app.services.token import decode_token, is_blacklisted
from app.schemas.messaging import (
    ConversationStartRequest, ConversationResponse, MessageCreate, MessageResponse,
)
from app.services import messaging_svc, messaging_sse, notification_svc

router = APIRouter(prefix="/v1/conversations", tags=["messaging"])


async def _public_key_for(db: AsyncSession, user_id: uuid.UUID) -> str | None:
    result = await db.execute(select(UserE2EEKey).where(UserE2EEKey.user_id == user_id))
    key = result.scalars().first()
    return key.public_key_pem if key else None


async def _load_participant_conversation(db: AsyncSession, conversation_id: uuid.UUID, user_id):
    conv = await messaging_svc.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if not messaging_svc.is_participant(conv, user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not a participant")
    return conv


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def start_conversation(
    body: ConversationStartRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    try:
        conv = await messaging_svc.start_conversation(db, token.user_id, body.lawyer_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))

    counterpart_id = conv.lawyer_user_id if conv.user_id == token.user_id else conv.user_id
    cp = (await db.execute(select(User).where(User.id == counterpart_id))).scalars().first()
    return ConversationResponse(
        id=conv.id,
        counterpart_user_id=counterpart_id,
        counterpart_name=cp.full_name if cp else "Unknown",
        counterpart_role=cp.role.value if cp else "user",
        last_message_at=conv.last_message_at,
        unread_count=0,
        counterpart_public_key=await _public_key_for(db, counterpart_id),
    )


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    rows = await messaging_svc.list_conversations(db, token.user_id)
    out = []
    for r in rows:
        out.append(ConversationResponse(
            **r,
            counterpart_public_key=await _public_key_for(db, r["counterpart_user_id"]),
        ))
    return out


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: uuid.UUID,
    after: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    await _load_participant_conversation(db, conversation_id, token.user_id)
    msgs = await messaging_svc.list_messages(db, conversation_id, after=after)
    return [MessageResponse.model_validate(m) for m in msgs]


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    token: TokenData = Depends(get_current_user),
):
    conv = await _load_participant_conversation(db, conversation_id, token.user_id)
    msg = await messaging_svc.create_message(
        db, conv, token.user_id, body.ciphertext, body.iv
    )
    payload = MessageResponse.model_validate(msg)
    await messaging_sse.publish_message(
        redis, conv.id, payload.model_dump(mode="json")
    )

    # Notify the other participant (message content is E2EE — keep the body generic).
    recipient_id = conv.lawyer_user_id if token.user_id == conv.user_id else conv.user_id
    sender_is_lawyer = token.user_id == conv.lawyer_user_id
    try:
        await notification_svc.create(
            db, user_id=recipient_id, type="lawyer", mode="country",
            title="New message from your lawyer" if sender_is_lawyer else "New message from a client",
            body="You have a new secure message. Tap to read.",
            route="conversations", params={"conversation_id": str(conv.id)},
            commit=False,
        )
    except Exception:
        pass

    return payload


@router.post("/{conversation_id}/read")
async def mark_read(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    await _load_participant_conversation(db, conversation_id, token.user_id)
    count = await messaging_svc.mark_read(db, conversation_id, token.user_id)
    return {"marked_read": count}


@router.get("/{conversation_id}/stream")
async def stream_messages(
    conversation_id: uuid.UUID,
    access_token: str = Query(..., alias="token"),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    # EventSource cannot set Authorization headers, so the access token is passed as a
    # query param and validated here. Only ciphertext crosses the channel regardless.
    try:
        payload = decode_token(access_token)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")
    if await is_blacklisted(redis, payload["jti"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
    user_id = uuid.UUID(payload["sub"])
    user = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
    if not user or user.status != AccountStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not active")

    await _load_participant_conversation(db, conversation_id, user_id)

    from sse_starlette.sse import EventSourceResponse

    async def _gen():
        async for msg in messaging_sse.subscribe_messages(redis, conversation_id):
            yield {"data": msg}

    return EventSourceResponse(_gen())
