"""
Police report (GD / FIR) drafting service — national mode.

Owner-scoped CRUD plus an AI-assisted drafting helper that prefers the internal
RAG service and falls back to a deterministic formal-letter template when RAG is
unreachable (it runs on the user's PC via ngrok and is frequently offline).
"""
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.police_report import PoliceReport
from app.schemas.police_reports import (
    AiDraftRequest, AiDraftResponse, PoliceReportCreate, PoliceReportUpdate,
)
from app.services.rag_proxy import rag_url, rag_headers

logger = logging.getLogger(__name__)

PAGE_SIZE = 20

_TYPE_LABEL = {"gd": "General Diary", "fir": "First Information Report"}


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def create_report(
    db: AsyncSession, user_id: uuid.UUID, body: PoliceReportCreate
) -> PoliceReport:
    report = PoliceReport(
        user_id=user_id,
        report_type=body.report_type,
        language=body.language,
        state="draft",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def get_report(
    db: AsyncSession, report_id: uuid.UUID, user_id: uuid.UUID
) -> PoliceReport | None:
    result = await db.execute(
        select(PoliceReport).where(
            PoliceReport.id == report_id, PoliceReport.user_id == user_id
        )
    )
    return result.scalars().first()


async def list_reports(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1
) -> list[PoliceReport]:
    result = await db.execute(
        select(PoliceReport)
        .where(PoliceReport.user_id == user_id)
        .order_by(PoliceReport.updated_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    return list(result.scalars().all())


async def update_report(
    db: AsyncSession, report: PoliceReport, body: PoliceReportUpdate
) -> PoliceReport:
    if report.state != "draft":
        raise ValueError("Only draft reports can be edited")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(report, field, value)
    await db.commit()
    await db.refresh(report)
    return report


async def delete_report(db: AsyncSession, report: PoliceReport) -> None:
    await db.delete(report)
    await db.commit()


# ── Lifecycle ─────────────────────────────────────────────────────────────────

async def _next_reference_no(db: AsyncSession, report_type: str) -> str:
    """Generate a human-readable reference like GD-2026-0042 / FIR-2026-0042.

    Sequence is per-type per-year, derived from the count of already-finalized
    reports so numbers stay stable and monotonic enough for a demo.
    """
    year = datetime.now(tz=timezone.utc).year
    prefix = report_type.upper()
    count = (await db.execute(
        select(func.count()).select_from(PoliceReport).where(
            PoliceReport.report_type == report_type,
            PoliceReport.reference_no.is_not(None),
        )
    )).scalar() or 0
    return f"{prefix}-{year}-{count + 1:04d}"


async def finalize_report(db: AsyncSession, report: PoliceReport) -> PoliceReport:
    if report.state == "filed_by_user":
        raise ValueError("This report is already marked as filed")
    missing = [
        label for value, label in (
            (report.complainant_name, "complainant name"),
            (report.subject, "subject"),
            (report.narrative, "statement / narrative"),
            (report.thana, "police station (thana)"),
        ) if not (value or "").strip()
    ]
    if missing:
        raise ValueError("Please complete: " + ", ".join(missing))

    if not report.reference_no:
        report.reference_no = await _next_reference_no(db, report.report_type)
    report.state = "finalized"
    report.finalized_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(report)
    return report


async def mark_filed(db: AsyncSession, report: PoliceReport) -> PoliceReport:
    if report.state == "draft":
        raise ValueError("Finalize the report before marking it as filed")
    report.state = "filed_by_user"
    await db.commit()
    await db.refresh(report)
    return report


# ── AI-assisted drafting ──────────────────────────────────────────────────────

async def generate_ai_draft(body: AiDraftRequest) -> AiDraftResponse:
    """Produce a formal GD/FIR draft. Tries the RAG service first; on any failure
    falls back to a deterministic template so the feature always works."""
    rag = await _try_rag_draft(body)
    if rag is not None:
        return rag
    subject, narrative = _template_draft(body)
    return AiDraftResponse(
        subject=subject,
        narrative=narrative,
        ai_assisted=False,
        notice="Drafted offline from a standard template — the AI service was unavailable. Review and edit before finalizing.",
    )


async def _try_rag_draft(body: AiDraftRequest) -> AiDraftResponse | None:
    type_label = _TYPE_LABEL.get(body.report_type, "General Diary")
    instruction = (
        f"You are drafting a formal {type_label} statement for a Bangladesh police station. "
        "Write a clear, factual, first-person narrative suitable to submit to the Officer-in-Charge. "
        "Use only the facts provided; do not invent names, dates, or case numbers. "
        "Keep it respectful and concise (2-4 short paragraphs). Return only the statement body.\n\n"
        f"Incident description: {body.situation}"
    )
    if body.location:
        instruction += f"\nLocation: {body.location}"
    if body.incident_datetime:
        instruction += f"\nWhen: {body.incident_datetime}"

    payload = {"query": instruction, "mode": "national", "lang": body.language}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{rag_url()}/chat", json=payload, headers=rag_headers()
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # ConnectError, timeout, HTTP error, bad JSON
        logger.info("RAG draft unavailable, using template fallback: %s", e)
        return None

    narrative = (data.get("answer") or "").strip()
    if len(narrative) < 40:
        return None  # stub/empty answer — prefer the template
    subject = _default_subject(body)
    return AiDraftResponse(subject=subject, narrative=narrative, ai_assisted=True)


def _default_subject(body: AiDraftRequest) -> str:
    label = _TYPE_LABEL.get(body.report_type, "General Diary")
    itype = (body.incident_type or "").replace("_", " ").strip()
    where = f" at {body.location}" if body.location else ""
    if itype:
        return f"{label} — {itype}{where}".strip()
    return f"{label} — incident report{where}".strip()


def _template_draft(body: AiDraftRequest) -> tuple[str, str]:
    """Deterministic formal narrative built from the supplied facts."""
    name = (body.complainant_name or "the undersigned").strip()
    when = (body.incident_datetime or "the date mentioned below").strip()
    where = (body.location or "the location described").strip()
    type_label = _TYPE_LABEL.get(body.report_type, "General Diary")

    paras = [
        f"I, {name}, wish to report the following matter for record.",
        (
            f"On {when}, at {where}, the following incident took place: "
            f"{body.situation.strip()}"
        ),
        (
            f"I respectfully request that this matter be entered as a {type_label} "
            "and that appropriate action be taken. The facts stated above are true "
            "to the best of my knowledge."
        ),
    ]
    return _default_subject(body), "\n\n".join(paras)
