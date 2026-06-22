import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.messaging import Conversation, Message
from app.models.lawyer import Lawyer
from app.models.user import User

PAGE_SIZE = 50


async def start_conversation(
    db: AsyncSession, user_id: uuid.UUID, lawyer_id: uuid.UUID
) -> Conversation:
    """Get-or-create a conversation between a user and a verified lawyer.

    Raises ValueError if the lawyer is not a verified, account-linked lawyer, or if
    the caller is trying to message themselves.
    """
    result = await db.execute(select(Lawyer).where(Lawyer.id == lawyer_id))
    lawyer = result.scalars().first()
    if not lawyer or not lawyer.verified or lawyer.user_id is None:
        raise ValueError("Lawyer is not available for messaging")
    if lawyer.user_id == user_id:
        raise ValueError("You cannot start a conversation with yourself")

    existing = await db.execute(
        select(Conversation).where(
            and_(
                Conversation.user_id == user_id,
                Conversation.lawyer_user_id == lawyer.user_id,
            )
        )
    )
    conv = existing.scalars().first()
    if conv:
        return conv

    conv = Conversation(user_id=user_id, lawyer_user_id=lawyer.user_id)
    db.add(conv)
    await db.flush()
    return conv


async def list_conversations(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    """List a user's conversations from either side, with counterpart + unread count."""
    result = await db.execute(
        select(Conversation)
        .where(or_(Conversation.user_id == user_id, Conversation.lawyer_user_id == user_id))
        .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc())
    )
    conversations = list(result.scalars().all())

    out: list[dict] = []
    for conv in conversations:
        counterpart_id = conv.lawyer_user_id if conv.user_id == user_id else conv.user_id
        cp_result = await db.execute(select(User).where(User.id == counterpart_id))
        counterpart = cp_result.scalars().first()
        unread = await db.scalar(
            select(func.count()).select_from(Message).where(
                and_(
                    Message.conversation_id == conv.id,
                    Message.sender_id != user_id,
                    Message.read_at.is_(None),
                )
            )
        )
        out.append({
            "id": conv.id,
            "counterpart_user_id": counterpart_id,
            "counterpart_name": counterpart.full_name if counterpart else "Unknown",
            "counterpart_role": (counterpart.role.value if counterpart else "user"),
            "last_message_at": conv.last_message_at,
            "unread_count": int(unread or 0),
        })
    return out


async def get_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> Conversation | None:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    return result.scalars().first()


def is_participant(conv: Conversation, user_id: uuid.UUID) -> bool:
    return user_id in (conv.user_id, conv.lawyer_user_id)


async def list_messages(
    db: AsyncSession, conversation_id: uuid.UUID, after: datetime | None = None
) -> list[Message]:
    q = select(Message).where(Message.conversation_id == conversation_id)
    if after is not None:
        q = q.where(Message.created_at > after)
    q = q.order_by(Message.created_at).limit(500)
    result = await db.execute(q)
    return list(result.scalars().all())


async def create_message(
    db: AsyncSession, conv: Conversation, sender_id: uuid.UUID, ciphertext: str, iv: str
) -> Message:
    msg = Message(
        conversation_id=conv.id,
        sender_id=sender_id,
        ciphertext=ciphertext,
        iv=iv,
    )
    db.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)
    await db.flush()
    return msg


async def mark_read(db: AsyncSession, conversation_id: uuid.UUID, reader_id: uuid.UUID) -> int:
    """Mark all counterpart messages in a conversation as read. Returns count updated."""
    result = await db.execute(
        select(Message).where(
            and_(
                Message.conversation_id == conversation_id,
                Message.sender_id != reader_id,
                Message.read_at.is_(None),
            )
        )
    )
    now = datetime.now(timezone.utc)
    count = 0
    for msg in result.scalars().all():
        msg.read_at = now
        count += 1
    await db.flush()
    return count
