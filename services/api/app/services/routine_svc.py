import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.routine import AcademicRoutine, RoutineStatus
from app.schemas.routines import RoutineCreate, RoutineUpdate

PAGE_SIZE = 20


async def list_routines(
    db: AsyncSession,
    department: str | None = None,
    batch: str | None = None,
    semester: str | None = None,
    status_filter: RoutineStatus | None = None,
    is_admin: bool = False,
    page: int = 1,
) -> list[AcademicRoutine]:
    q = select(AcademicRoutine)
    if not is_admin:
        q = q.where(AcademicRoutine.status == RoutineStatus.published)
    elif status_filter is not None:
        q = q.where(AcademicRoutine.status == status_filter)
    if department is not None:
        q = q.where(AcademicRoutine.department.ilike(f"%{department}%"))
    if batch is not None:
        q = q.where(AcademicRoutine.batch == batch)
    if semester is not None:
        q = q.where(AcademicRoutine.semester.ilike(f"%{semester}%"))
    q = q.order_by(AcademicRoutine.created_at.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_routine(
    db: AsyncSession,
    routine_id: uuid.UUID,
    is_admin: bool = False,
) -> AcademicRoutine | None:
    q = select(AcademicRoutine).where(AcademicRoutine.id == routine_id)
    if not is_admin:
        q = q.where(AcademicRoutine.status == RoutineStatus.published)
    result = await db.execute(q)
    return result.scalars().first()


async def create_routine(
    db: AsyncSession,
    data: RoutineCreate,
    created_by: uuid.UUID,
) -> AcademicRoutine:
    routine = AcademicRoutine(
        tenant_id=data.tenant_id,
        department=data.department,
        batch=data.batch,
        semester=data.semester,
        academic_year=data.academic_year,
        title=data.title,
        slots=[s.model_dump() for s in data.slots],
        created_by_user_id=created_by,
    )
    db.add(routine)
    await db.commit()
    await db.refresh(routine)
    return routine


async def update_routine(
    db: AsyncSession,
    routine: AcademicRoutine,
    data: RoutineUpdate,
) -> AcademicRoutine:
    if data.title is not None:
        routine.title = data.title
    if data.department is not None:
        routine.department = data.department
    if data.batch is not None:
        routine.batch = data.batch
    if data.semester is not None:
        routine.semester = data.semester
    if data.academic_year is not None:
        routine.academic_year = data.academic_year
    if data.slots is not None:
        routine.slots = [s.model_dump() for s in data.slots]
    await db.commit()
    await db.refresh(routine)
    return routine


async def publish_routine(
    db: AsyncSession,
    routine: AcademicRoutine,
    published_by: uuid.UUID,
) -> AcademicRoutine:
    if routine.status == RoutineStatus.published:
        raise ValueError("Routine is already published")
    routine.status = RoutineStatus.published
    routine.published_by_user_id = published_by
    routine.published_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(routine)
    return routine
