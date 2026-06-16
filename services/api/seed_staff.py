"""
Seed campus application-chain staff (dean, accounts, etc.) for testing the
Apply-Formally approval flow.

Usage (from services/api, venv active):
    python seed_staff.py                 # seed default dean + accounts admins
    python seed_staff.py <password>      # same, with a custom password

Creates/updates admin users with a staff_position. Safe to re-run — existing
accounts are updated in place. Login at the University Admin console with the
printed credentials.
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# (email, full name, role, staff_position)
STAFF = [
    ("mentor@diu.edu.bd",   "Mentor Teacher (DIU)",  "admin", "mentor"),
    ("depthead@diu.edu.bd", "Department Head (DIU)", "admin", "department_head"),
    ("dean@diu.edu.bd",     "Dr. Dean (DIU)",        "admin", "dean"),
    ("accounts@diu.edu.bd", "Accounts Office (DIU)", "admin", "accounts"),
]


async def main(password: str) -> None:
    from app.config import get_settings
    from app.models.user import User, Role, AccountStatus, STAFF_POSITIONS
    from app.services.password import hash_password

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    async with AsyncSession(engine) as session:
        for email, name, role, position in STAFF:
            assert position in STAFF_POSITIONS, position
            user = (await session.execute(
                select(User).where(User.email == email)
            )).scalars().first()

            if user:
                user.full_name = name
                user.role = Role(role)
                user.staff_position = position
                user.status = AccountStatus.active
                user.email_verified = True
                user.mfa_enabled = False
                user.password_hash = hash_password(password)
                print(f"[updated] {email:24} role={role} position={position}")
            else:
                session.add(User(
                    id=uuid.uuid4(),
                    full_name=name,
                    email=email,
                    password_hash=hash_password(password),
                    role=Role(role),
                    status=AccountStatus.active,
                    email_verified=True,
                    staff_position=position,
                ))
                print(f"[created] {email:24} role={role} position={position}")

        await session.commit()

    await engine.dispose()
    print(f"\nDone. Password for all seeded staff: {password}")
    print("Sign in at the University Admin console; the Applications queue shows each stage.")


if __name__ == "__main__":
    pwd = sys.argv[1] if len(sys.argv) > 1 else "StaffPass!99"
    if len(pwd) < 8:
        print("Error: password must be at least 8 characters")
        sys.exit(1)
    asyncio.run(main(pwd))
