import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, TokenData
from app.services import notification_svc
from app.schemas.notifications import (
    NotificationResponse, NotificationListResponse, UnreadCountResponse,
    NotificationPrefs, NotificationPrefsUpdate,
)

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


def _mode_param(mode: str | None) -> str | None:
    return mode if mode in ("campus", "country") else None


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    mode: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    m = _mode_param(mode)
    items = await notification_svc.list_for_user(db, token.user_id, mode=m, page=page)
    unread = await notification_svc.unread_count(db, token.user_id, mode=m)
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        unread_count=unread,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    mode: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    unread = await notification_svc.unread_count(db, token.user_id, mode=_mode_param(mode))
    return UnreadCountResponse(unread_count=unread)


# Preferences — registered before /{id} routes to avoid path capture.
@router.get("/preferences", response_model=NotificationPrefs)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    pref = await notification_svc.get_prefs(db, token.user_id)
    return NotificationPrefs.model_validate(pref)


@router.put("/preferences", response_model=NotificationPrefs)
async def update_preferences(
    body: NotificationPrefsUpdate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    pref = await notification_svc.set_prefs(
        db, token.user_id, body.model_dump(exclude_unset=True)
    )
    return NotificationPrefs.model_validate(pref)


@router.post("/read-all")
async def mark_all_read(
    mode: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    count = await notification_svc.mark_all_read(db, token.user_id, mode=_mode_param(mode))
    return {"marked_read": count}


@router.post("/{notif_id}/read")
async def mark_read(
    notif_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    ok = await notification_svc.mark_read(db, token.user_id, notif_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return {"ok": True}
