"""Admin moderation for officer-scorecard ratings (super_admin / admin)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.schemas.officer_scorecards import (
    ModerateRequest, OfficerRatingResponse, RatingModerationItem,
)
from app.services import officer_scorecard_svc

router = APIRouter(prefix="/v1/admin/officer-scorecards", tags=["admin-officer-scorecards"])


@router.get("/ratings", response_model=list[RatingModerationItem])
async def list_ratings(
    status: str | None = Query(default="pending"),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
    _token: TokenData = Depends(require_role("super_admin", "admin")),
):
    return await officer_scorecard_svc.list_ratings_for_moderation(db, status=status, page=page)


@router.post("/ratings/{rating_id}/moderate", response_model=OfficerRatingResponse)
async def moderate_rating(
    rating_id: uuid.UUID,
    body: ModerateRequest,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin", "admin")),
):
    try:
        rating = await officer_scorecard_svc.moderate_rating(
            db, rating_id, body.action, token.user_id
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    return OfficerRatingResponse.model_validate(rating)
