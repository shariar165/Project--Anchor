"""
Filing system business logic.

Handles complaints (academic), reports (hostel/classroom), and grievances (department).
Anonymous filings encrypt the complainant identity with Fernet so even a DB breach
does not reveal who filed.
"""
import asyncio
import base64
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.filing import (
    ClassroomReport, Filing, FilingAttachment, FilingReview,
    FilingState, FilingTemplate, SubjectResponse,
)
from app.schemas.filings import (
    ClassroomReportCreate, FilingCreate, FilingUpdate,
)

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).parent.parent.parent / "data" / "filing_uploads"

_CATEGORY_PREFIX = {
    "complaint": "CMP",
    "report": "RPT",
    "grievance": "GRV",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _upload_path(filing_id: uuid.UUID) -> Path:
    p = UPLOAD_DIR / str(filing_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _tracking_code(length: int = 12) -> str:
    """Generate a URL-safe base32 tracking code (uppercase, no padding)."""
    raw = secrets.token_bytes(length)
    return base64.b32encode(raw).decode()[:length].upper()


def _encrypt_actor(user_id: uuid.UUID) -> bytes:
    """Fernet-encrypt the user_id for anonymous filing identity protection."""
    from cryptography.fernet import Fernet
    from app.config import get_settings
    settings = get_settings()
    # Derive a 32-byte key from secret_key (Fernet needs URL-safe base64 of 32 bytes)
    raw = bytes.fromhex(settings.secret_key)[:32]
    key = base64.urlsafe_b64encode(raw)
    f = Fernet(key)
    return f.encrypt(str(user_id).encode())


# ── Templates ─────────────────────────────────────────────────────────────────

async def list_templates(db: AsyncSession) -> list[FilingTemplate]:
    result = await db.execute(
        select(FilingTemplate).where(FilingTemplate.active.is_(True)).order_by(FilingTemplate.category, FilingTemplate.key)
    )
    return list(result.scalars().all())


async def get_template_by_key(db: AsyncSession, key: str) -> FilingTemplate | None:
    result = await db.execute(
        select(FilingTemplate).where(FilingTemplate.key == key)
    )
    return result.scalars().first()


# ── Filing number generation ──────────────────────────────────────────────────

async def _next_filing_number(db: AsyncSession, category: str) -> str:
    prefix = _CATEGORY_PREFIX.get(category, "FIL")
    year = _now().year
    pattern = f"DIU-{prefix}-{year}-%"
    result = await db.execute(
        select(func.count(Filing.id)).where(
            Filing.filing_number.like(pattern)
        )
    )
    count = result.scalar() or 0
    return f"DIU-{prefix}-{year}-{count + 1:05d}"


# ── Seeding ───────────────────────────────────────────────────────────────────

_SEED_TEMPLATES = [
    # key, name, name_bn, category, anonymity_mode, routing_target, stepup, modq, proof_req, proof_hint, resp_window, esc_days
    ("academic_rank1",    "Normal feedback",                   "সাধারণ মতামত",              "complaint",  "attributed", "dept_head", False, False, False, None, 7, 7),
    ("academic_rank2",    "Professional conduct",              "পেশাদার আচরণের অভিযোগ",    "complaint",  "attributed", "dept_head", False, False, False, "Describe specific incidents with dates.", 7, 7),
    ("academic_rank3",    "Serious academic concern",          "গুরুতর শিক্ষা-সংক্রান্ত উদ্বেগ", "complaint", "anonymous", "dean",     True,  True,  False, "Attach evidence if available — your identity stays protected.", 3, 3),
    ("dept_c1",           "Incident-based grievance",          "ঘটনা-ভিত্তিক অভিযোগ",      "grievance",  "attributed", "dept_head", False, False, True,  "Attach a photo or document showing the issue.", 7, 7),
    ("dept_c2",           "Semester rating",                   "সেমিস্টার রেটিং",           "grievance",  "aggregated", "dept_head", False, False, False, None, 7, 7),
    ("dept_c3",           "Department culture",                "বিভাগীয় পরিবেশ",           "grievance",  "anonymous",  "dean",      True,  True,  False, None, 7, 7),
    ("classroom",         "Classroom condition",               "শ্রেণীকক্ষের অবস্থা",       "report",     "attributed", "dept_head", False, False, False, "A photo of the issue is helpful.", 7, 7),
    ("hall_tutor",        "Hall tutor report",                 "হল টিউটর রিপোর্ট",         "report",     "attributed", "provost",   False, False, False, None, 7, 7),
    ("hostel_incident",   "Hostel — seat/curfew/roommate",     "হোস্টেল অভিযোগ",           "report",     "attributed", "provost",   False, False, False, None, 7, 7),
    ("warden_misconduct", "Warden misconduct",                 "ওয়ার্ডেনের অসদাচরণ",       "report",     "anonymous",  "provost",   True,  True,  False, "Anonymous report — your identity will be protected.", 7, 7),
]


async def seed_templates(db: AsyncSession) -> None:
    result = await db.execute(select(func.count(FilingTemplate.id)))
    count = result.scalar() or 0
    if count > 0:
        return
    for (key, name, name_bn, category, anon, routing, stepup, modq, proof_req, proof_hint, resp_window, esc_days) in _SEED_TEMPLATES:
        tpl = FilingTemplate(
            key=key,
            name=name,
            name_bn=name_bn,
            category=category,
            anonymity_mode=anon,
            routing_target=routing,
            requires_stepup=stepup,
            goes_to_moderation_queue=modq,
            proof_required=proof_req,
            proof_hint=proof_hint,
            subject_response_window_days=resp_window,
            default_escalation_days=esc_days,
            active=True,
        )
        db.add(tpl)
    await db.commit()
    logger.info("Filing templates seeded (%d templates)", len(_SEED_TEMPLATES))


# ── Filing CRUD ───────────────────────────────────────────────────────────────

async def create_filing(
    db: AsyncSession,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
    data: FilingCreate,
) -> Filing:
    template = await get_template_by_key(db, data.template_key)
    if template is None:
        raise ValueError(f"Unknown template key: {data.template_key}")

    filing = Filing(
        tenant_id=tenant_id,
        category=template.category,
        template_id=template.id,
        complainant_user_id=user_id,
        language=data.language,
        state=FilingState.draft,
        field_values={},
    )
    db.add(filing)
    await db.commit()
    await db.refresh(filing)
    await db.refresh(filing, ["template", "attachments", "reviews", "subject_responses"])
    return filing


async def get_filing(
    db: AsyncSession,
    filing_id: uuid.UUID,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
) -> Filing | None:
    filing = await db.get(Filing, filing_id)
    if filing is None:
        return None
    # Return None (not 403) to avoid leaking existence — same pattern as applications
    if filing.complainant_user_id != user_id:
        if tenant_id is None or filing.tenant_id != tenant_id:
            return None
    await db.refresh(filing, ["template", "attachments", "reviews", "subject_responses"])
    return filing


async def get_filing_by_id_any_owner(
    db: AsyncSession,
    filing_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
) -> Filing | None:
    """Fetch filing for subject/admin — still scoped to tenant."""
    filing = await db.get(Filing, filing_id)
    if filing is None:
        return None
    if tenant_id and filing.tenant_id and filing.tenant_id != tenant_id:
        return None
    await db.refresh(filing, ["template", "attachments", "reviews", "subject_responses"])
    return filing


async def list_filings(
    db: AsyncSession,
    user_id: uuid.UUID,
    category: str | None = None,
    state: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[Filing]:
    q = select(Filing).where(Filing.complainant_user_id == user_id)
    if category:
        q = q.where(Filing.category == category)
    if state:
        q = q.where(Filing.state == state)
    q = q.order_by(Filing.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    filings = list(result.scalars().all())
    for f in filings:
        await db.refresh(f, ["template"])
    return filings


async def list_filings_admin(
    db: AsyncSession,
    tenant_id: uuid.UUID | None,
    category: str | None = None,
    state: str | None = None,
    template_key: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[Filing]:
    """List all filings for admin — not scoped to a specific complainant."""
    q = select(Filing)
    if tenant_id:
        q = q.where(Filing.tenant_id == tenant_id)
    if category:
        q = q.where(Filing.category == category)
    if state:
        q = q.where(Filing.state == state)
    if template_key:
        q = q.join(FilingTemplate, Filing.template_id == FilingTemplate.id)
        q = q.where(FilingTemplate.key == template_key)
    q = q.order_by(Filing.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    filings = list(result.scalars().all())
    for f in filings:
        await db.refresh(f, ["template"])
    return filings


async def admin_review_filing(
    db: AsyncSession,
    filing: Filing,
    reviewer_id: uuid.UUID,
    reviewer_role: str,
    action: str,
    public_note: str | None,
    internal_note: str | None,
) -> Filing:
    """Admin review action: transition state and record a review entry."""
    state_map = {
        "mark_under_review": FilingState.under_review,
        "resolve": FilingState.resolved,
        "dismiss": FilingState.dismissed,
        "escalate": FilingState.routed,
    }
    new_state = state_map.get(action)
    now = _now()
    if new_state:
        filing.state = new_state
        filing.state_entered_at = now
        if action == "escalate":
            filing.escalation_level = filing.escalation_level + 1
        if action in ("resolve", "dismiss"):
            filing.finalized_at = now
            if public_note:
                filing.final_outcome_note = public_note

    review = FilingReview(
        filing_id=filing.id,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        action=action,
        public_note=public_note,
        internal_note=internal_note,
    )
    db.add(review)
    await db.commit()
    await db.refresh(filing)
    await db.refresh(filing, ["template", "attachments", "reviews", "subject_responses"])
    return filing


async def update_filing(
    db: AsyncSession, filing: Filing, data: FilingUpdate
) -> Filing:
    if filing.state != FilingState.draft:
        raise ValueError("Filing can only be edited in draft state")
    if data.body is not None:
        filing.body = data.body
    if data.field_values is not None:
        filing.field_values = data.field_values
    if data.language is not None:
        filing.language = data.language
    await db.commit()
    # Refresh scalar columns (updated_at is server-side) then relationships
    await db.refresh(filing)
    await db.refresh(filing, ["template", "attachments", "reviews", "subject_responses"])
    return filing


async def delete_filing(db: AsyncSession, filing: Filing) -> None:
    if filing.state != FilingState.draft:
        raise ValueError("Only draft filings can be deleted")
    await db.delete(filing)
    await db.commit()


# ── Submission ────────────────────────────────────────────────────────────────

async def submit_filing(
    db: AsyncSession,
    filing: Filing,
    user_id: uuid.UUID,
) -> Filing:
    if filing.state != FilingState.draft:
        raise ValueError("Only draft filings can be submitted")

    template = filing.template
    if template is None:
        raise ValueError("Filing has no template")

    if not filing.body or len(filing.body.strip()) < 10:
        raise ValueError("Filing body is too short — please describe the issue")

    now = _now()
    filing.filing_number = await _next_filing_number(db, filing.category)
    filing.submitted_at = now
    filing.state_entered_at = now

    if template.anonymity_mode == "anonymous":
        filing.encrypted_actor_link = _encrypt_actor(user_id)
        filing.complainant_user_id = None
        filing.anonymous_tracking_code = _tracking_code()
        filing.state = FilingState.moderation_queue if template.goes_to_moderation_queue else FilingState.routed
    else:
        filing.state = FilingState.moderation_queue if template.goes_to_moderation_queue else FilingState.routed

    await db.commit()
    await db.refresh(filing)
    await db.refresh(filing, ["template", "attachments", "reviews", "subject_responses"])
    return filing


async def withdraw_filing(db: AsyncSession, filing: Filing) -> Filing:
    if filing.state not in (FilingState.draft, FilingState.moderation_queue, FilingState.routed):
        raise ValueError("Filing cannot be withdrawn in current state")
    if filing.reviews:
        raise ValueError("Cannot withdraw — a reviewer has already acted on this filing")
    filing.state = FilingState.withdrawn
    filing.finalized_at = _now()
    await db.commit()
    await db.refresh(filing)
    await db.refresh(filing, ["template", "attachments", "reviews", "subject_responses"])
    return filing


# ── Anonymous lookup ──────────────────────────────────────────────────────────

async def anonymous_lookup(db: AsyncSession, tracking_code: str) -> Filing | None:
    result = await db.execute(
        select(Filing).where(Filing.anonymous_tracking_code == tracking_code)
    )
    return result.scalars().first()


# ── Reviews ───────────────────────────────────────────────────────────────────

async def record_review(
    db: AsyncSession,
    filing: Filing,
    reviewer_id: uuid.UUID,
    reviewer_role: str,
    action: str,
    internal_note: str | None,
    public_note: str | None,
) -> FilingReview:
    review = FilingReview(
        filing_id=filing.id,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        action=action,
        internal_note=internal_note,
        public_note=public_note,
    )
    db.add(review)

    now = _now()
    filing.state_entered_at = now

    if action == "resolve":
        filing.state = FilingState.resolved
        filing.finalized_at = now
        if public_note:
            filing.final_outcome_note = public_note
    elif action == "dismiss":
        filing.state = FilingState.dismissed
        filing.finalized_at = now
        if public_note:
            filing.final_outcome_note = public_note
    elif action == "reject_spam":
        filing.state = FilingState.spam_rejected
        filing.finalized_at = now
    elif action == "route":
        filing.state = FilingState.routed
    elif action == "request_subject_response":
        filing.state = FilingState.subject_notified

    await db.commit()
    await db.refresh(filing)
    await db.refresh(filing, ["template", "attachments", "reviews", "subject_responses"])
    await db.refresh(review)
    return review


# ── Subject responses ─────────────────────────────────────────────────────────

async def create_subject_response(
    db: AsyncSession,
    filing: Filing,
    subject_user_id: uuid.UUID,
    response_text: str,
) -> SubjectResponse:
    template = filing.template
    window_days = template.subject_response_window_days if template else 7
    now = _now()
    resp = SubjectResponse(
        filing_id=filing.id,
        subject_user_id=subject_user_id,
        response_text=response_text,
        notified_at=now,
        responded_at=now,
        response_window_ends_at=now + timedelta(days=window_days),
    )
    db.add(resp)
    filing.state = FilingState.subject_responded
    filing.state_entered_at = now
    await db.commit()
    await db.refresh(resp)
    return resp


async def get_subject_response(
    db: AsyncSession, filing_id: uuid.UUID
) -> SubjectResponse | None:
    result = await db.execute(
        select(SubjectResponse).where(SubjectResponse.filing_id == filing_id)
        .order_by(SubjectResponse.notified_at.desc())
    )
    return result.scalars().first()


# ── Inbound filings (subject view) ────────────────────────────────────────────

async def list_inbound_filings(
    db: AsyncSession,
    subject_user_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
    page: int = 1,
    page_size: int = 20,
) -> list[Filing]:
    q = select(Filing).where(Filing.subject_user_id == subject_user_id)
    if tenant_id:
        q = q.where(Filing.tenant_id == tenant_id)
    q = q.order_by(Filing.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    filings = list(result.scalars().all())
    for f in filings:
        await db.refresh(f, ["template"])
    return filings


# ── Attachments ───────────────────────────────────────────────────────────────

async def save_attachment(
    db: AsyncSession,
    filing: Filing,
    filename: str,
    content: bytes,
    content_type: str,
) -> FilingAttachment:
    sha256 = hashlib.sha256(content).hexdigest()
    dest = _upload_path(filing.id) / f"{uuid.uuid4()}_{filename}"
    dest.write_bytes(content)

    attach = FilingAttachment(
        filing_id=filing.id,
        original_filename=filename,
        file_ref=str(dest),
        content_type=content_type,
        sha256_hash=sha256,
    )
    db.add(attach)
    await db.commit()
    await db.refresh(attach)
    return attach


async def delete_attachment(
    db: AsyncSession, filing: Filing, attachment_id: uuid.UUID
) -> None:
    if filing.state != FilingState.draft:
        raise ValueError("Attachments can only be removed while in draft state")
    result = await db.execute(
        select(FilingAttachment).where(
            FilingAttachment.id == attachment_id,
            FilingAttachment.filing_id == filing.id,
        )
    )
    attach = result.scalars().first()
    if attach is None:
        raise ValueError("Attachment not found")
    try:
        Path(attach.file_ref).unlink(missing_ok=True)
    except Exception:
        pass
    await db.delete(attach)
    await db.commit()


async def explain_attachment(attach: FilingAttachment, lang: str) -> dict:
    """Ask the AI pipeline to explain a proof document."""
    output_lang = "Bengali" if lang == "bn" else "English"
    filename = attach.original_filename
    doc_type_hint = "official document"
    if "medical" in filename.lower() or "certificate" in filename.lower():
        doc_type_hint = "medical certificate"
    elif "screenshot" in filename.lower():
        doc_type_hint = "screenshot"
    elif "photo" in filename.lower() or filename.lower().endswith((".jpg", ".jpeg", ".png")):
        doc_type_hint = "photo evidence"

    prompt = (
        f"A student has uploaded a file named '{filename}' as proof for a formal complaint or grievance. "
        f"It appears to be a {doc_type_hint}. "
        f"In {output_lang}, briefly explain: what type of document this is, "
        f"what it likely proves, and whether it is relevant for a complaint. "
        f"Keep it under 150 words. Add a disclaimer that this is an AI explanation only."
    )

    try:
        from app.ai.models import ChatRequest
        from app.ai import pipeline
        response = await asyncio.wait_for(
            pipeline.run(ChatRequest(query=prompt, mode="campus", lang="EN" if lang == "en" else "BN")),
            timeout=20.0,
        )
        return {
            "explanation": response.answer.strip(),
            "document_type_detected": doc_type_hint,
            "language": lang,
        }
    except Exception as e:
        logger.warning("Document explain failed: %s", e)
        return {
            "explanation": f"This appears to be a {doc_type_hint}. AI explanation unavailable — please review the document manually.",
            "document_type_detected": doc_type_hint,
            "language": lang,
        }


# ── AI drafting stub ──────────────────────────────────────────────────────────

async def generate_draft(filing: Filing) -> str:
    """Returns a structured stub until uni-complaint-drafter skill is built."""
    logger.warning("AI complaint drafting requested but uni-complaint-drafter skill not yet built")
    raise NotImplementedError("uni-complaint-drafter skill not yet available")


# ── Classroom reports ─────────────────────────────────────────────────────────

async def add_classroom_report(
    db: AsyncSession,
    tenant_id: uuid.UUID | None,
    user_id: uuid.UUID,
    data: ClassroomReportCreate,
) -> ClassroomReport:
    # Explicit check for duplicates (DB-level unique constraint may not fire for NULL tenant_id in SQLite)
    existing = await db.execute(
        select(ClassroomReport).where(
            ClassroomReport.reporter_user_id == user_id,
            ClassroomReport.classroom_ref == data.classroom_ref,
            ClassroomReport.issue_type == data.issue_type,
        )
    )
    if existing.scalars().first() is not None:
        raise ValueError("already_reported")

    report = ClassroomReport(
        tenant_id=tenant_id,
        classroom_ref=data.classroom_ref,
        issue_type=data.issue_type,
        reporter_user_id=user_id,
        notes=data.notes,
    )
    db.add(report)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ValueError("already_reported")
    await db.refresh(report)
    return report


async def get_classroom_reports_agg(
    db: AsyncSession,
    tenant_id: uuid.UUID | None,
    classroom_ref: str | None = None,
    issue_type: str | None = None,
) -> list[dict]:
    q = (
        select(
            ClassroomReport.classroom_ref,
            ClassroomReport.issue_type,
            func.count(ClassroomReport.id).label("count"),
        )
        .group_by(ClassroomReport.classroom_ref, ClassroomReport.issue_type)
        .order_by(func.count(ClassroomReport.id).desc())
    )
    if tenant_id:
        q = q.where(ClassroomReport.tenant_id == tenant_id)
    if classroom_ref:
        q = q.where(ClassroomReport.classroom_ref == classroom_ref)
    if issue_type:
        q = q.where(ClassroomReport.issue_type == issue_type)

    result = await db.execute(q)
    return [
        {"classroom_ref": row.classroom_ref, "issue_type": row.issue_type, "count": row.count}
        for row in result.all()
    ]
