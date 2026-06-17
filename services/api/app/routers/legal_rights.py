from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.legal_rights import LegalRightResponse
from app.services import legal_rights_svc

router = APIRouter(prefix="/v1/legal-rights", tags=["legal-rights"])


@router.get("", response_model=list[LegalRightResponse])
async def list_legal_rights(
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    return await legal_rights_svc.list_legal_rights(db, category=category, page=page)
