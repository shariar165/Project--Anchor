import csv
import io
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timetable import (
    TimetableTerm, TimetableBatch, TimetableSection, TimetableLabGroup,
    TimetableRoom, TimetableCourse, TimetableFacultyProfile,
    TimetableStudentEnrollment, TimetableCourseOffering,
    TimetableTeacherEligibility, TimetableScheduleConfig,
    TimetableConstraint, TimetableSolveJob, TimetableEntry,
)
from app.models.routine import AcademicRoutine, RoutineStatus
from app.models.user import User
from app.schemas.timetable import (
    TermCreate, TermPatch,
    BatchCreate, BatchPatch, SectionCreate,
    RoomCreate, RoomPatch,
    CourseCreate, CoursePatch,
    FacultyProfileCreate, FacultyProfilePatch,
    OfferingCreate, EligibilityCreate,
    ScheduleConfigUpsert,
    ConstraintCreate, ConstraintPatch,
    EntryEdit, ConflictOut,
)

# ── Terms ─────────────────────────────────────────────────────────────────────

async def list_terms(db: AsyncSession, tenant_id: uuid.UUID | None = None) -> list[TimetableTerm]:
    q = select(TimetableTerm)
    if tenant_id:
        q = q.where(TimetableTerm.tenant_id == tenant_id)
    result = await db.execute(q.order_by(TimetableTerm.created_at.desc()))
    return list(result.scalars().all())


async def create_term(db: AsyncSession, data: TermCreate) -> TimetableTerm:
    term = TimetableTerm(name=data.name, tenant_id=data.tenant_id)
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return term


async def get_term(db: AsyncSession, term_id: uuid.UUID) -> TimetableTerm | None:
    result = await db.execute(select(TimetableTerm).where(TimetableTerm.id == term_id))
    return result.scalars().first()


async def patch_term(db: AsyncSession, term: TimetableTerm, data: TermPatch) -> TimetableTerm:
    if data.name is not None:
        term.name = data.name
    if data.is_active is not None:
        if data.is_active:
            # deactivate all others in the same tenant
            all_terms = await list_terms(db, tenant_id=term.tenant_id)
            for t in all_terms:
                t.is_active = False
        term.is_active = data.is_active
    await db.commit()
    await db.refresh(term)
    return term


async def delete_term(db: AsyncSession, term: TimetableTerm) -> None:
    # guard: no solve jobs referencing this term
    result = await db.execute(select(TimetableSolveJob).where(TimetableSolveJob.term_id == term.id).limit(1))
    if result.scalars().first():
        raise ValueError("Cannot delete term with existing solve jobs")
    await db.delete(term)
    await db.commit()


# ── Batches / Sections / Lab groups ──────────────────────────────────────────

async def list_batches(db: AsyncSession, tenant_id: uuid.UUID | None = None) -> list[TimetableBatch]:
    q = select(TimetableBatch)
    if tenant_id:
        q = q.where(TimetableBatch.tenant_id == tenant_id)
    result = await db.execute(q.order_by(TimetableBatch.name))
    batches = list(result.scalars().all())
    # eagerly load sections + lab groups
    for batch in batches:
        sec_result = await db.execute(
            select(TimetableSection).where(TimetableSection.batch_id == batch.id)
        )
        batch._sections = list(sec_result.scalars().all())
        for sec in batch._sections:
            lg_result = await db.execute(
                select(TimetableLabGroup).where(TimetableLabGroup.section_id == sec.id)
            )
            sec._lab_groups = list(lg_result.scalars().all())
    return batches


async def create_batch(db: AsyncSession, data: BatchCreate) -> TimetableBatch:
    batch = TimetableBatch(name=data.name, program=data.program, tenant_id=data.tenant_id)
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return batch


async def get_batch(db: AsyncSession, batch_id: uuid.UUID) -> TimetableBatch | None:
    result = await db.execute(select(TimetableBatch).where(TimetableBatch.id == batch_id))
    return result.scalars().first()


async def patch_batch(db: AsyncSession, batch: TimetableBatch, data: BatchPatch) -> TimetableBatch:
    if data.name is not None:
        batch.name = data.name
    if data.program is not None:
        batch.program = data.program
    if data.active is not None:
        batch.active = data.active
    await db.commit()
    await db.refresh(batch)
    return batch


async def create_section(db: AsyncSession, batch_id: uuid.UUID, data: SectionCreate) -> TimetableSection:
    section = TimetableSection(batch_id=batch_id, name=data.name)
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section


async def create_lab_group(db: AsyncSession, section_id: uuid.UUID, name: str) -> TimetableLabGroup:
    lg = TimetableLabGroup(section_id=section_id, name=name)
    db.add(lg)
    await db.commit()
    await db.refresh(lg)
    return lg


async def generate_sections(
    db: AsyncSession, batch_id: uuid.UUID, count: int, lab_split: bool = True
) -> list[TimetableSection]:
    sections = []
    for i in range(count):
        name = chr(ord('A') + i)
        sec = TimetableSection(batch_id=batch_id, name=name)
        db.add(sec)
        await db.flush()
        if lab_split:
            db.add(TimetableLabGroup(section_id=sec.id, name=f"{name}1"))
            db.add(TimetableLabGroup(section_id=sec.id, name=f"{name}2"))
        sections.append(sec)
    await db.commit()
    return sections


# ── Rooms ─────────────────────────────────────────────────────────────────────

async def list_rooms(db: AsyncSession, tenant_id: uuid.UUID | None = None) -> list[TimetableRoom]:
    q = select(TimetableRoom)
    if tenant_id:
        q = q.where(TimetableRoom.tenant_id == tenant_id)
    result = await db.execute(q.order_by(TimetableRoom.name))
    return list(result.scalars().all())


async def create_room(db: AsyncSession, data: RoomCreate) -> TimetableRoom:
    room = TimetableRoom(
        name=data.name, room_type=data.room_type,
        capacity=data.capacity, tenant_id=data.tenant_id,
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


async def get_room(db: AsyncSession, room_id: uuid.UUID) -> TimetableRoom | None:
    result = await db.execute(select(TimetableRoom).where(TimetableRoom.id == room_id))
    return result.scalars().first()


async def patch_room(db: AsyncSession, room: TimetableRoom, data: RoomPatch) -> TimetableRoom:
    if data.name is not None:
        room.name = data.name
    if data.room_type is not None:
        room.room_type = data.room_type
    if data.capacity is not None:
        room.capacity = data.capacity
    await db.commit()
    await db.refresh(room)
    return room


async def delete_room(db: AsyncSession, room: TimetableRoom) -> None:
    await db.delete(room)
    await db.commit()


# ── Courses ───────────────────────────────────────────────────────────────────

async def list_courses(db: AsyncSession, tenant_id: uuid.UUID | None = None) -> list[TimetableCourse]:
    q = select(TimetableCourse)
    if tenant_id:
        q = q.where(TimetableCourse.tenant_id == tenant_id)
    result = await db.execute(q.order_by(TimetableCourse.code))
    return list(result.scalars().all())


async def create_course(db: AsyncSession, data: CourseCreate) -> TimetableCourse:
    course = TimetableCourse(
        code=data.code, name=data.name, credits=data.credits,
        is_lab=data.is_lab, weekly_classes=data.weekly_classes,
        tenant_id=data.tenant_id,
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


async def get_course(db: AsyncSession, course_id: uuid.UUID) -> TimetableCourse | None:
    result = await db.execute(select(TimetableCourse).where(TimetableCourse.id == course_id))
    return result.scalars().first()


async def patch_course(db: AsyncSession, course: TimetableCourse, data: CoursePatch) -> TimetableCourse:
    if data.code is not None:
        course.code = data.code
    if data.name is not None:
        course.name = data.name
    if data.credits is not None:
        course.credits = data.credits
    if data.is_lab is not None:
        course.is_lab = data.is_lab
    if data.weekly_classes is not None:
        course.weekly_classes = data.weekly_classes
    await db.commit()
    await db.refresh(course)
    return course


async def delete_course(db: AsyncSession, course: TimetableCourse) -> None:
    await db.delete(course)
    await db.commit()


# ── Faculty profiles ──────────────────────────────────────────────────────────

async def list_faculty(db: AsyncSession, tenant_id: uuid.UUID | None = None) -> list[TimetableFacultyProfile]:
    q = select(TimetableFacultyProfile)
    if tenant_id:
        q = q.where(TimetableFacultyProfile.tenant_id == tenant_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def create_faculty_profile(
    db: AsyncSession, data: FacultyProfileCreate
) -> TimetableFacultyProfile:
    fp = TimetableFacultyProfile(
        user_id=data.user_id, rank=data.rank,
        min_credits=data.min_credits, max_credits=data.max_credits,
        pref_slot=data.pref_slot, off_days=data.off_days,
        max_per_day=data.max_per_day, tenant_id=data.tenant_id,
    )
    db.add(fp)
    await db.commit()
    await db.refresh(fp)
    return fp


async def get_faculty_profile(db: AsyncSession, faculty_id: uuid.UUID) -> TimetableFacultyProfile | None:
    result = await db.execute(
        select(TimetableFacultyProfile).where(TimetableFacultyProfile.id == faculty_id)
    )
    return result.scalars().first()


async def patch_faculty_profile(
    db: AsyncSession, fp: TimetableFacultyProfile, data: FacultyProfilePatch
) -> TimetableFacultyProfile:
    if data.rank is not None:
        fp.rank = data.rank
    if data.min_credits is not None:
        fp.min_credits = data.min_credits
    if data.max_credits is not None:
        fp.max_credits = data.max_credits
    if data.pref_slot is not None:
        fp.pref_slot = data.pref_slot
    if data.off_days is not None:
        fp.off_days = data.off_days
    if data.max_per_day is not None:
        fp.max_per_day = data.max_per_day
    if data.active is not None:
        fp.active = data.active
    await db.commit()
    await db.refresh(fp)
    return fp


async def delete_faculty_profile(db: AsyncSession, fp: TimetableFacultyProfile) -> None:
    await db.delete(fp)
    await db.commit()


# ── Offerings ─────────────────────────────────────────────────────────────────

async def list_offerings(
    db: AsyncSession, term_id: uuid.UUID | None = None
) -> list[TimetableCourseOffering]:
    q = select(TimetableCourseOffering)
    if term_id:
        q = q.where(TimetableCourseOffering.term_id == term_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def create_offering(db: AsyncSession, data: OfferingCreate) -> TimetableCourseOffering:
    offering = TimetableCourseOffering(
        term_id=data.term_id, course_id=data.course_id, batch_id=data.batch_id,
    )
    db.add(offering)
    await db.commit()
    await db.refresh(offering)
    return offering


async def delete_offering(db: AsyncSession, offering_id: uuid.UUID) -> None:
    result = await db.execute(
        select(TimetableCourseOffering).where(TimetableCourseOffering.id == offering_id)
    )
    obj = result.scalars().first()
    if obj:
        await db.delete(obj)
        await db.commit()


# ── Eligibility ───────────────────────────────────────────────────────────────

async def list_eligibility(
    db: AsyncSession, faculty_id: uuid.UUID | None = None, course_id: uuid.UUID | None = None
) -> list[TimetableTeacherEligibility]:
    q = select(TimetableTeacherEligibility)
    if faculty_id:
        q = q.where(TimetableTeacherEligibility.faculty_id == faculty_id)
    if course_id:
        q = q.where(TimetableTeacherEligibility.course_id == course_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def create_eligibility(
    db: AsyncSession, data: EligibilityCreate
) -> TimetableTeacherEligibility:
    elig = TimetableTeacherEligibility(faculty_id=data.faculty_id, course_id=data.course_id)
    db.add(elig)
    await db.commit()
    await db.refresh(elig)
    return elig


async def delete_eligibility(db: AsyncSession, elig_id: uuid.UUID) -> None:
    result = await db.execute(
        select(TimetableTeacherEligibility).where(TimetableTeacherEligibility.id == elig_id)
    )
    obj = result.scalars().first()
    if obj:
        await db.delete(obj)
        await db.commit()


# ── Schedule config ───────────────────────────────────────────────────────────

async def get_schedule_config(
    db: AsyncSession, term_id: uuid.UUID | None = None, tenant_id: uuid.UUID | None = None
) -> TimetableScheduleConfig | None:
    q = select(TimetableScheduleConfig)
    if term_id:
        q = q.where(TimetableScheduleConfig.term_id == term_id)
    elif tenant_id:
        q = q.where(TimetableScheduleConfig.tenant_id == tenant_id)
    result = await db.execute(q.limit(1))
    return result.scalars().first()


async def upsert_schedule_config(
    db: AsyncSession, data: ScheduleConfigUpsert, requesting_tenant: uuid.UUID | None = None
) -> TimetableScheduleConfig:
    existing = await get_schedule_config(db, term_id=data.term_id, tenant_id=requesting_tenant)
    if existing:
        existing.days = data.days
        existing.slots = data.slots
        existing.off_days = data.off_days
        await db.commit()
        await db.refresh(existing)
        return existing
    cfg = TimetableScheduleConfig(
        tenant_id=data.tenant_id or requesting_tenant,
        term_id=data.term_id,
        days=data.days,
        slots=data.slots,
        off_days=data.off_days,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return cfg


# ── Constraints ───────────────────────────────────────────────────────────────

async def list_constraints(
    db: AsyncSession,
    term_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
) -> list[TimetableConstraint]:
    q = select(TimetableConstraint)
    if term_id:
        q = q.where(TimetableConstraint.term_id == term_id)
    if tenant_id:
        q = q.where(TimetableConstraint.tenant_id == tenant_id)
    result = await db.execute(q.order_by(TimetableConstraint.enforcement, TimetableConstraint.constraint_type))
    return list(result.scalars().all())


async def create_constraint(
    db: AsyncSession, data: ConstraintCreate, created_by: uuid.UUID | None = None
) -> TimetableConstraint:
    con = TimetableConstraint(
        constraint_type=data.constraint_type,
        scope=data.scope, params=data.params,
        enforcement=data.enforcement, weight=data.weight,
        enabled=True,
        term_id=data.term_id, tenant_id=data.tenant_id,
        created_by=created_by,
    )
    db.add(con)
    await db.commit()
    await db.refresh(con)
    return con


async def get_constraint(db: AsyncSession, con_id: uuid.UUID) -> TimetableConstraint | None:
    result = await db.execute(select(TimetableConstraint).where(TimetableConstraint.id == con_id))
    return result.scalars().first()


async def patch_constraint(
    db: AsyncSession, con: TimetableConstraint, data: ConstraintPatch
) -> TimetableConstraint:
    if data.enabled is not None:
        con.enabled = data.enabled
    if data.weight is not None:
        con.weight = data.weight
    if data.enforcement is not None:
        con.enforcement = data.enforcement
    if data.params is not None:
        con.params = data.params
    await db.commit()
    await db.refresh(con)
    return con


async def delete_constraint(db: AsyncSession, con: TimetableConstraint) -> None:
    await db.delete(con)
    await db.commit()


# ── Solve jobs ────────────────────────────────────────────────────────────────

async def create_solve_job(
    db: AsyncSession, term_id: uuid.UUID,
    requested_by: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    params: dict | None = None,
) -> TimetableSolveJob:
    job = TimetableSolveJob(
        term_id=term_id, requested_by=requested_by,
        tenant_id=tenant_id, params=params or {},
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_solve_job(db: AsyncSession, job_id: uuid.UUID) -> TimetableSolveJob | None:
    result = await db.execute(select(TimetableSolveJob).where(TimetableSolveJob.id == job_id))
    return result.scalars().first()


async def update_solve_job(db: AsyncSession, job: TimetableSolveJob, **kwargs) -> TimetableSolveJob:
    for k, v in kwargs.items():
        setattr(job, k, v)
    await db.commit()
    await db.refresh(job)
    return job


# ── Entries ───────────────────────────────────────────────────────────────────

async def list_entries(
    db: AsyncSession, term_id: uuid.UUID, version: int
) -> list[TimetableEntry]:
    result = await db.execute(
        select(TimetableEntry)
        .where(TimetableEntry.term_id == term_id, TimetableEntry.result_version == version)
        .order_by(TimetableEntry.day, TimetableEntry.slot)
    )
    return list(result.scalars().all())


async def get_entry(db: AsyncSession, entry_id: uuid.UUID) -> TimetableEntry | None:
    result = await db.execute(select(TimetableEntry).where(TimetableEntry.id == entry_id))
    return result.scalars().first()


async def patch_entry(db: AsyncSession, entry: TimetableEntry, data: EntryEdit) -> TimetableEntry:
    if data.new_day is not None:
        entry.day = data.new_day
    if data.new_slot is not None:
        entry.slot = data.new_slot
    if data.new_faculty_id is not None:
        entry.faculty_id = data.new_faculty_id
    if data.new_room_id is not None:
        entry.room_id = data.new_room_id
    entry.locked = data.lock
    entry.source = "manual"
    await db.commit()
    await db.refresh(entry)
    return entry


async def get_next_version(db: AsyncSession, term_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.max(TimetableEntry.result_version))
        .where(TimetableEntry.term_id == term_id)
    )
    current_max = result.scalar()
    return (current_max or 0) + 1


async def bulk_insert_entries(
    db: AsyncSession, entries: list[TimetableEntry]
) -> None:
    for entry in entries:
        db.add(entry)
    await db.commit()


# ── Validate entries ──────────────────────────────────────────────────────────

async def validate_entries(
    db: AsyncSession, term_id: uuid.UUID, version: int
) -> list[ConflictOut]:
    entries = await list_entries(db, term_id, version)
    conflicts: list[ConflictOut] = []

    # Load room types
    room_ids = {e.room_id for e in entries}
    rooms = {}
    for rid in room_ids:
        r = await get_room(db, rid)
        if r:
            rooms[rid] = r

    # Check (room, day, slot) uniqueness
    room_slot_seen: dict = {}
    for e in entries:
        key = (e.room_id, e.day, e.slot)
        if key in room_slot_seen:
            prev = room_slot_seen[key]
            conflicts.append(ConflictOut(
                conflict_type="room_double_booked",
                entry_ids=[prev.id, e.id],
                description=f"Room {rooms.get(e.room_id, {}).name if e.room_id in rooms else e.room_id} double-booked on day {e.day} slot {e.slot}",
            ))
        else:
            room_slot_seen[key] = e

    # Check (faculty, day, slot) uniqueness
    faculty_slot_seen: dict = {}
    for e in entries:
        key = (e.faculty_id, e.day, e.slot)
        if key in faculty_slot_seen:
            prev = faculty_slot_seen[key]
            conflicts.append(ConflictOut(
                conflict_type="teacher_overlap",
                entry_ids=[prev.id, e.id],
                description=f"Teacher assigned to two classes on day {e.day} slot {e.slot}",
            ))
        else:
            faculty_slot_seen[key] = e

    # Check theory section (day, slot) uniqueness — labs use lab_group so they're separate
    theory_slot_seen: dict = {}
    for e in entries:
        if not e.is_lab:
            key = (e.section_id, e.day, e.slot)
            if key in theory_slot_seen:
                prev = theory_slot_seen[key]
                conflicts.append(ConflictOut(
                    conflict_type="section_overlap",
                    entry_ids=[prev.id, e.id],
                    description=f"Section has two theory classes on day {e.day} slot {e.slot}",
                ))
            else:
                theory_slot_seen[key] = e

    # Check room type matches is_lab
    for e in entries:
        room = rooms.get(e.room_id)
        if room:
            if e.is_lab and room.room_type == "THEORY":
                conflicts.append(ConflictOut(
                    conflict_type="room_type_mismatch",
                    entry_ids=[e.id],
                    description=f"Lab class assigned to THEORY room {room.name}",
                ))
            elif not e.is_lab and room.room_type == "LAB":
                conflicts.append(ConflictOut(
                    conflict_type="room_type_mismatch",
                    entry_ids=[e.id],
                    description=f"Theory class assigned to LAB room {room.name}",
                ))

    # Check a section's theory and its own lab don't share a slot — lab-group
    # students also attend the section theory, so it's a real student clash.
    # (Two different lab groups of the same section may coexist.)
    section_theory_slot: dict = {}
    for e in entries:
        if not e.is_lab:
            section_theory_slot[(e.section_id, e.day, e.slot)] = e
    for e in entries:
        if e.is_lab:
            theory = section_theory_slot.get((e.section_id, e.day, e.slot))
            if theory is not None:
                conflicts.append(ConflictOut(
                    conflict_type="section_lab_overlap",
                    entry_ids=[theory.id, e.id],
                    description=f"Section has a theory and a lab class at the same time on day {e.day} slot {e.slot}",
                ))

    # Check lab entries have a lab_group_id
    for e in entries:
        if e.is_lab and e.lab_group_id is None:
            conflicts.append(ConflictOut(
                conflict_type="missing_lab_group",
                entry_ids=[e.id],
                description="Lab entry missing lab_group_id",
            ))

    return conflicts


# ── Publish entries → AcademicRoutine ─────────────────────────────────────────

async def publish_version(
    db: AsyncSession,
    term_id: uuid.UUID,
    version: int,
    published_by: uuid.UUID,
) -> list[uuid.UUID]:
    """Project tt_entries → AcademicRoutine rows (one per section), publish them."""
    entries = await list_entries(db, term_id, version)
    if not entries:
        raise ValueError("No entries found for this term/version")

    # Load term
    term_result = await db.execute(select(TimetableTerm).where(TimetableTerm.id == term_id))
    term = term_result.scalars().first()
    if not term:
        raise ValueError("Term not found")

    # Load schedule config for day/slot name resolution
    config = await get_schedule_config(db, term_id=term_id)
    if not config:
        raise ValueError("Schedule config not found for this term — set days/slots first")

    days_list: list[str] = config.days
    slots_list: list[str] = config.slots

    # Load supporting data (batch via section, course, faculty→user, room)
    section_ids = {e.section_id for e in entries}
    sections = {}
    for sid in section_ids:
        r = await db.execute(select(TimetableSection).where(TimetableSection.id == sid))
        s = r.scalars().first()
        if s:
            sections[sid] = s

    batch_ids = {s.batch_id for s in sections.values()}
    batches = {}
    for bid in batch_ids:
        r = await db.execute(select(TimetableBatch).where(TimetableBatch.id == bid))
        b = r.scalars().first()
        if b:
            batches[bid] = b

    faculty_ids = {e.faculty_id for e in entries}
    faculty_map = {}
    for fid in faculty_ids:
        r = await db.execute(select(TimetableFacultyProfile).where(TimetableFacultyProfile.id == fid))
        fp = r.scalars().first()
        if fp:
            ur = await db.execute(select(User).where(User.id == fp.user_id))
            user = ur.scalars().first()
            faculty_map[fid] = user.full_name if user else str(fid)

    room_ids = {e.room_id for e in entries}
    room_map = {}
    for rid in room_ids:
        r = await db.execute(select(TimetableRoom).where(TimetableRoom.id == rid))
        room = r.scalars().first()
        if room:
            room_map[rid] = room.name

    lab_group_ids = {e.lab_group_id for e in entries if e.lab_group_id}
    lab_group_map = {}
    for lgid in lab_group_ids:
        r = await db.execute(select(TimetableLabGroup).where(TimetableLabGroup.id == lgid))
        lg = r.scalars().first()
        if lg:
            lab_group_map[lgid] = lg.name

    # Group entries by section
    by_section: dict[uuid.UUID, list[TimetableEntry]] = {}
    for e in entries:
        by_section.setdefault(e.section_id, []).append(e)

    published_ids: list[uuid.UUID] = []
    now = datetime.now(timezone.utc)

    for section_id, sec_entries in by_section.items():
        section = sections.get(section_id)
        if not section:
            continue
        batch = batches.get(section.batch_id)
        if not batch:
            continue

        # Build SlotItem list (matches app/schemas/routines.py SlotItem shape)
        slot_items = []
        for e in sec_entries:
            day_name = days_list[e.day] if e.day < len(days_list) else str(e.day)
            slot_str = slots_list[e.slot] if e.slot < len(slots_list) else str(e.slot)
            # Parse "8:30-10:00" into start/end
            if "-" in slot_str:
                parts = slot_str.split("-", 1)
                start_time, end_time = parts[0].strip(), parts[1].strip()
            else:
                start_time, end_time = slot_str, ""

            teacher_name = faculty_map.get(e.faculty_id, "")
            room_name = room_map.get(e.room_id, "")
            lab_suffix = f" [{lab_group_map.get(e.lab_group_id, '')}]" if e.lab_group_id else ""

            # Load course
            cr = await db.execute(select(TimetableCourse).where(TimetableCourse.id == e.course_id))
            course = cr.scalars().first()

            slot_items.append({
                "day": day_name,
                "start_time": start_time,
                "end_time": end_time,
                "course_code": course.code if course else "",
                "course_name": (course.name if course else "") + lab_suffix,
                "teacher": teacher_name,
                "room": room_name,
            })

        dept = batch.program
        # Encode section into batch so A/B/C each get their own AcademicRoutine row
        batch_name = f"{batch.name} ({section.name})"
        semester = term.name
        title = f"{dept} {section.name} — {term.name}"

        # Upsert: find existing non-archived routine for this section identity
        existing_q = (
            select(AcademicRoutine)
            .where(
                AcademicRoutine.department == dept,
                AcademicRoutine.batch == batch_name,
                AcademicRoutine.semester == semester,
                AcademicRoutine.status != RoutineStatus.archived,
            )
        )
        existing_r = await db.execute(existing_q)
        routine = existing_r.scalars().first()

        if routine is None:
            routine = AcademicRoutine(
                tenant_id=term.tenant_id,
                department=dept,
                batch=batch_name,
                semester=semester,
                academic_year="",
                title=title,
                slots=slot_items,
                created_by_user_id=published_by,
            )
            db.add(routine)
        else:
            routine.slots = slot_items
            routine.title = title

        routine.status = RoutineStatus.published
        routine.published_by_user_id = published_by
        routine.published_at = now
        await db.flush()
        published_ids.append(routine.id)

    # Mark entries as published
    for e in entries:
        e.published = True

    await db.commit()
    return published_ids


# ── CSV / XLSX import ─────────────────────────────────────────────────────────

async def import_entities(
    db: AsyncSession,
    entity: str,
    file_bytes: bytes,
    content_type: str,
    tenant_id: uuid.UUID | None = None,
) -> dict:
    rows = _parse_file(file_bytes, content_type)
    created = 0
    errors: list[str] = []

    for i, row in enumerate(rows, start=2):  # row 1 = header
        try:
            if entity == "courses":
                await create_course(db, CourseCreate(
                    code=row["code"],
                    name=row["name"],
                    credits=int(row.get("credits", 3)),
                    is_lab=str(row.get("is_lab", "false")).lower() == "true",
                    weekly_classes=int(row.get("weekly_classes", 2)),
                    tenant_id=tenant_id,
                ))
            elif entity == "rooms":
                await create_room(db, RoomCreate(
                    name=row["name"],
                    room_type=row.get("room_type", "THEORY").upper(),
                    capacity=int(row.get("capacity", 30)),
                    tenant_id=tenant_id,
                ))
            else:
                errors.append(f"Row {i}: unsupported entity '{entity}'")
                continue
            created += 1
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")

    return {"created": created, "errors": errors}


def _parse_file(file_bytes: bytes, content_type: str) -> list[dict]:
    if "spreadsheet" in content_type or "xlsx" in content_type or "excel" in content_type:
        try:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return []
            headers = [str(h).strip().lower() if h else "" for h in rows[0]]
            return [
                {headers[j]: (str(v).strip() if v is not None else "") for j, v in enumerate(row)}
                for row in rows[1:]
            ]
        except Exception as exc:
            raise ValueError(f"Failed to parse XLSX: {exc}")
    else:
        text = file_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        return [dict(row) for row in reader]
