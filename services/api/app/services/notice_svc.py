import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.notice import Notice, NoticeScope, NoticeStatus
from app.models.user import User, Role, AccountStatus
from app.models.application import StudentCampusSettings
from app.schemas.notices import NoticeCreate, NoticeUpdate
from app.services import notification_svc

logger = logging.getLogger(__name__)

PAGE_SIZE = 20

# Roles that receive campus-notice notifications.
_NOTICE_AUDIENCE_ROLES = (Role.student, Role.user)


async def _notice_recipients(db: AsyncSession, notice: Notice) -> list[uuid.UUID]:
    """Active users a published notice should notify, per its scope."""
    q = select(User.id).where(
        User.status == AccountStatus.active,
        User.role.in_(_NOTICE_AUDIENCE_ROLES),
    )
    if notice.tenant_id is not None:
        q = q.where(User.tenant_id == notice.tenant_id)
    if notice.scope == NoticeScope.dept and notice.dept:
        # Restrict to students whose campus settings name this department.
        q = q.join(
            StudentCampusSettings, StudentCampusSettings.user_id == User.id
        ).where(StudentCampusSettings.department == notice.dept)
    result = await db.execute(q)
    return [row[0] for row in result.all()]


async def _notify_published(db: AsyncSession, notice: Notice) -> None:
    """Best-effort fan-out of an in-app notification for a freshly published notice."""
    try:
        recipients = await _notice_recipients(db, notice)
        if not recipients:
            return
        body = (notice.body or "").strip()
        if len(body) > 160:
            body = body[:157].rstrip() + "…"
        await notification_svc.create_bulk(
            db, recipients,
            type="notice", mode="campus", tenant_id=notice.tenant_id,
            title=notice.title, body=body or "A new campus notice was published.",
            route="notices", params={"notice_id": str(notice.id)},
        )
    except Exception as exc:  # never block publishing on notification failure
        logger.warning("[notice] notification fan-out failed for %s: %s", notice.id, exc)


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
    await _notify_published(db, notice)
    return notice


async def get_notice(db: AsyncSession, notice_id: uuid.UUID) -> Notice | None:
    result = await db.execute(select(Notice).where(Notice.id == notice_id))
    return result.scalars().first()
