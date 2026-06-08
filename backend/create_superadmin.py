"""
Create or reset the platform super admin account.

Usage (from backend/ directory, venv activated):
    python create_superadmin.py <password>

Example:
    python create_superadmin.py MySecurePass!99
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select

SUPER_ADMIN_EMAIL = "teamaivion@gmail.com"
SUPER_ADMIN_NAME = "AiVion Platform Team"


async def main(password: str) -> None:
    from app.config import get_settings
    from app.models.user import User, Role, AccountStatus
    from app.services.password import hash_password

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(User).where(User.email == SUPER_ADMIN_EMAIL)
        )
        user = result.scalars().first()

        if user:
            user.password_hash = hash_password(password)
            user.role = Role.super_admin
            user.status = AccountStatus.active
            user.email_verified = True
            user.full_name = SUPER_ADMIN_NAME
            print(f"[updated] {SUPER_ADMIN_EMAIL} — role set to super_admin")
        else:
            user = User(
                id=uuid.uuid4(),
                full_name=SUPER_ADMIN_NAME,
                email=SUPER_ADMIN_EMAIL,
                password_hash=hash_password(password),
                role=Role.super_admin,
                status=AccountStatus.active,
                email_verified=True,
            )
            session.add(user)
            print(f"[created] {SUPER_ADMIN_EMAIL} — super_admin account ready")

        await session.commit()

    await engine.dispose()
    print("Done. You can now sign in at the Super Admin Console.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {os.path.basename(__file__)} <password>")
        sys.exit(1)

    pwd = sys.argv[1]
    if len(pwd) < 8:
        print("Error: password must be at least 8 characters")
        sys.exit(1)

    asyncio.run(main(pwd))
