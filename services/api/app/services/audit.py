import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
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
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1)
    )
    prev = result.scalars().first()
    prev_hash = prev.row_hash if prev else b"\x00" * 32

    # The chain is ordered by created_at. System clocks (especially on Windows)
    # have coarse resolution, so two consecutive events can share a timestamp;
    # since row id is a random UUID it provides no insertion order. Force
    # created_at to be strictly greater than the previous row so created_at is a
    # reliable total order for both chaining and verification.
    created_at = datetime.now(tz=timezone.utc)
    if prev is not None:
        prev_ts = prev.created_at
        if prev_ts.tzinfo is None:  # SQLite returns tz-naive datetimes
            prev_ts = prev_ts.replace(tzinfo=timezone.utc)
        if created_at <= prev_ts:
            created_at = prev_ts + timedelta(microseconds=1)
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


def mask_email(email: str | None) -> str:
    """Partially redact an email for display: 'shariar@diu.edu.bd' -> 'sh***@diu.edu.bd'."""
    if not email:
        return "system"
    local, sep, domain = email.partition("@")
    if not sep:
        # Not an email (could be a phone or username) — keep first 2 chars
        return (local[:2] + "***") if len(local) > 2 else "***"
    visible = local[:2] if len(local) >= 2 else local
    return f"{visible}***@{domain}"


async def verify_chain(db: AsyncSession, limit: int = 1000) -> dict:
    """
    Verify the SHA-256 hash chain over the most recent `limit` rows.

    Each row's stored row_hash must equal sha256(prev.row_hash + canonical(row)),
    where prev is the immediately preceding row by created_at. To validate a
    bounded window we fetch one extra "anchor" row just before it: when the
    window reaches genesis the anchor is absent and the oldest row is verified
    against the zero hash; otherwise the anchor's *stored* hash seeds the chain
    (the anchor itself is not re-verified).

    Returns {ok, checked, first_tampered_id}. An empty/1-row log is trivially ok.
    """
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit + 1)
    )
    fetched = list(reversed(result.scalars().all()))

    if not fetched:
        return {"ok": True, "checked": 0, "first_tampered_id": None}

    # If we got more than `limit` rows, the oldest is an anchor (not re-verified).
    reached_genesis = len(fetched) <= limit
    if reached_genesis:
        prev_hash = b"\x00" * 32
        to_verify = fetched
    else:
        prev_hash = fetched[0].row_hash
        to_verify = fetched[1:]

    checked = 0
    for row in to_verify:
        # Reproduce the exact created_at used when the hash was written. log_event
        # always writes a tz-aware UTC datetime; SQLite reads it back tz-naive, so
        # normalize to UTC to reconstruct the identical isoformat string.
        row_ts = row.created_at
        if row_ts.tzinfo is None:
            row_ts = row_ts.replace(tzinfo=timezone.utc)
        payload = _canonical(
            row.event_type,
            str(row.user_id) if row.user_id else None,
            row.metadata_,
            row_ts,
        )
        expected = hashlib.sha256(prev_hash + payload).digest()
        checked += 1
        if expected != row.row_hash:
            return {"ok": False, "checked": checked, "first_tampered_id": str(row.id)}
        prev_hash = row.row_hash

    return {"ok": True, "checked": checked, "first_tampered_id": None}
