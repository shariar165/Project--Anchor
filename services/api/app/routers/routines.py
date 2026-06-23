import uuid
from fastapi import (
    APIRouter, Depends, File, HTTPException, Query, Security, UploadFile, status,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.redis import get_redis
from app.deps import get_current_user, require_role, TokenData
from app.models.routine import AcademicRoutine, RoutineStatus
from app.models.user import User, AccountStatus
from app.schemas.routines import RoutineCreate, RoutineUpdate, RoutineResponse
from app.services import export_svc, routine_svc
from app.services.token import decode_token, is_blacklisted

router = APIRouter(prefix="/v1/routines", tags=["routines"])

_opt_bearer = HTTPBearer(auto_error=False)


async def _opt_user(
    creds: HTTPAuthorizationCredentials | None = Security(_opt_bearer),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> TokenData | None:
    if creds is None:
        return None
    try:
        payload = decode_token(creds.credentials)
        if payload.get("type") != "access":
            return None
        td = TokenData(payload)
        if await is_blacklisted(redis, td.jti):
            return None
        result = await db.execute(select(User).where(User.id == td.user_id))
        user = result.scalars().first()
        if not user or user.status != AccountStatus.active:
            return None
        return td
    except Exception:
        return None


def _is_admin(token: TokenData | None) -> bool:
    return token is not None and token.role in ("admin", "moderator")


@router.get("", response_model=list[RoutineResponse])
async def list_routines(
    department: str | None = Query(default=None),
    batch: str | None = Query(default=None),
    semester: str | None = Query(default=None),
    status: RoutineStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    token: TokenData | None = Depends(_opt_user),
):
    admin = _is_admin(token)
    return await routine_svc.list_routines(
        db,
        department=department,
        batch=batch,
        semester=semester,
        status_filter=status if admin else None,
        is_admin=admin,
        page=page,
    )


@router.post("", response_model=RoutineResponse, status_code=status.HTTP_201_CREATED)
async def create_routine(
    body: RoutineCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await routine_svc.create_routine(db, body, created_by=token.user_id)


@router.get("/{routine_id}", response_model=RoutineResponse)
async def get_routine(
    routine_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData | None = Depends(_opt_user),
):
    admin = _is_admin(token)
    routine = await routine_svc.get_routine(db, routine_id, is_admin=admin)
    if routine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Routine not found")
    return routine


@router.get("/{routine_id}/export")
async def export_routine(
    routine_id: uuid.UUID,
    format: str = Query(default="pdf"),
    db: AsyncSession = Depends(get_db),
    token: TokenData | None = Depends(_opt_user),
):
    """Download a routine as PDF / DOCX / CSV. Slots render as a table."""
    admin = _is_admin(token)
    routine = await routine_svc.get_routine(db, routine_id, is_admin=admin)
    if routine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Routine not found")

    meta = []
    if routine.department:
        meta.append(("Department", routine.department))
    if routine.batch:
        meta.append(("Batch", routine.batch))
    if routine.semester:
        meta.append(("Semester", routine.semester))
    if routine.academic_year:
        meta.append(("Academic year", routine.academic_year))

    headers = ["Day", "Time", "Course", "Name", "Room", "Teacher"]
    rows = []
    for s in (routine.slots or []):
        time = s.get("time") or "-".join(t for t in (s.get("start_time"), s.get("end_time")) if t) or ""
        rows.append([
            s.get("day", ""),
            time,
            s.get("course_code") or s.get("course") or "",
            s.get("course_name") or "",
            s.get("room") or "",
            s.get("teacher") or s.get("instructor") or "",
        ])

    doc = export_svc.ExportDoc(
        title=routine.title,
        subtitle="Academic Routine",
        meta=meta,
        table_headers=headers,
        table_rows=rows,
    )
    stem = f"routine-{routine.semester or str(routine.id)[:8]}"
    return export_svc.export_response(doc, format, stem)


@router.patch("/{routine_id}", response_model=RoutineResponse)
async def update_routine(
    routine_id: uuid.UUID,
    body: RoutineUpdate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    routine = await routine_svc.get_routine(db, routine_id, is_admin=True)
    if routine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Routine not found")
    return await routine_svc.update_routine(db, routine, body)


@router.post("/{routine_id}/publish", response_model=RoutineResponse)
async def publish_routine(
    routine_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    routine = await routine_svc.get_routine(db, routine_id, is_admin=True)
    if routine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Routine not found")
    try:
        return await routine_svc.publish_routine(db, routine, published_by=token.user_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


# ── Routine Builder editing surface (admin) ───────────────────────────────────

class AIEditBody(BaseModel):
    text: str = Field(min_length=2, max_length=500)


@router.post("/{routine_id}/import")
async def import_routine_slots(
    routine_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Replace a routine's slots from an uploaded Excel/CSV (Excel round-trip
    editing). Moves the routine back to draft for review before re-publishing."""
    routine = await routine_svc.get_routine(db, routine_id, is_admin=True)
    if routine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Routine not found")

    content = await file.read()
    fn = (file.filename or "").lower()
    if fn.endswith((".xlsx", ".xls")):
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif fn.endswith(".csv"):
        content_type = "text/csv"
    else:
        content_type = file.content_type or ""

    try:
        result = await routine_svc.import_slots(db, routine, content, content_type)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return {**result, "routine": RoutineResponse.model_validate(routine)}


@router.get("/{routine_id}/validate")
async def validate_routine(
    routine_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Detect teacher/room/section clashes in a routine's slots for the editor's
    red-cell highlighting."""
    routine = await routine_svc.get_routine(db, routine_id, is_admin=True)
    if routine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Routine not found")
    conflicts = routine_svc.validate_slots(routine.slots or [])
    return {"conflicts": conflicts, "count": len(conflicts)}


@router.post("/{routine_id}/ai-edit")
async def ai_edit_routine(
    routine_id: uuid.UUID,
    body: AIEditBody,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    """Translate a natural-language instruction into a slot change (local Ollama).
    Returns a preview — the client applies it via PATCH after confirmation."""
    routine = await routine_svc.get_routine(db, routine_id, is_admin=True)
    if routine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Routine not found")
    return await routine_svc.ai_edit_slots(routine.slots or [], body.text)
