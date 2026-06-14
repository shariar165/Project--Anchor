from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.lawyer import Lawyer

PAGE_SIZE = 20


async def list_lawyers(
    db: AsyncSession,
    district: str | None = None,
    specialization: str | None = None,
    verified_only: bool = False,
    page: int = 1,
) -> list[Lawyer]:
    q = select(Lawyer)
    if district is not None:
        q = q.where(Lawyer.district.ilike(f"%{district}%"))
    if verified_only:
        q = q.where(Lawyer.verified.is_(True))
    q = q.order_by(Lawyer.name).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    result = await db.execute(q)
    lawyers = list(result.scalars().all())

    # Filter by specialization in Python — JSON list, small dataset
    if specialization:
        term = specialization.lower()
        lawyers = [l for l in lawyers if any(term in s.lower() for s in (l.specializations or []))]

    return lawyers
