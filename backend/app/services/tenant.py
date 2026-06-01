from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tenant import Tenant, TenantEmailDomain


async def resolve_by_email_domain(db: AsyncSession, email: str) -> Tenant | None:
    domain = email.split("@")[-1].lower()
    result = await db.execute(
        select(Tenant)
        .join(TenantEmailDomain, TenantEmailDomain.tenant_id == Tenant.id)
        .where(TenantEmailDomain.domain == domain, Tenant.active == True)
    )
    return result.scalars().first()
