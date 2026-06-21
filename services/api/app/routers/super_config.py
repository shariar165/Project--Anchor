"""Super-admin platform configuration.

Routes: /v1/super-admin/config
Auth: super_admin role only.

Stores platform-wide policy values (escalation timers, rate limits, trust
thresholds, ban durations, AI confidence thresholds, legal disclaimer,
retention, PDP Ordinance toggles) as one PlatformConfig row per section.
Values are stored & served here; runtime enforcement is a separate concern.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.limiter import limiter
from app.models.platform_config import PlatformConfig
from app.schemas.platform_config import ConfigUpdate, merged_config
from app.services.audit import log_event as audit_log
from app.services.device import get_ip

router = APIRouter(prefix="/v1/super-admin/config", tags=["super-admin-config"])


async def _load_stored(db: AsyncSession) -> dict:
    result = await db.execute(select(PlatformConfig))
    return {row.key: (row.value or {}) for row in result.scalars().all()}


@router.get("")
@limiter.limit("120/minute")
async def get_config(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Return the full platform config: stored sections merged over defaults."""
    return merged_config(await _load_stored(db))


@router.patch("")
@limiter.limit("30/minute")
async def update_config(
    body: ConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Upsert the provided config sections. Sections omitted are left untouched."""
    if not body.sections:
        return merged_config(await _load_stored(db))

    existing = {
        row.key: row
        for row in (await db.execute(select(PlatformConfig))).scalars().all()
    }
    for key, value in body.sections.items():
        row = existing.get(key)
        if row is None:
            db.add(PlatformConfig(key=key, value=value, updated_by_id=token.user_id))
        else:
            row.value = value
            row.updated_by_id = token.user_id

    await audit_log(db, "platform_config_updated", token.user_id, get_ip(request), {
        "sections": sorted(body.sections.keys()),
    })
    await db.commit()
    return merged_config(await _load_stored(db))
