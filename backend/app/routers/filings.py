"""
Filing system router — Complaints, Reports, Grievances.

Route ordering: static paths (/templates, /anonymous-lookup, /inbound, /classroom-reports)
MUST come before parameterised /{id} routes to avoid UUID matching conflicts.
"""
import uuid
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_stepup, TokenData
from app.limiter import limiter
from app.models.filing import Filing, FilingAttachment, FilingState, FilingTemplate
from app.redis import get_redis
from app.schemas.filings import (
    AnonymousLookupRequest, AnonymousLookupResponse,
    ClassroomReportAgg, ClassroomReportCreate,
    ExplainResponse, FilingCreate, FilingListItem,
    FilingResponse, FilingSubmitRequest, FilingTimelineEntry, FilingTimelineResponse,
    FilingTemplateResponse, FilingUpdate,
    SubjectRespondRequest, SubjectResponseResponse,
)
from app.services import filing_svc

router = APIRouter(tags=["filings"])

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "image/jpg",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


# ── Templates ─────────────────────────────────────────────────────────────────

@router.get("/v1/filings/templates", response_model=list[FilingTemplateResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    _token: TokenData = Depends(get_current_user),
):
    return await filing_svc.list_templates(db)


@router.get("/v1/filings/templates/{key}", response_model=FilingTemplateResponse)
async def get_template(
    key: str,
    db: AsyncSession = Depends(get_db),
    _token: TokenData = Depends(get_current_user),
):
    t = await filing_svc.get_template_by_key(db, key)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Template not found")
    return t


# ── Anonymous lookup (no auth required) ──────────────────────────────────────

@router.post("/v1/filings/anonymous-lookup", response_model=AnonymousLookupResponse)
async def anonymous_lookup(
    body: AnonymousLookupRequest,
    db: AsyncSession = Depends(get_db),
):
    filing = await filing_svc.anonymous_lookup(db, body.tracking_code)
    if filing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tracking code not found")
    return AnonymousLookupResponse(
        filing_number=filing.filing_number or "",
        state=filing.state,
        final_outcome_note=filing.final_outcome_note,
    )


# ── Inbound filings (where I am the subject) ─────────────────────────────────

@router.get("/v1/filings/inbound", response_model=list[FilingListItem])
async def list_inbound(
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    filings = await filing_svc.list_inbound_filings(db, token.user_id, token.tenant_id, page=page)
    return filings


@router.get("/v1/filings/inbound/{filing_id}", response_model=FilingResponse)
async def get_inbound_filing(
    filing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    filing = await filing_svc.get_filing_by_id_any_owner(db, filing_id, token.tenant_id)
    if filing is None or filing.subject_user_id != token.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Filing not found")
    # Strip complainant identity before returning
    return _strip_complainant(filing)


@router.post("/v1/filings/inbound/{filing_id}/respond", response_model=SubjectResponseResponse)
async def respond_to_filing(
    filing_id: uuid.UUID,
    body: SubjectRespondRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    filing = await filing_svc.get_filing_by_id_any_owner(db, filing_id, token.tenant_id)
    if filing is None or filing.subject_user_id != token.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Filing not found")
    if filing.state not in (FilingState.subject_notified, FilingState.routed):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Response window is not open")
    resp = await filing_svc.create_subject_response(db, filing, token.user_id, body.response_text)
    return resp


# ── Classroom reports ─────────────────────────────────────────────────────────

@router.get("/v1/classroom-reports", response_model=list[ClassroomReportAgg])
async def get_classroom_reports(
    classroom_ref: str | None = Query(default=None),
    issue_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    rows = await filing_svc.get_classroom_reports_agg(
        db, token.tenant_id, classroom_ref=classroom_ref, issue_type=issue_type
    )
    return rows


@router.post("/v1/classroom-reports", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_classroom_report(
    request: Request,
    body: ClassroomReportCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    try:
        report = await filing_svc.add_classroom_report(db, token.tenant_id, token.user_id, body)
    except ValueError as e:
        if str(e) == "already_reported":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="You have already reported this issue for this classroom",
            )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"id": str(report.id), "classroom_ref": report.classroom_ref, "issue_type": report.issue_type}


# ── Filing CRUD ───────────────────────────────────────────────────────────────

@router.get("/v1/filings", response_model=list[FilingListItem])
async def list_filings(
    category: str | None = Query(default=None),
    state: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    filings = await filing_svc.list_filings(
        db, token.user_id, category=category, state=state, page=page
    )
    return filings


@router.post("/v1/filings", response_model=FilingResponse, status_code=status.HTTP_201_CREATED)
async def create_filing(
    body: FilingCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    try:
        filing = await filing_svc.create_filing(db, token.user_id, token.tenant_id, body)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    return filing


@router.get("/v1/filings/{filing_id}", response_model=FilingResponse)
async def get_filing(
    filing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    filing = await filing_svc.get_filing(db, filing_id, token.user_id, token.tenant_id)
    if filing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Filing not found")
    return filing


@router.patch("/v1/filings/{filing_id}", response_model=FilingResponse)
async def update_filing(
    filing_id: uuid.UUID,
    body: FilingUpdate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    filing = await filing_svc.get_filing(db, filing_id, token.user_id, token.tenant_id)
    if filing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Filing not found")
    try:
        filing = await filing_svc.update_filing(db, filing, body)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    return filing


@router.delete("/v1/filings/{filing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_filing(
    filing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    filing = await filing_svc.get_filing(db, filing_id, token.user_id, token.tenant_id)
    if filing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Filing not found")
    try:
        await filing_svc.delete_filing(db, filing)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


# ── Attachments ───────────────────────────────────────────────────────────────

@router.post("/v1/filings/{filing_id}/attachments")
async def upload_attachment(
    filing_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    filing = await filing_svc.get_filing(db, filing_id, token.user_id, token.tenant_id)
    if filing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Filing not found")
    if filing.state != FilingState.draft:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Attachments can only be added to draft filings")
    if len(filing.attachments) >= 5:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Maximum 5 attachments per filing")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File type not allowed")

    content = await file.read()
    if len(content) > MAX_ATTACHMENT_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 10 MB limit")

    attach = await filing_svc.save_attachment(db, filing, file.filename or "upload", content, file.content_type)
    return {"id": str(attach.id), "original_filename": attach.original_filename, "sha256_hash": attach.sha256_hash}


@router.post("/v1/filings/{filing_id}/attachments/{attachment_id}/explain", response_model=ExplainResponse)
async def explain_attachment(
    filing_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    from sqlalchemy import select as sa_select
    filing = await filing_svc.get_filing(db, filing_id, token.user_id, token.tenant_id)
    if filing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Filing not found")

    result = await db.execute(
        sa_select(FilingAttachment).where(
            FilingAttachment.id == attachment_id,
            FilingAttachment.filing_id == filing_id,
        )
    )
    attach = result.scalars().first()
    if attach is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    if attach.explain_cache:
        import json as _json
        try:
            cached = _json.loads(attach.explain_cache)
            return ExplainResponse(**cached)
        except Exception:
            pass

    result_dict = await filing_svc.explain_attachment(attach, filing.language)
    attach.explain_cache = json.dumps(result_dict)
    await db.commit()
    return ExplainResponse(**result_dict)


@router.delete("/v1/filings/{filing_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    filing_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    filing = await filing_svc.get_filing(db, filing_id, token.user_id, token.tenant_id)
    if filing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Filing not found")
    try:
        await filing_svc.delete_attachment(db, filing, attachment_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


# ── Submit & lifecycle ────────────────────────────────────────────────────────

@router.post("/v1/filings/{filing_id}/submit", response_model=FilingResponse)
@limiter.limit("30/minute")
async def submit_filing(
    request: Request,
    filing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
    redis=Depends(get_redis),
):
    filing = await filing_svc.get_filing(db, filing_id, token.user_id, token.tenant_id)
    if filing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Filing not found")

    try:
        filing = await filing_svc.submit_filing(db, filing, token.user_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    return filing


@router.post("/v1/filings/{filing_id}/withdraw", response_model=FilingResponse)
async def withdraw_filing(
    filing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    filing = await filing_svc.get_filing(db, filing_id, token.user_id, token.tenant_id)
    if filing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Filing not found")
    try:
        filing = await filing_svc.withdraw_filing(db, filing)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    return filing


# ── Timeline ──────────────────────────────────────────────────────────────────

@router.get("/v1/filings/{filing_id}/timeline", response_model=FilingTimelineResponse)
async def get_timeline(
    filing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    filing = await filing_svc.get_filing(db, filing_id, token.user_id, token.tenant_id)
    if filing is None:
        # Also check inbound for subject
        filing = await filing_svc.get_filing_by_id_any_owner(db, filing_id, token.tenant_id)
        if filing is None or filing.subject_user_id != token.user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Filing not found")

    entries: list[FilingTimelineEntry] = []
    if filing.submitted_at:
        entries.append(FilingTimelineEntry(
            event="submitted", actor_role=None, note="Filing submitted", timestamp=filing.submitted_at
        ))
    for review in filing.reviews:
        entries.append(FilingTimelineEntry(
            event=review.action,
            actor_role=review.reviewer_role,
            note=review.public_note,
            timestamp=review.reviewed_at,
        ))
    if filing.subject_responses:
        for sr in filing.subject_responses:
            if sr.responded_at:
                entries.append(FilingTimelineEntry(
                    event="subject_responded",
                    actor_role="subject",
                    note=None,
                    timestamp=sr.responded_at,
                ))

    entries.sort(key=lambda e: e.timestamp)

    return FilingTimelineResponse(
        filing_id=filing.id,
        state=filing.state,
        entries=entries,
    )


# ── Subject response view (complainant reads subject's response) ───────────────

@router.get("/v1/filings/{filing_id}/subject-response", response_model=SubjectResponseResponse | None)
async def get_subject_response(
    filing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    filing = await filing_svc.get_filing(db, filing_id, token.user_id, token.tenant_id)
    if filing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Filing not found")
    resp = await filing_svc.get_subject_response(db, filing_id)
    return resp


# ── AI draft stub ─────────────────────────────────────────────────────────────

@router.post("/v1/filings/{filing_id}/draft-with-ai")
async def draft_with_ai(
    filing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        detail="AI drafting (uni-complaint-drafter skill) is not yet available. Please draft manually.",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_complainant(filing: Filing) -> Filing:
    """Remove complainant identity fields before returning to a subject."""
    filing.complainant_user_id = None
    filing.encrypted_actor_link = None
    filing.anonymous_tracking_code = None
    return filing
