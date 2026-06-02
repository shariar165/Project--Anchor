from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.database import engine
from app.redis import get_redis, close_redis
from app.limiter import limiter
from app.routers import auth, mfa, sessions, tracking
from app.routers import ai as ai_router
from app.routers import alerts as alerts_router
from app.routers import admin_alerts as admin_alerts_router
from app.routers import applications as applications_router
from app.routers import feed as feed_router
from app.routers import feed_admin as feed_admin_router
from app.routers import filings as filings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: warm Redis + auto-load sample corpus into BM25 if empty
    get_redis()
    try:
        from app.ai.sample_corpus import load_sample_corpus
        from app.ai import vector_store, bm25_index
        if vector_store.count("national") == 0 and bm25_index.index_count("national") == 0:
            import asyncio
            asyncio.create_task(load_sample_corpus(generate_prefixes=False))
    except Exception:
        pass
    try:
        from app.database import AsyncSessionLocal
        from app.services.filing_svc import seed_templates
        async with AsyncSessionLocal() as _db:
            await seed_templates(_db)
    except Exception:
        pass
    yield
    # Shutdown: close Redis
    await close_redis()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Anchor AI API",
        version="1.0.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(auth.router)
    app.include_router(mfa.router)
    app.include_router(sessions.router)
    app.include_router(tracking.router)
    app.include_router(ai_router.router)
    app.include_router(alerts_router.router)
    app.include_router(admin_alerts_router.router)
    app.include_router(applications_router.router)
    app.include_router(feed_router.router)
    app.include_router(feed_admin_router.router)
    app.include_router(filings_router.router)

    # Serve uploaded feed attachments in dev
    from fastapi.staticfiles import StaticFiles
    from pathlib import Path as _Path
    _upload_dir = _Path(__file__).parent.parent / "uploads" / "feed"
    _upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads/feed", StaticFiles(directory=str(_upload_dir)), name="feed_uploads")

    @app.get("/health", tags=["health"])
    async def health():
        from sqlalchemy import text
        from app.database import AsyncSessionLocal
        db_ok = False
        redis_ok = False
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            pass
        try:
            redis = get_redis()
            await redis.ping()
            redis_ok = True
        except Exception:
            pass
        status = "ok" if db_ok and redis_ok else "degraded"
        return {"status": status, "db": "ok" if db_ok else "error", "redis": "ok" if redis_ok else "error"}

    return app


app = create_app()
