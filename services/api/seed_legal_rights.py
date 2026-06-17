"""
Seed the national-mode "Know your rights" legal-explainer corpus.

Usage (from services/api, venv active):
    python seed_legal_rights.py

Idempotent — inserts the curated corpus only if the legal_rights table is empty.
Safe to re-run. The same seed also runs automatically on API startup (lifespan).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


async def main() -> None:
    from app.config import get_settings
    from app.services.legal_rights_svc import seed_legal_rights

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    async with AsyncSession(engine) as session:
        inserted = await seed_legal_rights(session)

    await engine.dispose()
    if inserted:
        print(f"Done. Inserted {inserted} legal-rights entries.")
    else:
        print("legal_rights table already populated — nothing to do.")


if __name__ == "__main__":
    asyncio.run(main())
