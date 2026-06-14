from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, TokenData
from app.schemas.dept_ratings import DepartmentRatingCreate, DepartmentRatingResponse, DepartmentSummary
from app.services import dept_rating_svc

router = APIRouter(prefix="/v1/departments", tags=["departments"])


# IMPORTANT: /ratings/mine must come before /{dept}/summary to avoid
# "mine" being captured as {dept} with remainder "/summary" failing to match.
@router.get("/ratings/mine", response_model=list[DepartmentRatingResponse])
async def my_ratings(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    ratings = await dept_rating_svc.list_my_ratings(db, token.user_id)
    return [DepartmentRatingResponse.from_orm_masked(r) for r in ratings]


@router.post("/ratings", response_model=DepartmentRatingResponse, status_code=status.HTTP_201_CREATED)
async def create_rating(
    body: DepartmentRatingCreate,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(get_current_user),
):
    try:
        rating = await dept_rating_svc.create_rating(
            db, body, rater_user_id=token.user_id, tenant_id=token.tenant_id
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    return DepartmentRatingResponse.from_orm_masked(rating)


@router.get("/{dept}/summary", response_model=DepartmentSummary)
async def department_summary(
    dept: str,
    db: AsyncSession = Depends(get_db),
):
    return await dept_rating_svc.get_department_summary(db, dept)
