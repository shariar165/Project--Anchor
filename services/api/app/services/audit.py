import hashlib
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog


def _canonical(event_type: str, user_id: str | None, metadata: dict | None, created_at: datetime) -> bytes:
    obj = {
        "event_type": event_type,
        "user_id": user_id,
        "metadata": metadata or {},
        "created_at": created_at.isoformat(),
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


async def log_event(
    db: AsyncSession,
    event_type: str,
    user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(1))
    prev = result.scalars().first()
    prev_hash = prev.row_hash if prev else b"\x00" * 32

    created_at = datetime.now(tz=timezone.utc)
    payload = _canonical(event_type, str(user_id) if user_id else None, metadata, created_at)
    row_hash = hashlib.sha256(prev_hash + payload).digest()

    entry = AuditLog(
        event_type=event_type,
        user_id=user_id,
        ip_address=ip_address,
        metadata_=metadata,
        row_hash=row_hash,
        created_at=created_at,
    )
    db.add(entry)
    await db.flush()
    return entry
