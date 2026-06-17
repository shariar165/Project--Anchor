import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
from app.config import get_settings

logger = logging.getLogger(__name__)


def _make_engine():
    settings = get_settings()
    url = settings.database_url
    try:
        from sqlalchemy.engine.url import make_url
        u = make_url(url)
        logger.info("[DB] Connecting to: %s://%s:%s/%s", u.drivername, u.host, u.port, u.database)
    except Exception:
        logger.info("[DB] DATABASE_URL starts with: %s", url[:40] if url else "NOT SET")
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


engine = _make_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
