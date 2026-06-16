"""
Seed a realistic DIU Software-Engineering scenario into the live database so the
timetable generator can be exercised end-to-end through the Admin UI
(Data → Schedule → Rules → Generate → Grid → Publish).

Creates ~115 faculty, 9 batches (40–48) × 8 sections (A–H) with lab groups, the
real per-batch course lists (one lab course per batch), the real theory/lab room
inventory, a round-robin eligibility map, a schedule config, and offerings —
all under a single term (default "Demo Term").

Usage (from services/api, venv active):
    python seed_timetable_demo.py                 # seed (fails if seed term exists)
    python seed_timetable_demo.py --wipe          # clear ALL timetable tables first, then seed
    python seed_timetable_demo.py --slots 6       # fewer time slots (tighter)
    python seed_timetable_demo.py --batches 3     # only the newest 3 batches

NOTE: --wipe truncates every tt_* table and deletes prior seed faculty accounts
(those at the seed email domain). These tables are owned by the generator, so this
is safe in a dev/demo database. Do NOT --wipe a database with real timetable data.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

SEED_TERM_NAME = "Demo Term"
SEED_EMAIL_DOMAIN = "seed.diu.edu.bd"


async def _wipe(session: AsyncSession) -> None:
    from app.models.timetable import (
        TimetableEntry, TimetableSolveJob, TimetableCourseOffering,
        TimetableTeacherEligibility, TimetableLabGroup, TimetableSection,
        TimetableStudentEnrollment, TimetableScheduleConfig, TimetableConstraint,
        TimetableBatch, TimetableCourse, TimetableRoom, TimetableFacultyProfile,
        TimetableTerm,
    )
    from app.models.user import User

    # FK-safe order: children before parents.
    for model in (
        TimetableEntry, TimetableSolveJob, TimetableCourseOffering,
        TimetableTeacherEligibility, TimetableStudentEnrollment, TimetableLabGroup,
        TimetableSection, TimetableScheduleConfig, TimetableConstraint,
        TimetableBatch, TimetableCourse, TimetableRoom, TimetableFacultyProfile,
        TimetableTerm,
    ):
        await session.execute(delete(model))
    await session.execute(delete(User).where(User.email.like(f"%@{SEED_EMAIL_DOMAIN}")))
    await session.commit()
    print("[wipe] cleared all tt_* tables and seed faculty accounts")


async def main(args) -> None:
    from app.config import get_settings
    from app.models.timetable import TimetableTerm
    from app.services.timetable_seed_data import seed_scenario

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    async with AsyncSession(engine) as session:
        if args.wipe:
            await _wipe(session)

        existing = (await session.execute(
            select(TimetableTerm).where(TimetableTerm.name == SEED_TERM_NAME)
        )).scalars().first()
        if existing:
            print(f"Error: a term named {SEED_TERM_NAME!r} already exists. "
                  f"Re-run with --wipe to reset, or delete it from the Admin UI.")
            await engine.dispose()
            sys.exit(1)

        info = await seed_scenario(
            session,
            n_batches=args.batches,
            n_slots=args.slots,
            eligible_per_course=args.eligible,
            term_name=SEED_TERM_NAME,
        )

    await engine.dispose()
    print("\n[done] seeded scenario:")
    for k, v in info.items():
        print(f"  {k:16} = {v}")
    print(
        "\nOpen the Admin UI → Timetable Generator. The active term is "
        f"{SEED_TERM_NAME!r}. Go to the Generate tab and run the solver."
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Seed the timetable demo scenario.")
    p.add_argument("--wipe", action="store_true", help="clear all tt_* tables + seed faculty first")
    p.add_argument("--batches", type=int, default=9, help="number of batches (newest first), 1-9")
    p.add_argument("--slots", type=int, default=8, help="time slots per day, 1-8")
    p.add_argument("--eligible", type=int, default=4, help="eligible teachers per course")
    asyncio.run(main(p.parse_args()))
