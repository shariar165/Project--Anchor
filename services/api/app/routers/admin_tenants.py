import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import require_role, TokenData
from app.models.tenant import Tenant, TenantEmailDomain
from app.models.user import User, Role, AccountStatus
from app.services import password as pwd_svc, audit as audit_svc
from app.services.device import get_ip

router = APIRouter(prefix="/v1/super-admin/tenants", tags=["admin-tenants"])

_VALID_TIERS = {"pilot", "active"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class DomainOut(BaseModel):
    id: uuid.UUID
    domain: str

    model_config = {"from_attributes": True}


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    active: bool
    status: str
    tier: str
    country: Optional[str] = None
    contact_name: Optional[str] = None
    vector_namespace: Optional[str] = None
    domains: list[DomainOut] = []
    user_count: int = 0
    created_at: Optional[datetime] = None


class InitialAdmin(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8)


class OnboardRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100)
    email_domains: list[str] = Field(min_length=1)
    tier: str = "active"
    country: Optional[str] = "Bangladesh"
    contact_name: Optional[str] = None
    vector_namespace: Optional[str] = None
    initial_admin: InitialAdmin

    @field_validator("slug")
    @classmethod
    def _norm_slug(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("slug must not be empty")
        return v

    @field_validator("tier")
    @classmethod
    def _check_tier(cls, v: str) -> str:
        v = (v or "active").strip().lower()
        if v not in _VALID_TIERS:
            raise ValueError(f"tier must be one of: {', '.join(sorted(_VALID_TIERS))}")
        return v


class UpdateTenantRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    tier: Optional[str] = None
    country: Optional[str] = None
    contact_name: Optional[str] = None
    vector_namespace: Optional[str] = None
    active: Optional[bool] = None

    @field_validator("tier")
    @classmethod
    def _check_tier(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if v not in _VALID_TIERS:
            raise ValueError(f"tier must be one of: {', '.join(sorted(_VALID_TIERS))}")
        return v


class AddDomainRequest(BaseModel):
    domain: str = Field(min_length=1, max_length=253)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _derive_status(tenant: Tenant) -> str:
    if not tenant.active:
        return "Suspended"
    return "Pilot" if (tenant.tier or "active") == "pilot" else "Active"


def _normalize_domain(raw: str) -> str:
    d = raw.strip().lower().lstrip("@")
    if not d or "." not in d:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid email domain: {raw}")
    return d


def _to_out(tenant: Tenant, user_count: int) -> TenantOut:
    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        active=tenant.active,
        status=_derive_status(tenant),
        tier=tenant.tier or "active",
        country=tenant.country,
        contact_name=tenant.contact_name,
        vector_namespace=tenant.vector_namespace,
        domains=[DomainOut.model_validate(d) for d in tenant.email_domains],
        user_count=user_count,
        created_at=tenant.created_at,
    )


async def _user_counts(db: AsyncSession) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        select(User.tenant_id, func.count())
        .where(User.tenant_id.is_not(None))
        .group_by(User.tenant_id)
    )
    return {tid: cnt for tid, cnt in rows.all()}


async def _get_tenant_or_404(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    result = await db.execute(
        select(Tenant).options(selectinload(Tenant.email_domains)).where(Tenant.id == tenant_id)
    )
    tenant = result.scalars().first()
    if not tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("")
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    result = await db.execute(
        select(Tenant)
        .options(selectinload(Tenant.email_domains))
        .order_by(Tenant.created_at.desc())
    )
    tenants = result.scalars().all()
    counts = await _user_counts(db)
    return {"items": [_to_out(t, counts.get(t.id, 0)) for t in tenants]}


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    tenant = await _get_tenant_or_404(db, tenant_id)
    user_count = await db.scalar(
        select(func.count()).select_from(User).where(User.tenant_id == tenant_id)
    )
    return _to_out(tenant, user_count or 0)


@router.post("", status_code=status.HTTP_201_CREATED)
async def onboard_tenant(
    body: OnboardRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    domains = [_normalize_domain(d) for d in body.email_domains]
    if len(set(domains)) != len(domains):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Duplicate email domains in request")

    # Uniqueness checks
    if (await db.execute(select(Tenant).where(Tenant.slug == body.slug))).scalars().first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Slug already in use: {body.slug}")

    existing_domain = (
        await db.execute(select(TenantEmailDomain).where(TenantEmailDomain.domain.in_(domains)))
    ).scalars().first()
    if existing_domain:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Email domain already in use: {existing_domain.domain}"
        )

    if (await db.execute(select(User).where(User.email == body.initial_admin.email))).scalars().first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Admin email already registered")

    if await pwd_svc.check_pwned(body.initial_admin.password):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password found in breach database"
        )

    tenant = Tenant(
        name=body.name,
        slug=body.slug,
        active=True,
        tier=body.tier,
        country=body.country,
        contact_name=body.contact_name,
        vector_namespace=(body.vector_namespace or body.slug),
    )
    db.add(tenant)
    await db.flush()  # assign tenant.id

    for d in domains:
        db.add(TenantEmailDomain(tenant_id=tenant.id, domain=d))

    admin = User(
        full_name=body.initial_admin.full_name,
        email=body.initial_admin.email,
        password_hash=pwd_svc.hash_password(body.initial_admin.password),
        role=Role.admin,
        status=AccountStatus.active,
        email_verified=True,
        tenant_id=tenant.id,
    )
    db.add(admin)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Tenant or admin conflicts with an existing record")

    await audit_svc.log_event(
        db, "tenant_onboarded", token.user_id, get_ip(request),
        {"tenant_id": str(tenant.id), "slug": tenant.slug, "admin_email": admin.email},
    )

    await db.refresh(tenant, attribute_names=["email_domains"])
    return _to_out(tenant, 1)


@router.patch("/{tenant_id}")
async def update_tenant(
    tenant_id: uuid.UUID,
    body: UpdateTenantRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    tenant = await _get_tenant_or_404(db, tenant_id)
    changes: dict = {}
    for field in ("name", "tier", "country", "contact_name", "vector_namespace", "active"):
        val = getattr(body, field)
        if val is not None:
            setattr(tenant, field, val)
            changes[field] = val

    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    await db.flush()
    await audit_svc.log_event(
        db, "tenant_updated", token.user_id, get_ip(request),
        {"tenant_id": str(tenant.id), "changes": changes},
    )
    user_count = await db.scalar(
        select(func.count()).select_from(User).where(User.tenant_id == tenant_id)
    )
    return _to_out(tenant, user_count or 0)


@router.post("/{tenant_id}/domains", status_code=status.HTTP_201_CREATED)
async def add_domain(
    tenant_id: uuid.UUID,
    body: AddDomainRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    tenant = await _get_tenant_or_404(db, tenant_id)
    domain = _normalize_domain(body.domain)

    if (await db.execute(select(TenantEmailDomain).where(TenantEmailDomain.domain == domain))).scalars().first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Email domain already in use: {domain}")

    db.add(TenantEmailDomain(tenant_id=tenant.id, domain=domain))
    await db.flush()
    await audit_svc.log_event(
        db, "tenant_domain_added", token.user_id, get_ip(request),
        {"tenant_id": str(tenant.id), "domain": domain},
    )
    await db.refresh(tenant, attribute_names=["email_domains"])
    user_count = await db.scalar(
        select(func.count()).select_from(User).where(User.tenant_id == tenant_id)
    )
    return _to_out(tenant, user_count or 0)


@router.delete("/{tenant_id}/domains/{domain_id}")
async def remove_domain(
    tenant_id: uuid.UUID,
    domain_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    result = await db.execute(
        select(TenantEmailDomain).where(
            TenantEmailDomain.id == domain_id, TenantEmailDomain.tenant_id == tenant_id
        )
    )
    dom = result.scalars().first()
    if not dom:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Domain not found")

    remaining = await db.scalar(
        select(func.count()).select_from(TenantEmailDomain).where(TenantEmailDomain.tenant_id == tenant_id)
    )
    if (remaining or 0) <= 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="A tenant must keep at least one email domain"
        )

    domain_value = dom.domain
    await db.delete(dom)
    await db.flush()
    await audit_svc.log_event(
        db, "tenant_domain_removed", token.user_id, get_ip(request),
        {"tenant_id": str(tenant_id), "domain": domain_value},
    )
    return {"ok": True}


@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    tenant = await _get_tenant_or_404(db, tenant_id)
    user_count = await db.scalar(
        select(func.count()).select_from(User).where(User.tenant_id == tenant_id)
    )
    if user_count:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Cannot delete a tenant with {user_count} attached user(s); suspend it instead",
        )

    slug = tenant.slug
    await db.delete(tenant)  # email domains cascade
    await db.flush()
    await audit_svc.log_event(
        db, "tenant_deleted", token.user_id, get_ip(request),
        {"tenant_id": str(tenant_id), "slug": slug},
    )
    return {"ok": True}
