import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_role, TokenData
from app.models.user import User, Role, AccountStatus, STAFF_POSITIONS
from app.services import password as pwd_svc, audit as audit_svc
from app.services.device import get_ip

router = APIRouter(prefix="/v1/admin/users", tags=["admin-users"])

PAGE_SIZE = 20

_CREATABLE_ROLES = {"admin", "moderator"}
_ASSIGNABLE_ROLES = {"admin", "moderator", "user", "student"}


class CreateAdminRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str
    tenant_id: Optional[uuid.UUID] = None
    staff_position: Optional[str] = None


class UpdateRoleRequest(BaseModel):
    role: str


class UpdatePositionRequest(BaseModel):
    staff_position: Optional[str] = None


class UpdateStatusRequest(BaseModel):
    status: str


class UpdateTenantRequest(BaseModel):
    tenant_id: uuid.UUID


class UserRow(BaseModel):
    id: uuid.UUID
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    status: str
    mfa_enabled: bool
    email_verified: bool
    tenant_id: Optional[uuid.UUID] = None
    staff_position: Optional[str] = None

    model_config = {"from_attributes": True}


@router.get("")
async def list_users(
    page: int = Query(default=1, ge=1),
    role: Optional[str] = Query(default=None),
    user_status: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None, alias="q", max_length=120),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    q = select(User)

    # Non-super_admin callers are scoped to their own tenant
    if token.role != "super_admin" and token.tenant_id:
        q = q.where(User.tenant_id == token.tenant_id)

    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.where(or_(User.full_name.ilike(term), User.email.ilike(term)))

    if role:
        try:
            q = q.where(User.role == Role(role))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {role}")

    if user_status:
        try:
            q = q.where(User.status == AccountStatus(user_status))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid status: {user_status}")

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(User.created_at.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    result = await db.execute(q)
    users = result.scalars().all()

    return {
        "items": [UserRow.model_validate(u) for u in users],
        "total": total,
        "page": page,
        "pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    body: CreateAdminRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    if body.role not in _CREATABLE_ROLES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Role must be one of: {', '.join(sorted(_CREATABLE_ROLES))}",
        )

    if body.staff_position is not None and body.staff_position not in STAFF_POSITIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"staff_position must be one of: {', '.join(sorted(STAFF_POSITIONS))}",
        )

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalars().first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")

    if await pwd_svc.check_pwned(body.password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password found in breach database")

    user = User(
        full_name=body.full_name,
        email=body.email,
        password_hash=pwd_svc.hash_password(body.password),
        role=Role(body.role),
        status=AccountStatus.active,
        email_verified=True,
        tenant_id=body.tenant_id,
        staff_position=body.staff_position,
    )
    db.add(user)
    await db.flush()
    await audit_svc.log_event(
        db, "admin_user_created", user.id, get_ip(request),
        {"created_by": str(token.user_id), "role": body.role},
    )
    return UserRow.model_validate(user)


@router.patch("/{user_id}/tenant")
async def update_user_tenant(
    user_id: uuid.UUID,
    body: UpdateTenantRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    from app.models.tenant import Tenant
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == body.tenant_id))
    if not tenant_result.scalars().first():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    user.tenant_id = body.tenant_id
    await audit_svc.log_event(
        db, "user_tenant_changed", user.id, get_ip(request),
        {"by": str(token.user_id), "new_tenant_id": str(body.tenant_id)},
    )
    return UserRow.model_validate(user)


@router.patch("/{user_id}/role")
async def update_user_role(
    user_id: uuid.UUID,
    body: UpdateRoleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    if body.role not in _ASSIGNABLE_ROLES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Role must be one of: {', '.join(sorted(_ASSIGNABLE_ROLES))}",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == token.user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role")

    user.role = Role(body.role)
    await audit_svc.log_event(
        db, "user_role_changed", user.id, get_ip(request),
        {"by": str(token.user_id), "new_role": body.role},
    )
    return UserRow.model_validate(user)


@router.patch("/{user_id}/position")
async def update_user_position(
    user_id: uuid.UUID,
    body: UpdatePositionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    if body.staff_position is not None and body.staff_position not in STAFF_POSITIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"staff_position must be one of: {', '.join(sorted(STAFF_POSITIONS))}",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    # Non-super_admin callers can only act within their own tenant; 404 (not 403)
    # so the existence of cross-tenant users is not leaked.
    if token.role != "super_admin" and (
        not token.tenant_id or user.tenant_id != token.tenant_id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role not in (Role.admin, Role.moderator):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Staff position can only be assigned to admin or moderator users",
        )

    user.staff_position = body.staff_position
    await audit_svc.log_event(
        db, "user_position_changed", user.id, get_ip(request),
        {"by": str(token.user_id), "new_position": body.staff_position},
    )
    return UserRow.model_validate(user)


@router.patch("/{user_id}/status")
async def update_user_status(
    user_id: uuid.UUID,
    body: UpdateStatusRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("admin", "moderator")),
):
    allowed = {"active", "suspended"}
    if body.status not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Status must be one of: {', '.join(sorted(allowed))}",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    # Non-super_admin callers can only act within their own tenant; 404 (not 403)
    # so the existence of cross-tenant users is not leaked.
    if token.role != "super_admin" and (
        not token.tenant_id or user.tenant_id != token.tenant_id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == token.user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cannot change your own status")

    user.status = AccountStatus(body.status)
    await audit_svc.log_event(
        db, "user_status_changed", user.id, get_ip(request),
        {"by": str(token.user_id), "new_status": body.status},
    )
    return UserRow.model_validate(user)
