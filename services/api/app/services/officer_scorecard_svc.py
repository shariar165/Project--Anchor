"""
Officer scorecard service — national-mode police accountability.

Public read of station/officer aggregates (approved ratings only); authenticated
rating submission held in a super-admin moderation queue.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.officer_scorecard import Officer, OfficerRating, PoliceStation
from app.schemas.officer_scorecards import (
    OfficerRatingCreate, OfficerSummary, RatingModerationItem,
    StationListItem, StationSummary,
)

PAGE_SIZE = 50


def _avg(vals: list) -> float | None:
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


# ── Directory + aggregates ────────────────────────────────────────────────────

async def list_stations(
    db: AsyncSession, district: str | None = None, q: str | None = None
) -> list[StationListItem]:
    stmt = select(PoliceStation).order_by(PoliceStation.district, PoliceStation.name)
    if district:
        stmt = stmt.where(PoliceStation.district == district)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(PoliceStation.name.ilike(like), PoliceStation.district.ilike(like)))
    stations = list((await db.execute(stmt)).scalars().all())
    if not stations:
        return []

    # One grouped query for approved-rating aggregates across the listed stations.
    ids = [s.id for s in stations]
    rows = (await db.execute(
        select(
            OfficerRating.station_id,
            func.count(),
            func.avg(OfficerRating.overall),
        )
        .where(OfficerRating.station_id.in_(ids), OfficerRating.status == "approved")
        .group_by(OfficerRating.station_id)
    )).all()
    agg = {sid: (cnt, avg) for sid, cnt, avg in rows}

    items: list[StationListItem] = []
    for s in stations:
        cnt, avg = agg.get(s.id, (0, None))
        item = StationListItem.model_validate(s)
        item.total_count = cnt
        item.avg_overall = round(float(avg), 2) if avg is not None else None
        items.append(item)
    return items


async def get_station(db: AsyncSession, station_id: uuid.UUID) -> PoliceStation | None:
    return (await db.execute(
        select(PoliceStation).where(PoliceStation.id == station_id)
    )).scalars().first()


async def get_station_summary(db: AsyncSession, station: PoliceStation) -> StationSummary:
    ratings = list((await db.execute(
        select(OfficerRating).where(
            OfficerRating.station_id == station.id,
            OfficerRating.status == "approved",
        )
    )).scalars().all())

    histogram = {str(i): sum(1 for r in ratings if r.overall == i) for i in range(1, 6)}

    # Per-officer aggregates
    officers = list((await db.execute(
        select(Officer).where(Officer.station_id == station.id).order_by(Officer.name)
    )).scalars().all())
    officer_summaries: list[OfficerSummary] = []
    for o in officers:
        o_ratings = [r for r in ratings if r.officer_id == o.id]
        officer_summaries.append(OfficerSummary(
            id=o.id, name=o.name, rank=o.rank, badge_no=o.badge_no,
            total_count=len(o_ratings),
            avg_overall=_avg([r.overall for r in o_ratings]),
        ))

    return StationSummary(
        id=station.id,
        name=station.name,
        district=station.district,
        division=station.division,
        address=station.address,
        total_count=len(ratings),
        avg_overall=_avg([r.overall for r in ratings]),
        avg_responsiveness=_avg([r.responsiveness for r in ratings]),
        avg_conduct=_avg([r.conduct for r in ratings]),
        avg_integrity=_avg([r.integrity for r in ratings]),
        histogram=histogram,
        officers=officer_summaries,
    )


# ── Ratings ───────────────────────────────────────────────────────────────────

async def create_rating(
    db: AsyncSession, data: OfficerRatingCreate, rater_user_id: uuid.UUID
) -> OfficerRating:
    station = await get_station(db, data.station_id)
    if station is None:
        raise ValueError("Police station not found")
    if data.officer_id is not None:
        officer = (await db.execute(
            select(Officer).where(
                Officer.id == data.officer_id, Officer.station_id == data.station_id
            )
        )).scalars().first()
        if officer is None:
            raise ValueError("Officer not found at this station")

    # Explicit duplicate guard: the (rater, station, officer) unique constraint
    # does NOT catch repeats when officer_id is NULL (SQL treats NULLs as distinct),
    # so a station-level re-rating would slip through. Check both cases here.
    dup_stmt = select(OfficerRating).where(
        OfficerRating.rater_user_id == rater_user_id,
        OfficerRating.station_id == data.station_id,
    )
    if data.officer_id is None:
        dup_stmt = dup_stmt.where(OfficerRating.officer_id.is_(None))
    else:
        dup_stmt = dup_stmt.where(OfficerRating.officer_id == data.officer_id)
    if (await db.execute(dup_stmt)).scalars().first() is not None:
        raise ValueError("You have already rated this station/officer")

    rating = OfficerRating(
        rater_user_id=rater_user_id,
        station_id=data.station_id,
        officer_id=data.officer_id,
        responsiveness=data.responsiveness,
        conduct=data.conduct,
        integrity=data.integrity,
        overall=data.overall,
        comment=data.comment,
        anonymous=data.anonymous,
        status="pending",
    )
    db.add(rating)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ValueError("You have already rated this station/officer")
    await db.refresh(rating)
    return rating


async def list_my_ratings(db: AsyncSession, rater_user_id: uuid.UUID) -> list[OfficerRating]:
    return list((await db.execute(
        select(OfficerRating)
        .where(OfficerRating.rater_user_id == rater_user_id)
        .order_by(OfficerRating.created_at.desc())
    )).scalars().all())


# ── Admin moderation ──────────────────────────────────────────────────────────

async def list_ratings_for_moderation(
    db: AsyncSession, status: str | None = "pending", page: int = 1
) -> list[RatingModerationItem]:
    stmt = (
        select(OfficerRating, PoliceStation.name, Officer.name)
        .join(PoliceStation, OfficerRating.station_id == PoliceStation.id)
        .outerjoin(Officer, OfficerRating.officer_id == Officer.id)
        .order_by(OfficerRating.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    if status:
        stmt = stmt.where(OfficerRating.status == status)
    rows = (await db.execute(stmt)).all()

    items: list[RatingModerationItem] = []
    for rating, station_name, officer_name in rows:
        item = RatingModerationItem.model_validate(rating)
        item.station_name = station_name
        item.officer_name = officer_name
        items.append(item)
    return items


async def moderate_rating(
    db: AsyncSession, rating_id: uuid.UUID, action: str, moderator_id: uuid.UUID
) -> OfficerRating:
    rating = (await db.execute(
        select(OfficerRating).where(OfficerRating.id == rating_id)
    )).scalars().first()
    if rating is None:
        raise ValueError("Rating not found")
    rating.status = "approved" if action == "approve" else "rejected"
    rating.moderated_at = datetime.now(tz=timezone.utc)
    rating.moderated_by = moderator_id
    await db.commit()
    await db.refresh(rating)
    return rating


# ── Seed ──────────────────────────────────────────────────────────────────────

_SEED_STATIONS = [
    ("Mirpur Model Thana", "Dhaka", "Dhaka"),
    ("Pallabi Thana", "Dhaka", "Dhaka"),
    ("Gulshan Thana", "Dhaka", "Dhaka"),
    ("Dhanmondi Thana", "Dhaka", "Dhaka"),
    ("Ramna Thana", "Dhaka", "Dhaka"),
    ("Mohammadpur Thana", "Dhaka", "Dhaka"),
    ("Tejgaon Thana", "Dhaka", "Dhaka"),
    ("Uttara West Thana", "Dhaka", "Dhaka"),
    ("Badda Thana", "Dhaka", "Dhaka"),
    ("Khilgaon Thana", "Dhaka", "Dhaka"),
    ("Motijheel Thana", "Dhaka", "Dhaka"),
    ("Sutrapur Thana", "Dhaka", "Dhaka"),
]


async def seed_stations(db: AsyncSession) -> None:
    """Idempotent seed of well-known Dhaka thanas. Called on app startup."""
    existing = (await db.execute(
        select(PoliceStation.name, PoliceStation.district)
    )).all()
    present = {(n, d) for n, d in existing}
    added = False
    for name, district, division in _SEED_STATIONS:
        if (name, district) in present:
            continue
        db.add(PoliceStation(name=name, district=district, division=division))
        added = True
    if added:
        await db.commit()
