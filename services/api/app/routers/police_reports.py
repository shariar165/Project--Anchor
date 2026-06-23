"""
Police report (GD / FIR) drafting router — national mode.

Route ordering: literal paths (/draft-with-ai) MUST be registered before the
parameterised /{report_id} routes to avoid UUID matching conflicts.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, TokenData
from app.limiter import limiter
from app.schemas.police_reports import (
    AiDraftRequest, AiDraftResponse,
    PoliceReportCreate, PoliceReportListItem, PoliceReportResponse, PoliceReportUpdate,
)
from app.services import export_svc, police_report_svc

router = APIRouter(prefix="/v1/police-reports", tags=["police-reports"])

_TYPE_LABEL = {"gd": "General Diary", "fir": "First Information Report"}


@router.get("", response_model=list[PoliceReportListItem])
async def list_my_reports(
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    return await police_report_svc.list_reports(db, token.user_id, page=page)


@router.post("", response_model=PoliceReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    body: PoliceReportCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    return await police_report_svc.create_report(db, token.user_id, body)


@router.post("/draft-with-ai", response_model=AiDraftResponse)
@limiter.limit("20/minute")
async def draft_with_ai(
    request: Request,
    body: AiDraftRequest,
    _token: TokenData = Depends(get_current_user),
):
    return await police_report_svc.generate_ai_draft(body)


@router.get("/{report_id}", response_model=PoliceReportResponse)
async def get_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    report = await police_report_svc.get_report(db, report_id, token.user_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.patch("/{report_id}", response_model=PoliceReportResponse)
async def update_report(
    report_id: uuid.UUID,
    body: PoliceReportUpdate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    report = await police_report_svc.get_report(db, report_id, token.user_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Report not found")
    try:
        return await police_report_svc.update_report(db, report, body)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    report = await police_report_svc.get_report(db, report_id, token.user_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Report not found")
    await police_report_svc.delete_report(db, report)


@router.post("/{report_id}/finalize", response_model=PoliceReportResponse)
async def finalize_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    report = await police_report_svc.get_report(db, report_id, token.user_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Report not found")
    try:
        return await police_report_svc.finalize_report(db, report)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{report_id}/mark-filed", response_model=PoliceReportResponse)
async def mark_filed(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    report = await police_report_svc.get_report(db, report_id, token.user_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Report not found")
    try:
        return await police_report_svc.mark_filed(db, report)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{report_id}/export")
async def export_report(
    report_id: uuid.UUID,
    format: str = Query(default="pdf"),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    """Download the report as a print-ready PDF / DOCX / CSV to take to the thana."""
    report = await police_report_svc.get_report(db, report_id, token.user_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Report not found")

    title = _TYPE_LABEL.get(report.report_type, "General Diary")
    meta = [
        ("Reference", report.reference_no or "Draft (not finalized)"),
        ("Type", title),
    ]
    if report.thana:
        meta.append(("To the Officer-in-Charge", report.thana))
    if report.district:
        meta.append(("District", report.district))
    if report.subject:
        meta.append(("Subject", report.subject))
    if report.complainant_name:
        meta.append(("Complainant", report.complainant_name))
    if report.guardian_name:
        meta.append(("Guardian", report.guardian_name))
    if report.address:
        meta.append(("Address", report.address))
    if report.phone:
        meta.append(("Phone", report.phone))
    if report.nid:
        meta.append(("NID", report.nid))
    if report.incident_datetime:
        meta.append(("Date / time of incident", report.incident_datetime))
    if report.location:
        meta.append(("Location", report.location))
    if report.property_details:
        meta.append(("Property / details", report.property_details))
    if report.accused_details:
        meta.append(("Accused / suspect", report.accused_details))
    if report.witnesses:
        meta.append(("Witnesses", report.witnesses))

    doc = export_svc.ExportDoc(
        title=title,
        subtitle="Bangladesh Police — drafted via Anchor AI. Review, sign, and submit at the thana.",
        meta=meta,
        body=report.narrative or "",
    )
    stem = report.reference_no or f"{report.report_type}-{str(report.id)[:8]}"
    return export_svc.export_response(doc, format, stem)
