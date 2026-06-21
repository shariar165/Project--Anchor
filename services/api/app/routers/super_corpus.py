"""Super-admin legal corpus management.

Routes: /v1/super-admin/corpus
Auth: super_admin role only.

Thin proxy to the internal RAG service (services/rag). ChromaDB is the source
of truth for the corpus, so the Core API keeps no registry table — it forwards
list/ingest/delete to RAG after enforcing the super_admin JWT.
"""
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_role, TokenData
from app.limiter import limiter
from app.services.audit import log_event as audit_log
from app.services.device import get_ip
from app.services.rag_proxy import rag_url, rag_headers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/super-admin/corpus", tags=["super-admin-corpus"])


def _err(e: Exception) -> HTTPException:
    if isinstance(e, httpx.ConnectError):
        return HTTPException(status_code=503, detail="RAG service unavailable.")
    if isinstance(e, httpx.HTTPStatusError):
        return HTTPException(status_code=e.response.status_code, detail=str(e))
    logger.error("Corpus proxy error: %s", e, exc_info=True)
    return HTTPException(status_code=500, detail="Corpus operation failed.")


@router.get("/documents")
@limiter.limit("60/minute")
async def list_documents(
    request: Request,
    namespace: str = Query(default="national"),
    token: TokenData = Depends(require_role("super_admin")),
):
    """List corpus documents in a namespace (national | diu | tenant slug)."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{rag_url()}/corpus/documents",
                params={"namespace": namespace},
                headers=rag_headers(),
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise _err(e)


@router.get("/stats")
@limiter.limit("60/minute")
async def corpus_stats(
    request: Request,
    token: TokenData = Depends(require_role("super_admin")),
):
    """Per-namespace chunk/document counts."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{rag_url()}/corpus/stats", headers=rag_headers())
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise _err(e)


@router.post("/documents")
@limiter.limit("20/minute")
async def ingest_document(
    body: dict[str, Any],
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Ingest a custom document into the corpus. Indexing can take a few seconds."""
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{rag_url()}/corpus/ingest", json=body, headers=rag_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise _err(e)

    await audit_log(db, "corpus_document_ingested", token.user_id, get_ip(request), {
        "namespace": body.get("namespace", "national"),
        "title": body.get("title"),
        "document_id": data.get("document_id"),
        "chunks_loaded": data.get("chunks_loaded"),
    })
    await db.commit()
    return data


@router.delete("/documents/{document_id}")
@limiter.limit("20/minute")
async def delete_document(
    document_id: str,
    request: Request,
    namespace: str = Query(default="national"),
    db: AsyncSession = Depends(get_db),
    token: TokenData = Depends(require_role("super_admin")),
):
    """Delete a document's chunks from the corpus."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.delete(
                f"{rag_url()}/corpus/documents/{document_id}",
                params={"namespace": namespace},
                headers=rag_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise _err(e)

    await audit_log(db, "corpus_document_deleted", token.user_id, get_ip(request), {
        "namespace": namespace,
        "document_id": document_id,
        "chunks_removed": data.get("chunks_removed"),
    })
    await db.commit()
    return data
