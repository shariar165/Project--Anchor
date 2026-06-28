"""In-app notification business logic.

Single enforcement point: `create()` / `create_bulk()` skip generating a notification
whose preference category is disabled for the recipient (see TYPE_PREF_MAP).
"""
import logging
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import (
    Notification, NotificationPreference, TYPE_PREF_MAP,
)

logger = logging.getLogger(__name__)

PAGE_SIZE = 30

_PREF_FIELDS = ("alerts", "cases", "notices", "feed", "marketing")
_PREF_DEFAULTS = {"alerts": True, "cases": True, "notices": True, "feed": True, "marketing": False}


# ── Preferences ───────────────────────────────────────────────────────────────

async def get_prefs(db: AsyncSession, user_id: uuid.UUID) -> NotificationPreference:
    """Fetch a user's prefs row, creating defaults on first access."""
    pref = await db.get(NotificationPreference, user_id)
    if pref is None:
        pref = NotificationPreference(user_id=user_id)
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
    return pref


async def set_prefs(db: AsyncSession, user_id: uuid.UUID, values: dict) -> NotificationPreference:
    pref = await get_prefs(db, user_id)
    for field in _PREF_FIELDS:
        if field in values and values[field] is not None:
            setattr(pref, field, bool(values[field]))
    await db.commit()
    await db.refresh(pref)
    return pref


async def get_channels(db: AsyncSession, user_id: uuid.UUID) -> dict:
    pref = await get_prefs(db, user_id)
    return pref.channels or {}


async def set_channels(db: AsyncSession, user_id: uuid.UUID, channels: dict) -> dict:
    pref = await get_prefs(db, user_id)
    pref.channels = channels
    await db.commit()
    await db.refresh(pref)
    return pref.channels or {}


def _pref_allows(pref: NotificationPreference | None, type_: str) -> bool:
    """Whether the recipient's prefs permit a notification of this type.

    Missing prefs row → use defaults (everything except marketing is on).
    Unknown type → always allowed (fail open; safety types must never be dropped).
    """
    category = TYPE_PREF_MAP.get(type_)
    if category is None:
        return True
    if pref is None:
        return _PREF_DEFAULTS.get(category, True)
    return bool(getattr(pref, category, True))


# ── Creation (enforced) ───────────────────────────────────────────────────────

async def create(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str = "",
    mode: str | None = None,
    tenant_id: uuid.UUID | None = None,
    route: str | None = None,
    params: dict | None = None,
    commit: bool = True,
) -> Notification | None:
    """Create one notification, honoring the recipient's preferences.

    Returns the row, or None if the recipient disabled this category.
    """
    pref = await db.get(NotificationPreference, user_id)
    if not _pref_allows(pref, type):
        return None
    notif = Notification(
        user_id=user_id, type=type, title=title, body=body or "",
        mode=mode, tenant_id=tenant_id, route=route, params=params,
    )
    db.add(notif)
    if commit:
        await db.commit()
        await db.refresh(notif)
    else:
        await db.flush()
    return notif


async def create_bulk(
    db: AsyncSession,
    user_ids: Iterable[uuid.UUID],
    *,
    type: str,
    title: str,
    body: str = "",
    mode: str | None = None,
    tenant_id: uuid.UUID | None = None,
    route: str | None = None,
    params: dict | None = None,
    commit: bool = True,
) -> int:
    """Fan-out helper. Batch-loads prefs once, inserts one row per allowed recipient.

    Returns the number of notifications created.
    """
    ids = list({uid for uid in user_ids if uid is not None})
    if not ids:
        return 0

    category = TYPE_PREF_MAP.get(type)
    disabled: set[uuid.UUID] = set()
    if category is not None:
        # Only users who explicitly turned this category OFF are excluded;
        # users with no prefs row keep the default (on, except marketing).
        rows = await db.execute(
            select(NotificationPreference.user_id).where(
                NotificationPreference.user_id.in_(ids),
                getattr(NotificationPreference, category).is_(False),
            )
        )
        disabled = {r[0] for r in rows.all()}

    created = 0
    for uid in ids:
        if uid in disabled:
            continue
        db.add(Notification(
            user_id=uid, type=type, title=title, body=body or "",
            mode=mode, tenant_id=tenant_id, route=route, params=params,
        ))
        created += 1

    if created:
        if commit:
            await db.commit()
        else:
            await db.flush()
    return created


# ── Reads / mutations ─────────────────────────────────────────────────────────

def _mode_filter(query, mode: str | None):
    """Filter to a mode plus mode-agnostic (NULL) rows."""
    if mode in ("campus", "country"):
        return query.where(
            (Notification.mode == mode) | (Notification.mode.is_(None))
        )
    return query


async def list_for_user(
    db: AsyncSession, user_id: uuid.UUID, mode: str | None = None, page: int = 1,
) -> list[Notification]:
    q = select(Notification).where(Notification.user_id == user_id)
    q = _mode_filter(q, mode)
    q = q.order_by(Notification.created_at.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    result = await db.execute(q)
    return list(result.scalars().all())


async def unread_count(db: AsyncSession, user_id: uuid.UUID, mode: str | None = None) -> int:
    q = select(func.count(Notification.id)).where(
        Notification.user_id == user_id, Notification.read_at.is_(None),
    )
    q = _mode_filter(q, mode)
    return int(await db.scalar(q) or 0)


async def mark_read(db: AsyncSession, user_id: uuid.UUID, notif_id: uuid.UUID) -> bool:
    notif = await db.get(Notification, notif_id)
    if notif is None or notif.user_id != user_id:
        return False
    if notif.read_at is None:
        notif.read_at = datetime.now(timezone.utc)
        await db.commit()
    return True


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID, mode: str | None = None) -> int:
    now = datetime.now(timezone.utc)
    q = select(Notification).where(
        Notification.user_id == user_id, Notification.read_at.is_(None),
    )
    q = _mode_filter(q, mode)
    rows = (await db.execute(q)).scalars().all()
    count = 0
    for n in rows:
        n.read_at = now
        count += 1
    if count:
        await db.commit()
    return count
