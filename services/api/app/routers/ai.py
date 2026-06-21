"""
AI Legal Companion router — /ai/chat and supporting endpoints.
Proxies to the internal RAG service (services/rag) over HTTP.
JWT auth is enforced here at the API layer; RAG never sees user tokens.
"""
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from app.limiter import limiter
from app.deps import get_current_user, require_role
from app.services.rag_proxy import rag_url as _rag_url, rag_headers as _rag_headers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat")
@limiter.limit("30/minute")
async def chat(
    request: Request,
    body: dict[str, Any],
    _user=Depends(get_current_user),
) -> dict[str, Any]:
    """
    Anchor AI Legal Companion — proxies to the RAG service.

    Stages (run inside services/rag):
      0 Safety pre-flight (emergency / crisis / injection detection)
      1 Query understanding (intent + entity extraction)
      2 Contextual hybrid retrieval (dense + BM25 + RRF merge)
      3 Corrective RAG (confidence gate + web search fallback)
      4 Generation (legal reasoning scaffold with citation grounding)
      5 Claim-level verification
      6 Output adaptation (language + register + citations + disclaimer)
    """
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{_rag_url()}/chat",
                json=body,
                headers=_rag_headers(),
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable.")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        logger.error("RAG proxy error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="AI pipeline error — please try again.")


@router.post("/ingest", include_in_schema=False)
async def ingest_sample(
    request: Request,
    _token=Depends(require_role("super_admin")),
) -> dict[str, Any]:
    """Proxy to RAG service sample-corpus reload. Super-admin only."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{_rag_url()}/ingest", headers=_rag_headers())
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable.")
    except Exception as e:
        logger.error("Ingest proxy error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def ai_health() -> dict[str, Any]:
    """Proxy health check to RAG service. Returns degraded status if RAG is unreachable."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{_rag_url()}/health", headers=_rag_headers())
            return resp.json()
    except httpx.ConnectError:
        return {"pipeline": "unavailable", "error": "RAG service unreachable"}
    except Exception as e:
        return {"pipeline": "unavailable", "error": str(e)}
