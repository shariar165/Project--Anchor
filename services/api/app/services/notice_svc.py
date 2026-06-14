import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.notice import Notice, NoticeScope, NoticeStatus
from app.schemas.notices import NoticeCreate, NoticeUpdate

PAGE_SIZE = 20


async def list_notices(
    db: AsyncSession,
    scope: NoticeScope | None = None,
    dept: str | None = None,
    batch: str | None = None,
    tenant_id: uuid.UUID | None = None,
    status_filter: NoticeStatus | None = None,
    is_admin: bool = False,
    page: int = 1,
) -> list[Notice]:
    q = select(Notice)
    if not is_admin:
        q = q.where(Notice.status == NoticeStatus.published)
    elif status_filter is not None:
        q = q.where(Notice.status == status_filter)
    if scope is not None:
        q = q.where(Notice.scope == scope)
    if dept is not None:
        q = q.where(Notice.dept == dept)
    if batch is not None:
        q = q.where(Notice.batch == batch)
    if tenant_id is not None:
        q = q.where(Notice.tenant_id == tenant_id)
    q = q.order_by(Notice.created_at.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    result = await db.execute(q)
    return list(result.scalars().all())


async def create_notice(
    db: AsyncSession,
    data: NoticeCreate,
    published_by: uuid.UUID,
) -> Notice:
    notice = Notice(
        tenant_id=data.tenant_id,
        scope=data.scope,
        dept=data.dept,
        batch=data.batch,
        title=data.title,
        body=data.body,
        published_by_user_id=published_by,
        expires_at=data.expires_at,
        status=NoticeStatus.draft,
    )
    db.add(notice)
    await db.commit()
    await db.refresh(notice)
    return notice


async def update_notice(
    db: AsyncSession,
    notice: Notice,
    data: NoticeUpdate,
) -> Notice:
    if data.title is not None:
        notice.title = data.title
    if data.body is not None:
        notice.body = data.body
    if data.scope is not None:
        notice.scope = data.scope
    if data.dept is not None:
        notice.dept = data.dept
    if data.batch is not None:
        notice.batch = data.batch
    if data.expires_at is not None:
        notice.expires_at = data.expires_at
    await db.commit()
    await db.refresh(notice)
    return notice


async def publish_notice(
    db: AsyncSession,
    notice: Notice,
) -> Notice:
    if notice.status == NoticeStatus.published:
        raise ValueError("Notice is already published")
    notice.status = NoticeStatus.published
    notice.published_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(notice)
    return notice


async def get_notice(db: AsyncSession, notice_id: uuid.UUID) -> Notice | None:
    result = await db.execute(select(Notice).where(Notice.id == notice_id))
    return result.scalars().first()
