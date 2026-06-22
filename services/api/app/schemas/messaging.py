from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
import uuid


class ConversationStartRequest(BaseModel):
    lawyer_id: uuid.UUID


class ConversationResponse(BaseModel):
    id: uuid.UUID
    counterpart_user_id: uuid.UUID
    counterpart_name: str
    counterpart_role: str
    last_message_at: datetime | None
    unread_count: int
    counterpart_public_key: str | None = None


class MessageCreate(BaseModel):
    ciphertext: str = Field(min_length=1, max_length=20000)
    iv: str = Field(min_length=1, max_length=64)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    ciphertext: str
    iv: str
    created_at: datetime
    read_at: datetime | None
