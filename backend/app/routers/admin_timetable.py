import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.deps import require_role, TokenData
from app.services import timetable_svc
from app.services.timetable_solver import run_solve_job, nl_to_entry_edit, load_solver_data
from app.schemas.timetable import (
    TermCreate, TermPatch, TermOut,
    BatchCreate, BatchPatch, BatchOut, SectionCreate,
    GenerateStructureRequest,
    RoomCreate, RoomPatch, RoomOut,
    CourseCreate, CoursePatch, CourseOut,
    FacultyProfileCreate, FacultyProfilePatch, FacultyProfileOut,
    OfferingCreate, OfferingOut,
    EligibilityCreate, EligibilityOut,
    ScheduleConfigUpsert, ScheduleConfigOut,
    ConstraintCreate, ConstraintPatch, ConstraintOut,
    SolveRequest, SolveJobOut,
    EntryEdit, EntryOut, EntryDetailOut,
    ResolveRequest, NLEditRequest,
    PublishRequest, PublishOut,
    ValidateOut, ConflictOut,
    ImportResult,
)
from app.models.timetable import TimetableEntry

router = APIRouter(prefix="/v1/admin/timetable", tags=["timetable"])


# ── Terms ─────────────────────────────────────────────────────────────────────

@router.get("/terms", response_model=list[TermOut])
async def list_terms(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await timetable_svc.list_terms(db, tenant_id=token.tenant_id)


@router.post("/terms", response_model=TermOut, status_code=status.HTTP_201_CREATED)
async def create_term(
    body: TermCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    if body.tenant_id is None:
        body = body.model_copy(update={"tenant_id": token.tenant_id})
    return await timetable_svc.create_term(db, body)


@router.patch("/terms/{term_id}", response_model=TermOut)
async def patch_term(
    term_id: uuid.UUID,
    body: TermPatch,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    term = await timetable_svc.get_term(db, term_id)
    if not term:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Term not found")
    return await timetable_svc.patch_term(db, term, body)


@router.delete("/terms/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_term(
    term_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    term = await timetable_svc.get_term(db, term_id)
    if not term:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Term not found")
    try:
        await timetable_svc.delete_term(db, term)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


# ── Batches ───────────────────────────────────────────────────────────────────

@router.get("/batches", response_model=list[BatchOut])
async def list_batches(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    batches = await timetable_svc.list_batches(db, tenant_id=token.tenant_id)
    result = []
    for batch in batches:
        sections_out = []
        for sec in getattr(batch, "_sections", []):
            lgs = [
                {"id": str(lg.id), "section_id": str(lg.section_id), "name": lg.name}
                for lg in getattr(sec, "_lab_groups", [])
            ]
            sections_out.append({
                "id": sec.id, "batch_id": sec.batch_id, "name": sec.name,
                "lab_groups": lgs,
            })
        result.append(BatchOut(
            id=batch.id, tenant_id=batch.tenant_id,
            name=batch.name, program=batch.program,
            active=batch.active, sections=sections_out,
        ))
    return result


@router.post("/batches", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
async def create_batch(
    body: BatchCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    if body.tenant_id is None:
        body = body.model_copy(update={"tenant_id": token.tenant_id})
    batch = await timetable_svc.create_batch(db, body)
    return BatchOut(
        id=batch.id, tenant_id=batch.tenant_id,
        name=batch.name, program=batch.program,
        active=batch.active, sections=[],
    )


@router.patch("/batches/{batch_id}", response_model=BatchOut)
async def patch_batch(
    batch_id: uuid.UUID,
    body: BatchPatch,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    batch = await timetable_svc.get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    batch = await timetable_svc.patch_batch(db, batch, body)
    return BatchOut(
        id=batch.id, tenant_id=batch.tenant_id,
        name=batch.name, program=batch.program,
        active=batch.active, sections=[],
    )


@router.post("/batches/{batch_id}/sections", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_section(
    batch_id: uuid.UUID,
    body: SectionCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    batch = await timetable_svc.get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    sec = await timetable_svc.create_section(db, batch_id, body)
    return {"id": str(sec.id), "batch_id": str(sec.batch_id), "name": sec.name}


@router.post("/batches/{batch_id}/generate-structure", response_model=dict, status_code=status.HTTP_201_CREATED)
async def generate_structure(
    batch_id: uuid.UUID,
    body: GenerateStructureRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    batch = await timetable_svc.get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    sections = await timetable_svc.generate_sections(db, batch_id, body.count, body.lab_split)
    return {"created_sections": len(sections), "batch_id": str(batch_id)}


# ── Rooms ─────────────────────────────────────────────────────────────────────

@router.get("/rooms", response_model=list[RoomOut])
async def list_rooms(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await timetable_svc.list_rooms(db, tenant_id=token.tenant_id)


@router.post("/rooms", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(
    body: RoomCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    if body.tenant_id is None:
        body = body.model_copy(update={"tenant_id": token.tenant_id})
    return await timetable_svc.create_room(db, body)


@router.patch("/rooms/{room_id}", response_model=RoomOut)
async def patch_room(
    room_id: uuid.UUID,
    body: RoomPatch,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    room = await timetable_svc.get_room(db, room_id)
    if not room:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Room not found")
    return await timetable_svc.patch_room(db, room, body)


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    room = await timetable_svc.get_room(db, room_id)
    if not room:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Room not found")
    await timetable_svc.delete_room(db, room)


# ── Courses ───────────────────────────────────────────────────────────────────

@router.get("/courses", response_model=list[CourseOut])
async def list_courses(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await timetable_svc.list_courses(db, tenant_id=token.tenant_id)


@router.post("/courses", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    body: CourseCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    if body.tenant_id is None:
        body = body.model_copy(update={"tenant_id": token.tenant_id})
    return await timetable_svc.create_course(db, body)


@router.patch("/courses/{course_id}", response_model=CourseOut)
async def patch_course(
    course_id: uuid.UUID,
    body: CoursePatch,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    course = await timetable_svc.get_course(db, course_id)
    if not course:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return await timetable_svc.patch_course(db, course, body)


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    course = await timetable_svc.get_course(db, course_id)
    if not course:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    await timetable_svc.delete_course(db, course)


# ── Faculty ───────────────────────────────────────────────────────────────────

@router.get("/faculty", response_model=list[FacultyProfileOut])
async def list_faculty(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await timetable_svc.list_faculty(db, tenant_id=token.tenant_id)


@router.post("/faculty", response_model=FacultyProfileOut, status_code=status.HTTP_201_CREATED)
async def create_faculty(
    body: FacultyProfileCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    if body.tenant_id is None:
        body = body.model_copy(update={"tenant_id": token.tenant_id})
    return await timetable_svc.create_faculty_profile(db, body)


@router.patch("/faculty/{faculty_id}", response_model=FacultyProfileOut)
async def patch_faculty(
    faculty_id: uuid.UUID,
    body: FacultyProfilePatch,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    fp = await timetable_svc.get_faculty_profile(db, faculty_id)
    if not fp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Faculty profile not found")
    return await timetable_svc.patch_faculty_profile(db, fp, body)


@router.delete("/faculty/{faculty_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faculty(
    faculty_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    fp = await timetable_svc.get_faculty_profile(db, faculty_id)
    if not fp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Faculty profile not found")
    await timetable_svc.delete_faculty_profile(db, fp)


# ── Offerings ─────────────────────────────────────────────────────────────────

@router.get("/offerings", response_model=list[OfferingOut])
async def list_offerings(
    term_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await timetable_svc.list_offerings(db, term_id=term_id)


@router.post("/offerings", response_model=OfferingOut, status_code=status.HTTP_201_CREATED)
async def create_offering(
    body: OfferingCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await timetable_svc.create_offering(db, body)


@router.delete("/offerings/{offering_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_offering(
    offering_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    await timetable_svc.delete_offering(db, offering_id)


# ── Eligibility ───────────────────────────────────────────────────────────────

@router.get("/eligibility", response_model=list[EligibilityOut])
async def list_eligibility(
    faculty_id: uuid.UUID | None = Query(default=None),
    course_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await timetable_svc.list_eligibility(db, faculty_id=faculty_id, course_id=course_id)


@router.post("/eligibility", response_model=EligibilityOut, status_code=status.HTTP_201_CREATED)
async def create_eligibility(
    body: EligibilityCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await timetable_svc.create_eligibility(db, body)


@router.delete("/eligibility/{elig_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_eligibility(
    elig_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    await timetable_svc.delete_eligibility(db, elig_id)


# ── Schedule config ───────────────────────────────────────────────────────────

@router.get("/config", response_model=ScheduleConfigOut | None)
async def get_config(
    term_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await timetable_svc.get_schedule_config(db, term_id=term_id, tenant_id=token.tenant_id)


@router.post("/config", response_model=ScheduleConfigOut)
async def upsert_config(
    body: ScheduleConfigUpsert,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await timetable_svc.upsert_schedule_config(db, body, requesting_tenant=token.tenant_id)


# ── Constraints ───────────────────────────────────────────────────────────────

@router.get("/constraints", response_model=list[ConstraintOut])
async def list_constraints(
    term_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    return await timetable_svc.list_constraints(db, term_id=term_id, tenant_id=token.tenant_id)


@router.post("/constraints", response_model=ConstraintOut, status_code=status.HTTP_201_CREATED)
async def create_constraint(
    body: ConstraintCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    if body.tenant_id is None:
        body = body.model_copy(update={"tenant_id": token.tenant_id})
    return await timetable_svc.create_constraint(db, body, created_by=token.user_id)


@router.patch("/constraints/{con_id}", response_model=ConstraintOut)
async def patch_constraint(
    con_id: uuid.UUID,
    body: ConstraintPatch,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    con = await timetable_svc.get_constraint(db, con_id)
    if not con:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Constraint not found")
    return await timetable_svc.patch_constraint(db, con, body)


@router.delete("/constraints/{con_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_constraint(
    con_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    con = await timetable_svc.get_constraint(db, con_id)
    if not con:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Constraint not found")
    await timetable_svc.delete_constraint(db, con)


# ── Solve ─────────────────────────────────────────────────────────────────────

@router.post("/solve", response_model=SolveJobOut, status_code=status.HTTP_202_ACCEPTED)
async def start_solve(
    body: SolveRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    job = await timetable_svc.create_solve_job(
        db, term_id=body.term_id,
        requested_by=token.user_id,
        tenant_id=token.tenant_id,
        params={"time_limit_s": body.time_limit_s, "seed_from_version": body.seed_from_version},
    )
    background_tasks.add_task(run_solve_job, job.id, AsyncSessionLocal, body)
    return SolveJobOut.from_orm_job(job)


@router.get("/solve/{job_id}", response_model=SolveJobOut)
async def get_solve_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    job = await timetable_svc.get_solve_job(db, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Solve job not found")
    return SolveJobOut.from_orm_job(job)


# ── Entries ───────────────────────────────────────────────────────────────────

@router.get("/entries", response_model=list[EntryDetailOut])
async def list_entries(
    term_id: uuid.UUID = Query(...),
    version: int = Query(...),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    from sqlalchemy import select
    from app.models.timetable import (
        TimetableCourse, TimetableSection, TimetableBatch,
        TimetableLabGroup, TimetableFacultyProfile, TimetableRoom,
    )
    from app.models.user import User

    entries = await timetable_svc.list_entries(db, term_id, version)
    result = []
    for e in entries:
        # Resolve names inline
        course_r = await db.execute(select(TimetableCourse).where(TimetableCourse.id == e.course_id))
        course = course_r.scalars().first()
        sec_r = await db.execute(select(TimetableSection).where(TimetableSection.id == e.section_id))
        section = sec_r.scalars().first()
        batch = None
        if section:
            batch_r = await db.execute(select(TimetableBatch).where(TimetableBatch.id == section.batch_id))
            batch = batch_r.scalars().first()
        lg = None
        if e.lab_group_id:
            lg_r = await db.execute(select(TimetableLabGroup).where(TimetableLabGroup.id == e.lab_group_id))
            lg = lg_r.scalars().first()
        fp_r = await db.execute(select(TimetableFacultyProfile).where(TimetableFacultyProfile.id == e.faculty_id))
        fp = fp_r.scalars().first()
        faculty_name = ""
        if fp:
            ur = await db.execute(select(User).where(User.id == fp.user_id))
            user = ur.scalars().first()
            faculty_name = user.full_name if user else ""
        room_r = await db.execute(select(TimetableRoom).where(TimetableRoom.id == e.room_id))
        room = room_r.scalars().first()

        result.append(EntryDetailOut(
            id=e.id, term_id=e.term_id, result_version=e.result_version,
            course_code=course.code if course else "",
            course_name=course.name if course else "",
            section_name=section.name if section else "",
            batch_name=batch.name if batch else "",
            lab_group_name=lg.name if lg else None,
            faculty_name=faculty_name,
            room_name=room.name if room else "",
            room_type=room.room_type if room else "",
            day=e.day, slot=e.slot,
            is_lab=e.is_lab, locked=e.locked,
            source=e.source, published=e.published,
            course_id=e.course_id, section_id=e.section_id,
            lab_group_id=e.lab_group_id,
            faculty_id=e.faculty_id, room_id=e.room_id,
        ))
    return result


@router.patch("/entries/{entry_id}", response_model=EntryOut)
async def patch_entry(
    entry_id: uuid.UUID,
    body: EntryEdit,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    entry = await timetable_svc.get_entry(db, entry_id)
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return await timetable_svc.patch_entry(db, entry, body)


# ── Resolve (minimal-perturbation re-solve) ───────────────────────────────────

@router.post("/resolve", response_model=SolveJobOut, status_code=status.HTTP_202_ACCEPTED)
async def resolve(
    body: ResolveRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    base_entries = await timetable_svc.list_entries(db, body.term_id, body.base_version)
    locked_ids = {e.id for e in base_entries if e.locked} if body.keep_locked else set()

    solve_req = SolveRequest(
        term_id=body.term_id,
        time_limit_s=body.time_limit_s,
        seed_from_version=body.base_version,
    )
    job = await timetable_svc.create_solve_job(
        db, term_id=body.term_id,
        requested_by=token.user_id,
        tenant_id=token.tenant_id,
        params={"mode": "resolve", "base_version": body.base_version},
    )
    background_tasks.add_task(
        run_solve_job, job.id, AsyncSessionLocal, solve_req,
        body.change, locked_ids, base_entries,
    )
    return SolveJobOut.from_orm_job(job)


# ── NL edit ───────────────────────────────────────────────────────────────────

@router.post("/nl-edit", response_model=SolveJobOut, status_code=status.HTTP_202_ACCEPTED)
async def nl_edit(
    body: NLEditRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    base_entries = await timetable_svc.list_entries(db, body.term_id, body.base_version)
    entries_context = [
        {
            "id": str(e.id),
            "course_id": str(e.course_id),
            "section_id": str(e.section_id),
            "faculty_id": str(e.faculty_id),
            "room_id": str(e.room_id),
            "day": e.day,
            "slot": e.slot,
        }
        for e in base_entries
    ]
    edit = await nl_to_entry_edit(body.text, entries_context)
    if edit is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Could not parse the command — please use structured edit or rephrase",
        )

    solve_req = SolveRequest(term_id=body.term_id, seed_from_version=body.base_version)
    locked_ids = {e.id for e in base_entries if e.locked}
    job = await timetable_svc.create_solve_job(
        db, term_id=body.term_id,
        requested_by=token.user_id,
        tenant_id=token.tenant_id,
        params={"mode": "nl-edit", "text": body.text},
    )
    background_tasks.add_task(
        run_solve_job, job.id, AsyncSessionLocal, solve_req,
        edit, locked_ids, base_entries,
    )
    return SolveJobOut.from_orm_job(job)


# ── Validate ──────────────────────────────────────────────────────────────────

@router.get("/validate", response_model=ValidateOut)
async def validate(
    term_id: uuid.UUID = Query(...),
    version: int = Query(...),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    conflicts = await timetable_svc.validate_entries(db, term_id, version)
    return ValidateOut(
        version=version,
        conflicts=conflicts,
        hard_count=len(conflicts),
        soft_count=0,
    )


# ── Publish ───────────────────────────────────────────────────────────────────

@router.post("/publish", response_model=PublishOut)
async def publish(
    body: PublishRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    conflicts = await timetable_svc.validate_entries(db, body.term_id, body.version)
    hard_conflicts = [c for c in conflicts if c.conflict_type not in ("soft",)]
    if hard_conflicts:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot publish: {len(hard_conflicts)} hard conflict(s). Run /validate for details.",
        )
    try:
        published_ids = await timetable_svc.publish_version(
            db, body.term_id, body.version, published_by=token.user_id
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return PublishOut(published_routines=len(published_ids), routine_ids=published_ids)


# ── CSV / XLSX import ─────────────────────────────────────────────────────────

@router.post("/import", response_model=ImportResult)
async def import_data(
    entity: str = Query(..., description="courses | rooms"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    content = await file.read()
    content_type = file.content_type or ""
    result = await timetable_svc.import_entities(
        db, entity, content, content_type, tenant_id=token.tenant_id
    )
    return ImportResult(entity=entity, **result)
