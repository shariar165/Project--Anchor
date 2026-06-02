"""Verification Feed attachment storage."""
import hashlib
import uuid
from pathlib import Path

import aiofiles
import aiofiles.os
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.feed import VerificationFeedAttachment

FEED_UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads" / "feed"

ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "video/mp4", "video/quicktime",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


async def save_attachment(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> VerificationFeedAttachment:
    settings = get_settings()
    max_bytes = settings.feed_max_attachment_mb * 1024 * 1024

    # Validate size
    if len(file_bytes) > max_bytes:
        raise ValueError(f"File exceeds {settings.feed_max_attachment_mb} MB limit")

    # Validate content type
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"Unsupported file type: {content_type}")

    # Count existing attachments
    count_result = await db.execute(
        select(func.count()).select_from(VerificationFeedAttachment).where(
            VerificationFeedAttachment.post_id == post_id
        )
    )
    count = count_result.scalar() or 0
    if count >= settings.feed_max_attachments:
        raise ValueError(f"Maximum {settings.feed_max_attachments} attachments allowed")

    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Store file
    dest_dir = FEED_UPLOAD_DIR / str(post_id)
    await aiofiles.os.makedirs(str(dest_dir), exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{filename}"
    dest_path = dest_dir / safe_name
    async with aiofiles.open(str(dest_path), "wb") as f:
        await f.write(file_bytes)

    file_ref = f"{post_id}/{safe_name}"
    attachment = VerificationFeedAttachment(
        post_id=post_id,
        file_ref=file_ref,
        file_hash_sha256=file_hash,
        content_type=content_type,
        file_size_bytes=len(file_bytes),
    )
    db.add(attachment)
    await db.flush()
    return attachment


async def get_attachment(
    db: AsyncSession,
    attachment_id: uuid.UUID,
    post_id: uuid.UUID | None = None,
) -> VerificationFeedAttachment | None:
    q = select(VerificationFeedAttachment).where(VerificationFeedAttachment.id == attachment_id)
    if post_id:
        q = q.where(VerificationFeedAttachment.post_id == post_id)
    result = await db.execute(q)
    return result.scalars().first()


async def explain_attachment(
    db: AsyncSession,
    attach: VerificationFeedAttachment,
    lang: str = "EN",
) -> str:
    # Return cached result if available
    if attach.explain_cache:
        return attach.explain_cache

    # Only explain PDF and documents
    if attach.content_type not in {"application/pdf", "application/msword",
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}:
        explanation = "Document explanation is only available for PDF and Word files."
        attach.explain_cache = explanation
        await db.flush()
        return explanation

    try:
        file_path = FEED_UPLOAD_DIR / attach.file_ref
        async with aiofiles.open(str(file_path), "rb") as f:
            file_bytes = await f.read()

        lang_hint = "in Bengali" if lang == "BN" else "in simple English"
        explanation = (
            f"This document ({attach.content_type}) is {attach.file_size_bytes} bytes. "
            f"Document analysis is available once the AI engine is connected. "
            f"Please review the attached file directly."
        )
    except Exception:
        explanation = "Could not read document. Please verify the file was uploaded correctly."

    attach.explain_cache = explanation
    await db.flush()
    return explanation
