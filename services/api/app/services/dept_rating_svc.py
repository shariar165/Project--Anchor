import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.dept_rating import DepartmentRating
from app.schemas.dept_ratings import DepartmentRatingCreate, DepartmentSummary


async def create_rating(
    db: AsyncSession,
    data: DepartmentRatingCreate,
    rater_user_id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
) -> DepartmentRating:
    rating = DepartmentRating(
        rater_user_id=rater_user_id,
        tenant_id=tenant_id,
        department=data.department,
        period=data.period,
        overall=data.overall,
        teaching_quality=data.teaching_quality,
        resources=data.resources,
        environment=data.environment,
        feedback=data.feedback,
        anonymous=data.anonymous,
    )
    db.add(rating)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ValueError("You have already rated this department for this period")
    await db.refresh(rating)
    return rating


async def get_department_summary(
    db: AsyncSession,
    department: str,
    tenant_id: uuid.UUID | None = None,
) -> DepartmentSummary:
    q = select(DepartmentRating).where(DepartmentRating.department == department)
    if tenant_id is not None:
        q = q.where(DepartmentRating.tenant_id == tenant_id)
    ratings = list((await db.execute(q)).scalars().all())

    def _avg(vals: list) -> float | None:
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    histogram = {str(i): sum(1 for r in ratings if r.overall == i) for i in range(1, 6)}

    return DepartmentSummary(
        department=department,
        total_count=len(ratings),
        avg_overall=_avg([r.overall for r in ratings]),
        avg_teaching=_avg([r.teaching_quality for r in ratings]),
        avg_resources=_avg([r.resources for r in ratings]),
        avg_environment=_avg([r.environment for r in ratings]),
        histogram=histogram,
    )


async def list_my_ratings(
    db: AsyncSession,
    rater_user_id: uuid.UUID,
) -> list[DepartmentRating]:
    q = (
        select(DepartmentRating)
        .where(DepartmentRating.rater_user_id == rater_user_id)
        .order_by(DepartmentRating.created_at.desc())
    )
    result = await db.execute(q)
    return list(result.scalars().all())
