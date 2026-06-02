"""
Application system business logic.

Approval chain: first-approver (mentor|department_head) → dean → accounts (if required) → approved
"""
import asyncio
import hashlib
import io
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import (
    Application, ApplicationAttachment, ApplicationReview,
    ApplicationState, ApplicationTemplate, StudentCampusSettings,
)
from app.models.user import User, Role
from app.schemas.applications import (
    ApplicationCreate, ApplicationUpdate, ReviewRequest,
)

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).parent.parent.parent / "data" / "uploads"

# mentor/dept_head → dean → accounts → final
_NEXT_LEVEL: dict[str, str] = {
    "mentor": "dean",
    "department_head": "dean",
    "dean": "accounts",
    "accounts": "",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _upload_path(application_id: uuid.UUID) -> Path:
    p = UPLOAD_DIR / str(application_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Templates ─────────────────────────────────────────────────────────────────

async def list_templates(db: AsyncSession) -> list[ApplicationTemplate]:
    result = await db.execute(
        select(ApplicationTemplate).where(ApplicationTemplate.active.is_(True))
    )
    return list(result.scalars().all())


async def get_template(db: AsyncSession, template_id: uuid.UUID) -> ApplicationTemplate | None:
    return await db.get(ApplicationTemplate, template_id)


async def get_template_by_key(db: AsyncSession, key: str) -> ApplicationTemplate | None:
    result = await db.execute(
        select(ApplicationTemplate).where(ApplicationTemplate.key == key)
    )
    return result.scalars().first()


# ── Application CRUD ──────────────────────────────────────────────────────────

async def create_application(
    db: AsyncSession,
    student_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
    data: ApplicationCreate,
) -> Application:
    app = Application(
        student_id=student_id,
        tenant_id=tenant_id,
        template_id=data.template_id,
        field_values=data.field_values,
        language=data.language,
        state=ApplicationState.draft,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    await db.refresh(app, ["template", "attachments", "reviews"])
    return app


async def get_application(
    db: AsyncSession,
    application_id: uuid.UUID,
    student_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
) -> Application | None:
    app = await db.get(Application, application_id)
    if app is None:
        return None
    # Cross-tenant guard — return None (404) rather than 403 to avoid leaking existence
    if app.student_id != student_id:
        if tenant_id is None or app.tenant_id != tenant_id:
            return None
    await db.refresh(app, ["template", "attachments", "reviews"])
    return app


async def get_application_any_user(
    db: AsyncSession,
    application_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
) -> Application | None:
    """Fetch application for admin/reviewer — still scoped to tenant."""
    app = await db.get(Application, application_id)
    if app is None:
        return None
    if tenant_id and app.tenant_id and app.tenant_id != tenant_id:
        return None
    await db.refresh(app, ["template", "attachments", "reviews"])
    return app


async def list_applications(
    db: AsyncSession,
    student_id: uuid.UUID,
    state: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[Application]:
    q = select(Application).where(Application.student_id == student_id)
    if state:
        q = q.where(Application.state == state)
    q = q.order_by(Application.updated_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    apps = list(result.scalars().all())
    for app in apps:
        await db.refresh(app, ["template"])
    return apps


async def update_application(
    db: AsyncSession, app: Application, data: ApplicationUpdate
) -> Application:
    if app.state not in (ApplicationState.draft, ApplicationState.changes_requested):
        raise ValueError("Application cannot be edited in current state")
    if data.field_values is not None:
        app.field_values = data.field_values
    if data.letter_body is not None:
        app.letter_body = data.letter_body
    if data.language is not None:
        app.language = data.language
    await db.commit()
    await db.refresh(app, ["template", "attachments", "reviews"])
    return app


async def delete_application(db: AsyncSession, app: Application) -> None:
    if app.state != ApplicationState.draft:
        raise ValueError("Only draft applications can be deleted")
    await db.delete(app)
    await db.commit()


# ── Submission & lifecycle ────────────────────────────────────────────────────

async def submit_application(
    db: AsyncSession,
    app: Application,
    first_approver_choice: str,
    settings: "StudentCampusSettings | None",
) -> Application:
    if app.state not in (ApplicationState.draft,):
        raise ValueError("Only draft applications can be submitted")

    if first_approver_choice == "mentor":
        if settings is None or settings.mentor_user_id is None:
            raise ValueError("No mentor configured. Set a mentor in Settings or send to your department.")
        app.current_approver_id = settings.mentor_user_id
        app.current_approver_level = "mentor"
    else:
        app.current_approver_id = None
        app.current_approver_level = "department_head"

    app.first_approver_type = first_approver_choice
    app.state = ApplicationState.in_review
    await db.commit()
    await db.refresh(app, ["template", "attachments", "reviews"])
    return app


async def withdraw_application(db: AsyncSession, app: Application) -> Application:
    if app.state not in (ApplicationState.submitted, ApplicationState.in_review):
        raise ValueError("Application cannot be withdrawn in current state")
    if app.reviews:
        raise ValueError("Cannot withdraw — an approver has already acted")
    app.state = ApplicationState.withdrawn
    await db.commit()
    await db.refresh(app, ["template", "attachments", "reviews"])
    return app


async def resubmit_application(db: AsyncSession, app: Application) -> Application:
    if app.state != ApplicationState.changes_requested:
        raise ValueError("Only applications with requested changes can be resubmitted")
    app.state = ApplicationState.in_review
    app.round_count += 1
    await db.commit()
    await db.refresh(app, ["template", "attachments", "reviews"])
    return app


async def record_review(
    db: AsyncSession,
    app: Application,
    reviewer_id: uuid.UUID,
    data: ReviewRequest,
) -> ApplicationReview:
    review = ApplicationReview(
        application_id=app.id,
        reviewer_id=reviewer_id,
        reviewer_role=app.current_approver_level or "reviewer",
        decision=data.decision,
        notes=data.notes,
    )
    db.add(review)

    now = _now()
    if data.decision == "approved":
        template = app.template
        requires_accounts = template.requires_accounts_approval if template else False
        next_level = _NEXT_LEVEL.get(app.current_approver_level or "", "")

        if app.current_approver_level == "dean" and not requires_accounts:
            next_level = ""

        if not next_level:
            app.state = ApplicationState.approved
            app.approved_at = now
            app.current_approver_level = None
            # Trigger PDF generation in background
            asyncio.create_task(_generate_pdf_background(app.id))
        else:
            app.current_approver_level = next_level
            app.current_approver_id = None

    elif data.decision == "rejected":
        app.state = ApplicationState.rejected
        app.rejected_at = now
        app.current_approver_level = None

    elif data.decision == "changes_requested":
        app.state = ApplicationState.changes_requested

    await db.commit()
    # Refresh all columns first (updated_at is server-side so it's expired after commit),
    # then explicitly load relationships so Pydantic serialization never triggers lazy loads.
    await db.refresh(app)
    await db.refresh(app, ["template", "attachments", "reviews"])
    return review


# ── Attachments ───────────────────────────────────────────────────────────────

async def save_attachment(
    db: AsyncSession,
    app: Application,
    filename: str,
    content: bytes,
    content_type: str,
) -> ApplicationAttachment:
    sha256 = hashlib.sha256(content).hexdigest()
    dest = _upload_path(app.id) / f"{uuid.uuid4()}_{filename}"
    dest.write_bytes(content)

    attach = ApplicationAttachment(
        application_id=app.id,
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
    db: AsyncSession, app: Application, attachment_id: uuid.UUID
) -> None:
    if app.state not in (ApplicationState.draft, ApplicationState.changes_requested):
        raise ValueError("Attachments can only be removed while drafting")
    result = await db.execute(
        select(ApplicationAttachment).where(
            ApplicationAttachment.id == attachment_id,
            ApplicationAttachment.application_id == app.id,
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


# ── AI Drafting ───────────────────────────────────────────────────────────────

async def generate_draft(app: Application, student_name: str) -> str:
    """Call the AI pipeline to draft a formal letter. Falls back to skeleton on failure."""
    template = app.template
    template_name = template.name if template else "General Application"
    fv = app.field_values or {}
    lang = app.language

    reason = fv.get("reason", fv.get("situation", ""))
    amount = fv.get("amount", fv.get("outstanding_amount", ""))
    pay_date = fv.get("payment_date", fv.get("payment_by_date", ""))
    dept = fv.get("department", "")
    course = fv.get("course_code", "")
    extra_fields = []
    if amount:
        extra_fields.append(f"Amount involved: {amount}")
    if pay_date:
        extra_fields.append(f"Requested date: {pay_date}")
    if dept:
        extra_fields.append(f"Department: {dept}")
    if course:
        extra_fields.append(f"Course: {course}")

    extra_str = "\n".join(extra_fields)

    output_lang = "Bengali" if lang == "bn" else "English"

    prompt = (
        f"Draft a formal university application letter in {output_lang} for the following request.\n\n"
        f"Application type: {template_name}\n"
        f"Student name: {student_name}\n"
        f"University: Daffodil International University\n"
        f"Student's situation (in their own words): {reason}\n"
        f"{extra_str}\n\n"
        f"Format the letter with:\n"
        f"- Date (today)\n"
        f"- To: The appropriate authority at DIU\n"
        f"- Subject: A clear, formal subject line\n"
        f"- Respectful greeting\n"
        f"- 3-4 paragraphs explaining the situation professionally\n"
        f"- Request for favorable consideration\n"
        f"- Formal closing (Yours sincerely / বিনীত নিবেদক)\n"
        f"- Signature block: Name, ID, Department, Date\n\n"
        f"Do not invent facts not provided. Use [TO BE FILLED] for any missing details."
    )

    try:
        from app.ai.models import ChatRequest
        from app.ai import pipeline
        response = await asyncio.wait_for(
            pipeline.run(ChatRequest(query=prompt, mode="campus", lang="EN" if lang == "en" else "BN")),
            timeout=30.0,
        )
        body = response.answer.strip()
        # Reject stub/garbage responses — a real letter contains letter keywords
        letter_markers = ("dear", "subject:", "to,", "yours sincerely", "respectfully", "বিনীত")
        looks_like_letter = any(m in body.lower() for m in letter_markers)
        if body and len(body) > 100 and looks_like_letter:
            return body
    except Exception as e:
        logger.warning("AI drafting failed: %s", e)

    # Skeleton fallback
    from datetime import date
    today = date.today().strftime("%d %B %Y")
    return (
        f"{today}\n\n"
        f"To,\nThe Registrar / Dean\nDaffodil International University\nDhaka, Bangladesh\n\n"
        f"Subject: {template_name} — Request for Favorable Consideration\n\n"
        f"Respected Sir/Madam,\n\n"
        f"I, {student_name}, a student of Daffodil International University, "
        f"most respectfully beg to state that {reason or '[TO BE FILLED — describe your situation]'}.\n\n"
        f"In light of the above circumstances, I humbly request your kind consideration "
        f"and approval of this application.\n\n"
        f"I shall remain ever grateful for your gracious action.\n\n"
        f"Yours sincerely,\n{student_name}\n[Student ID]\n[Department]\n{today}"
    )


async def explain_attachment(attach: ApplicationAttachment, lang: str) -> dict:
    """Read the file and ask the AI pipeline to explain the document."""
    output_lang = "Bengali" if lang == "bn" else "English"
    filename = attach.original_filename
    doc_type_hint = "official document"
    if "medical" in filename.lower() or "certificate" in filename.lower():
        doc_type_hint = "medical certificate"
    elif "court" in filename.lower() or "order" in filename.lower():
        doc_type_hint = "court order"
    elif "income" in filename.lower() or "salary" in filename.lower():
        doc_type_hint = "income/salary proof"

    prompt = (
        f"A student has uploaded a file named '{filename}' as proof for their university application. "
        f"It appears to be a {doc_type_hint}. "
        f"In {output_lang}, briefly explain: what type of document this is, "
        f"what it likely proves, whether it is relevant for a university application, "
        f"and any important warnings the student should know. "
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


# ── PDF Generation ────────────────────────────────────────────────────────────

def _pdf_safe(text: str) -> str:
    """Strip characters outside latin-1 so fpdf2 built-in fonts don't crash."""
    return text.encode("latin-1", errors="replace").decode("latin-1")

async def _generate_pdf_background(application_id: uuid.UUID) -> None:
    from app.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            app = await db.get(Application, application_id)
            if app is None:
                return
            await db.refresh(app, ["template", "attachments", "reviews"])
            pdf_bytes = _build_pdf(app)
            pdf_path = _upload_path(application_id) / "signed_application.pdf"
            pdf_path.write_bytes(pdf_bytes)
            app.pdf_ref = str(pdf_path)
            await db.commit()
    except Exception as e:
        logger.error("PDF generation failed for %s: %s", application_id, e)


def _build_pdf(app: Application) -> bytes:
    from fpdf import FPDF
    import qrcode

    pdf = FPDF()
    pdf.set_margins(25, 25, 25)
    pdf.add_page()
    w = pdf.w - pdf.l_margin - pdf.r_margin

    # Letterhead
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(w, 10, "Daffodil International University", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(w, 6, "Daffodil Smart City, Birulia, Savar, Dhaka-1216, Bangladesh", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(w, 5, "Verified via Anchor AI - campus.anchor-ai.bd", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_draw_color(11, 29, 53)
    pdf.set_line_width(0.5)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(6)

    # Application type (English name only — avoid Bangla in latin-1 font)
    template_name = _pdf_safe(app.template.name if app.template else "Application")
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(w, 8, template_name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    date_str = (app.approved_at or app.created_at).strftime("%d %b %Y")
    pdf.cell(w, 5, f"Reference: DIU-APP-{str(app.id)[:8].upper()}  |  Status: {app.state.upper()}  |  Date: {date_str}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Letter body
    if app.letter_body:
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(w, 6, _pdf_safe(app.letter_body))
        pdf.ln(4)

    # Approval chain table
    if app.reviews:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(w, 7, "Approval Chain", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 9)
        col_w = [w * 0.28, w * 0.24, w * 0.24, w * 0.24]
        pdf.set_fill_color(230, 230, 230)
        for header, cw in zip(["Role", "Decision", "Date", "Notes"], col_w):
            pdf.cell(cw, 6, header, border=1, fill=True)
        pdf.ln()
        pdf.set_font("Helvetica", "", 8)
        for rev in app.reviews:
            note = _pdf_safe((rev.notes or "")[:30])
            pdf.cell(col_w[0], 6, rev.reviewer_role.title(), border=1)
            pdf.cell(col_w[1], 6, rev.decision.title(), border=1)
            pdf.cell(col_w[2], 6, rev.reviewed_at.strftime("%d %b %Y"), border=1)
            pdf.cell(col_w[3], 6, note, border=1)
            pdf.ln()
        pdf.ln(4)

    # QR code
    verify_url = f"https://anchor-ai.bd/verify/{app.id}"
    try:
        qr_img = qrcode.make(verify_url)
        buf = io.BytesIO()
        qr_img.save(buf, format="PNG")
        buf.seek(0)
        qr_x = pdf.w - pdf.r_margin - 28
        qr_y = pdf.get_y()
        pdf.image(buf, x=qr_x, y=qr_y, w=28, h=28)
    except Exception:
        pass

    # Footer
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(w, 5, f"Anchor AI | Digital Signature | {verify_url}", align="C", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


# ── Campus Settings ───────────────────────────────────────────────────────────

async def get_or_create_settings(db: AsyncSession, user_id: uuid.UUID) -> StudentCampusSettings:
    settings = await db.get(StudentCampusSettings, user_id)
    if settings is None:
        settings = StudentCampusSettings(user_id=user_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


async def update_settings(
    db: AsyncSession,
    settings: StudentCampusSettings,
    mentor_user_id: uuid.UUID | None = ...,
    department: str | None = ...,
) -> StudentCampusSettings:
    if mentor_user_id is not ...:
        settings.mentor_user_id = mentor_user_id
    if department is not ... and not settings.department_locked:
        settings.department = department
    await db.commit()
    await db.refresh(settings)
    return settings


async def get_available_mentors(
    db: AsyncSession, tenant_id: uuid.UUID | None
) -> list[User]:
    q = select(User).where(
        User.role.in_([Role.admin, Role.moderator]),
    )
    if tenant_id:
        q = q.where(User.tenant_id == tenant_id)
    result = await db.execute(q.limit(100))
    return list(result.scalars().all())
