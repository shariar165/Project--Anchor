"""
Campus Application System router.

Route ordering: static paths (/templates, /me) before parameterised /{id} routes.
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, TokenData
from app.limiter import limiter
from app.models.application import Application, ApplicationAttachment, ApplicationState, ApplicationTemplate
from app.models.user import User
from app.redis import get_redis
from app.schemas.applications import (
    AIDraftRequest, AIDraftResponse, ApplicationCreate, ApplicationListItem,
    ApplicationResponse, ApplicationUpdate, AttachmentResponse,
    AvailableMentorItem, CampusSettingsResponse, CampusSettingsPatch,
    ExplainResponse, ReviewRequest, SubmitRequest,
    TimelineEntry, TimelineResponse,
)
from app.services import application_svc

router = APIRouter(tags=["applications"])

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "image/jpg",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


# ── Templates (static, must come before /{id}) ───────────────────────────────

@router.get("/v1/applications/templates")
async def list_templates(
    db: AsyncSession = Depends(get_db),
    _token: TokenData = Depends(get_current_user),
):
    templates = await application_svc.list_templates(db)
    return templates


@router.get("/v1/applications/templates/{key}")
async def get_template_by_key(
    key: str,
    db: AsyncSession = Depends(get_db),
    _token: TokenData = Depends(get_current_user),
):
    t = await application_svc.get_template_by_key(db, key)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Template not found")
    return t


# ── Student settings (static, must come before /{id}) ────────────────────────

@router.get("/v1/students/me/campus-settings", response_model=CampusSettingsResponse)
async def get_campus_settings(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    settings = await application_svc.get_or_create_settings(db, token.user_id)
    mentor_name = None
    if settings.mentor_user_id:
        mentor = await db.get(User, settings.mentor_user_id)
        if mentor:
            mentor_name = mentor.full_name
    return CampusSettingsResponse(
        user_id=settings.user_id,
        department=settings.department,
        mentor_user_id=settings.mentor_user_id,
        mentor_name=mentor_name,
        department_locked=settings.department_locked,
        updated_at=settings.updated_at,
    )


@router.patch("/v1/students/me/campus-settings", response_model=CampusSettingsResponse)
async def update_campus_settings(
    body: CampusSettingsPatch,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    settings = await application_svc.get_or_create_settings(db, token.user_id)
    mentor_user_id = ... if body.mentor_user_id is None and "mentor_user_id" not in body.model_fields_set else body.mentor_user_id
    department = ... if body.department is None and "department" not in body.model_fields_set else body.department

    if body.mentor_user_id is not None:
        # Validate mentor exists
        mentor = await db.get(User, body.mentor_user_id)
        if mentor is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mentor not found")

    settings = await application_svc.update_settings(
        db, settings,
        mentor_user_id=body.mentor_user_id if "mentor_user_id" in body.model_fields_set else ...,
        department=body.department if "department" in body.model_fields_set else ...,
    )
    mentor_name = None
    if settings.mentor_user_id:
        mentor = await db.get(User, settings.mentor_user_id)
        if mentor:
            mentor_name = mentor.full_name
    return CampusSettingsResponse(
        user_id=settings.user_id,
        department=settings.department,
        mentor_user_id=settings.mentor_user_id,
        mentor_name=mentor_name,
        department_locked=settings.department_locked,
        updated_at=settings.updated_at,
    )


@router.get("/v1/students/me/available-mentors")
async def get_available_mentors(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    mentors = await application_svc.get_available_mentors(db, token.tenant_id)
    return [
        AvailableMentorItem(
            user_id=m.id,
            full_name=m.full_name,
            email=m.email,
        )
        for m in mentors
    ]


# ── Application list + create ─────────────────────────────────────────────────

@router.get("/v1/applications", response_model=list[ApplicationListItem])
async def list_applications(
    state: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    apps = await application_svc.list_applications(db, token.user_id, state, page, page_size)
    return apps


@router.post("/v1/applications", response_model=ApplicationResponse, status_code=201)
@limiter.limit("30/minute")
async def create_application(
    request: Request,
    body: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    # Validate template exists
    template = await application_svc.get_template(db, body.template_id)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Template not found")
    app = await application_svc.create_application(db, token.user_id, token.tenant_id, body)
    return app


# ── Single application endpoints ──────────────────────────────────────────────

@router.get("/v1/applications/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    app = await application_svc.get_application(db, application_id, token.user_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


@router.patch("/v1/applications/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: uuid.UUID,
    body: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    app = await application_svc.get_application(db, application_id, token.user_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    try:
        app = await application_svc.update_application(db, app, body)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    return app


@router.delete("/v1/applications/{application_id}", status_code=204)
async def delete_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    app = await application_svc.get_application(db, application_id, token.user_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    try:
        await application_svc.delete_application(db, app)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


# ── AI Drafting ───────────────────────────────────────────────────────────────

@router.post("/v1/applications/{application_id}/draft-with-ai", response_model=AIDraftResponse)
@limiter.limit("10/minute")
async def draft_with_ai(
    request: Request,
    application_id: uuid.UUID,
    body: AIDraftRequest | None = None,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    app = await application_svc.get_application(db, application_id, token.user_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    if app.state not in (ApplicationState.draft, ApplicationState.changes_requested):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Cannot redraft in current state")

    if body and body.language:
        app.language = body.language

    # Get student name from DB
    student = await db.get(User, token.user_id)
    student_name = student.full_name if student else "Student"

    letter_body = await application_svc.generate_draft(app, student_name)
    app.letter_body = letter_body
    await db.commit()

    return AIDraftResponse(letter_body=letter_body, generated_at=datetime.now(timezone.utc))


# ── Attachments ───────────────────────────────────────────────────────────────

@router.post("/v1/applications/{application_id}/attachments", response_model=AttachmentResponse, status_code=201)
async def upload_attachment(
    application_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    app = await application_svc.get_application(db, application_id, token.user_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    if app.state not in (ApplicationState.draft, ApplicationState.changes_requested):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Cannot add attachments in current state")
    if len(app.attachments) >= 5:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Maximum 5 attachments per application")

    content = await file.read()
    if len(content) > MAX_ATTACHMENT_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 10 MB limit")

    attach = await application_svc.save_attachment(
        db, app, file.filename or "upload", content, file.content_type or "application/octet-stream"
    )
    return attach


@router.post("/v1/applications/{application_id}/attachments/{attachment_id}/explain", response_model=ExplainResponse)
@limiter.limit("10/minute")
async def explain_attachment(
    request: Request,
    application_id: uuid.UUID,
    attachment_id: uuid.UUID,
    lang: str = Query("en"),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    app = await application_svc.get_application(db, application_id, token.user_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")

    result = await db.execute(
        select(ApplicationAttachment).where(
            ApplicationAttachment.id == attachment_id,
            ApplicationAttachment.application_id == application_id,
        )
    )
    attach = result.scalars().first()
    if attach is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    explanation = await application_svc.explain_attachment(attach, lang)
    attach.explain_cache = explanation["explanation"]
    await db.commit()
    return explanation


@router.delete("/v1/applications/{application_id}/attachments/{attachment_id}", status_code=204)
async def delete_attachment(
    application_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    app = await application_svc.get_application(db, application_id, token.user_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    try:
        await application_svc.delete_attachment(db, app, attachment_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


# ── Submission lifecycle ──────────────────────────────────────────────────────

@router.post("/v1/applications/{application_id}/submit", response_model=ApplicationResponse)
async def submit_application(
    application_id: uuid.UUID,
    body: SubmitRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    app = await application_svc.get_application(db, application_id, token.user_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    settings = await application_svc.get_or_create_settings(db, token.user_id)
    try:
        app = await application_svc.submit_application(db, app, body.first_approver_choice, settings)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return app


@router.post("/v1/applications/{application_id}/resubmit", response_model=ApplicationResponse)
async def resubmit_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    app = await application_svc.get_application(db, application_id, token.user_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    try:
        app = await application_svc.resubmit_application(db, app)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    return app


@router.post("/v1/applications/{application_id}/withdraw", response_model=ApplicationResponse)
async def withdraw_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    app = await application_svc.get_application(db, application_id, token.user_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    try:
        app = await application_svc.withdraw_application(db, app)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    return app


@router.post("/v1/applications/{application_id}/review", response_model=ApplicationResponse)
async def review_application(
    application_id: uuid.UUID,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    """Approver action — restricted to the staff member who owns the current stage."""
    if token.role not in ("admin", "moderator", "super_admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Reviewer role required")
    app = await application_svc.get_application_any_user(db, application_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    if app.state not in (ApplicationState.in_review,):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Application is not in review state")
    caller = await db.get(User, token.user_id)
    if caller is None or not application_svc.can_review(caller, app):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="You are not the assigned approver for this application's current stage",
        )
    await application_svc.record_review(db, app, token.user_id, body)
    await db.refresh(app, ["template", "attachments", "reviews"])
    return app


# ── Timeline ──────────────────────────────────────────────────────────────────

@router.get("/v1/applications/{application_id}/timeline", response_model=TimelineResponse)
async def get_timeline(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    app = await application_svc.get_application(db, application_id, token.user_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")

    return TimelineResponse(
        application_id=app.id, state=app.state,
        entries=application_svc.build_timeline(app),
    )


# ── SSE stream ────────────────────────────────────────────────────────────────

@router.get("/v1/applications/{application_id}/stream")
async def stream_application(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    """Server-Sent Events stream for real-time application status updates."""
    app = await application_svc.get_application(db, application_id, token.user_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")

    async def event_generator():
        from app.database import AsyncSessionLocal
        last_state = None
        last_updated = None
        for _ in range(100):  # max ~5 min at 3s intervals
            try:
                async with AsyncSessionLocal() as session:
                    current = await session.get(Application, application_id)
                    if current is None:
                        break
                    if current.state != last_state or current.updated_at != last_updated:
                        last_state = current.state
                        last_updated = current.updated_at
                        payload = json.dumps({
                            "state": current.state,
                            "current_approver_level": current.current_approver_level,
                            "updated_at": current.updated_at.isoformat(),
                        })
                        yield f"data: {payload}\n\n"
                    if current.state in (
                        ApplicationState.approved, ApplicationState.rejected, ApplicationState.withdrawn
                    ):
                        break
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                break
            await asyncio.sleep(3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── PDF Download ──────────────────────────────────────────────────────────────

@router.get("/v1/applications/{application_id}/pdf")
async def download_pdf(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    app = await application_svc.get_application(db, application_id, token.user_id, token.tenant_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    if app.state != ApplicationState.approved:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="PDF only available for approved applications")

    if app.pdf_ref is None:
        # Generate on demand if background task hasn't completed yet
        from pathlib import Path
        pdf_bytes = application_svc._build_pdf(app)
        pdf_path = application_svc._upload_path(application_id) / "signed_application.pdf"
        pdf_path.write_bytes(pdf_bytes)
        app.pdf_ref = str(pdf_path)
        await db.commit()

    from pathlib import Path
    pdf_path = Path(app.pdf_ref)
    if not pdf_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="PDF not yet generated, please try again shortly")

    short_id = str(application_id)[:8].upper()
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"DIU-APP-{short_id}.pdf",
    )
