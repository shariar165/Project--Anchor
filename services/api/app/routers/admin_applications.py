"""
Admin-side Campus Application queue.

Reviewers (mentor / department_head / dean / accounts) discover and inspect the
applications waiting on their stage. The approve/reject/changes action itself
stays on POST /v1/applications/{id}/review (routers/applications.py), which
enforces stage ownership via application_svc.can_review().
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.models.user import User
from app.schemas.applications import (
    AdminApplicationListItem, ApplicationResponse,
    ApplicationStatsResponse, TimelineResponse,
)
from app.services import application_svc

router = APIRouter(prefix="/v1/admin/applications", tags=["admin-applications"])


@router.get("", response_model=list[AdminApplicationListItem])
async def list_admin_applications(
    stage: str | None = Query(None, description="mentor|department_head|dean|accounts"),
    state: str | None = Query(None),
    scope: str = Query("mine", pattern="^(mine|all)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    caller = await db.get(User, token.user_id)
    if caller is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unknown caller")
    apps = await application_svc.list_applications_admin(
        db, caller, token.tenant_id, stage=stage, state=state,
        scope=scope, page=page, page_size=page_size,
    )
    rows: list[AdminApplicationListItem] = []
    for app in apps:
        student = await db.get(User, app.student_id)
        rows.append(AdminApplicationListItem(
            id=app.id,
            student_id=app.student_id,
            student_name=student.full_name if student else None,
            state=app.state,
            language=app.language,
            current_approver_level=app.current_approver_level,
            requires_accounts_approval=(
                app.template.requires_accounts_approval if app.template else False
            ),
            round_count=app.round_count,
            template_name=app.template.name if app.template else None,
            template_key=app.template.key if app.template else None,
            created_at=app.created_at,
            updated_at=app.updated_at,
        ))
    return rows


@router.get("/stats", response_model=ApplicationStatsResponse)
async def admin_application_stats(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    caller = await db.get(User, token.user_id)
    if caller is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unknown caller")
    return await application_svc.application_stats(db, caller, token.tenant_id)


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_admin_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    app = await application_svc.get_application_any_user(db, application_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


@router.get("/{application_id}/timeline", response_model=TimelineResponse)
async def get_admin_application_timeline(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    app = await application_svc.get_application_any_user(db, application_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    return TimelineResponse(
        application_id=app.id, state=app.state,
        entries=application_svc.build_timeline(app),
    )
