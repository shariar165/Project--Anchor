import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.models.lawyer import Lawyer
from app.models.user import User, Role

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


async def get_lawyer_by_user(db: AsyncSession, user_id: uuid.UUID) -> Lawyer | None:
    result = await db.execute(select(Lawyer).where(Lawyer.user_id == user_id))
    return result.scalars().first()


async def apply_as_lawyer(db: AsyncSession, user: User, payload) -> Lawyer:
    """Create a pending lawyer profile for a logged-in user (one per account).

    Raises ValueError if the user already has a lawyer profile that is pending or
    verified. A previously rejected profile is reset back to pending and resubmitted.
    """
    existing = await get_lawyer_by_user(db, user.id)
    if existing is not None:
        if existing.status in ("pending", "verified"):
            raise ValueError("You already have a lawyer profile")
        # Rejected -> allow resubmission by overwriting the rejected row.
        existing.bar_number = payload.bar_number
        existing.phone = payload.phone
        existing.email = payload.email or user.email
        existing.district = payload.district
        existing.specializations = payload.specializations or []
        existing.bio = payload.bio
        existing.status = "pending"
        existing.verified = False
        existing.verified_at = None
        existing.verified_by = None
        existing.rejection_reason = None
        await db.flush()
        return existing

    # Guard against a duplicate bar number held by another lawyer.
    if payload.bar_number:
        dup = await db.execute(select(Lawyer).where(Lawyer.bar_number == payload.bar_number))
        if dup.scalars().first():
            raise ValueError("Bar number already registered")

    lawyer = Lawyer(
        user_id=user.id,
        name=user.full_name,
        bar_number=payload.bar_number,
        phone=payload.phone,
        email=payload.email or user.email,
        district=payload.district,
        specializations=payload.specializations or [],
        bio=payload.bio,
        status="pending",
        verified=False,
        tenant_id=user.tenant_id,
    )
    db.add(lawyer)
    await db.flush()
    return lawyer


async def list_for_admin(
    db: AsyncSession,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
) -> tuple[list[Lawyer], int]:
    q = select(Lawyer).where(Lawyer.user_id.is_not(None))
    if status:
        q = q.where(Lawyer.status == status)
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.where(or_(Lawyer.name.ilike(term), Lawyer.bar_number.ilike(term)))
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(Lawyer.created_at.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    result = await db.execute(q)
    return list(result.scalars().all()), int(total or 0)


async def verify_lawyer(db: AsyncSession, lawyer: Lawyer, by_user_id: uuid.UUID) -> Lawyer:
    """Mark a lawyer verified and upgrade the linked account to the `lawyer` role."""
    lawyer.status = "verified"
    lawyer.verified = True
    lawyer.verified_at = datetime.now(timezone.utc)
    lawyer.verified_by = by_user_id
    lawyer.rejection_reason = None
    if lawyer.user_id:
        result = await db.execute(select(User).where(User.id == lawyer.user_id))
        account = result.scalars().first()
        if account and account.role not in (Role.admin, Role.super_admin):
            account.role = Role.lawyer
    await db.flush()
    return lawyer


async def reject_lawyer(db: AsyncSession, lawyer: Lawyer, reason: str) -> Lawyer:
    lawyer.status = "rejected"
    lawyer.verified = False
    lawyer.verified_at = None
    lawyer.rejection_reason = reason
    await db.flush()
    return lawyer
