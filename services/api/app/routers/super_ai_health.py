"""Super-admin AI engine health.

Route: GET /v1/super-admin/ai-health
Auth: super_admin role only.

Aggregates live signals from the RAG microservice (component status + per-namespace
corpus stats) with this process's host metrics. Reports only real data — when RAG
is unreachable the endpoint still returns 200 with a degraded payload so the
dashboard renders instead of erroring.
"""
import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.limiter import limiter
from app.models.audit import AuditLog
from app.services.rag_proxy import rag_url, rag_headers
from app.services.sys_metrics import host_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/super-admin/ai-health", tags=["super-admin-ai-health"])


async def _rag_get(path: str) -> tuple[dict | None, str | None]:
    """GET a RAG endpoint. Returns (json, error). error is set when unreachable."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{rag_url()}{path}", headers=rag_headers())
            resp.raise_for_status()
            return resp.json(), None
    except httpx.ConnectError:
        return None, "unavailable"
    except httpx.HTTPStatusError as e:
        return None, f"http {e.response.status_code}"
    except Exception as e:  # timeout, JSON decode, etc.
        logger.warning("RAG health probe failed for %s: %s", path, e)
        return None, "error"


@router.get("")
@limiter.limit("60/minute")
async def ai_health(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    # 1. RAG component status (pipeline / embedder / chromadb / ollama)
    health, herr = await _rag_get("/health")
    if health is None:
        components = {
            "pipeline": herr or "unavailable",
            "embedder": herr or "unavailable",
            "chromadb": herr or "unavailable",
            "gemini": herr or "unavailable",
            "ollama": herr or "unavailable",
        }
        rag_reachable = False
    else:
        components = {
            "pipeline": health.get("pipeline", "unknown"),
            "embedder": health.get("embedder", "unknown"),
            "chromadb": health.get("chromadb", "unknown"),
            "gemini": health.get("gemini", "unknown"),
            "ollama": health.get("ollama", "unknown"),
        }
        rag_reachable = True

    # 2. Per-namespace corpus stats (real document/chunk counts replace mock table)
    corpus, cerr = await _rag_get("/corpus/stats")
    namespaces = []
    if corpus:
        for ns, stats in corpus.items():
            if not isinstance(stats, dict):
                continue
            namespaces.append({
                "namespace": ns,
                "documents": stats.get("documents"),
                "dense_chunks": stats.get("dense_chunks"),
                "sparse_chunks": stats.get("sparse_chunks"),
            })
        namespaces.sort(key=lambda n: n["namespace"])

    # 3. AI usage from the audit log (only if such events are recorded — otherwise
    #    omit rather than fabricate). ai_chat events are logged by routers/ai.py.
    since = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    chat_24h = (await db.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.event_type == "ai_chat",
            AuditLog.created_at >= since,
        )
    )).scalar() or 0

    return {
        "rag_reachable": rag_reachable,
        "components": components,
        "namespaces": namespaces,
        "corpus_error": cerr,
        "usage": {
            "ai_chat_24h": int(chat_24h),
            "tracked": True,
        },
        "host": host_metrics(),
        "checked_at": datetime.now(tz=timezone.utc).isoformat(),
    }
