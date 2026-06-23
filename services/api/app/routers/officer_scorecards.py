"""
Officer scorecard router — national-mode police accountability (public read).

Route ordering: literal /ratings/mine MUST be registered before /stations/{id}
to avoid path-segment conflicts.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, TokenData
from app.limiter import limiter
from app.schemas.officer_scorecards import (
    OfficerRatingCreate, OfficerRatingResponse, StationListItem, StationSummary,
)
from app.services import officer_scorecard_svc

router = APIRouter(prefix="/v1/officer-scorecards", tags=["officer-scorecards"])


@router.get("/stations", response_model=list[StationListItem])
async def list_stations(
    district: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await officer_scorecard_svc.list_stations(db, district=district, q=q)


@router.get("/ratings/mine", response_model=list[OfficerRatingResponse])
async def my_ratings(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    ratings = await officer_scorecard_svc.list_my_ratings(db, token.user_id)
    return [OfficerRatingResponse.from_orm_masked(r) for r in ratings]


@router.post("/ratings", response_model=OfficerRatingResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_rating(
    request: Request,
    body: OfficerRatingCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    try:
        rating = await officer_scorecard_svc.create_rating(db, body, rater_user_id=token.user_id)
    except ValueError as e:
        msg = str(e)
        code = status.HTTP_404_NOT_FOUND if "not found" in msg else status.HTTP_409_CONFLICT
        raise HTTPException(code, detail=msg)
    return OfficerRatingResponse.from_orm_masked(rating)


@router.get("/stations/{station_id}", response_model=StationSummary)
async def get_station(
    station_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    station = await officer_scorecard_svc.get_station(db, station_id)
    if station is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Police station not found")
    return await officer_scorecard_svc.get_station_summary(db, station)
