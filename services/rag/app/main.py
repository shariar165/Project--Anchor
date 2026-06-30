"""
Anchor RAG Service — standalone FastAPI microservice.

Exposes the 7-stage legal RAG pipeline over HTTP.
This is an internal service — it is NOT exposed to the public internet directly.
All requests must include X-Internal-Secret matching the RAG_INTERNAL_SECRET env var.

The Core API (services/api) proxies /ai/chat here after enforcing JWT auth.
RAG never sees user JWTs — only the shared internal secret.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load services/rag/.env into the environment BEFORE anything reads os.environ
# (config.py captures OLLAMA_BASE_URL etc. at import time). Explicit path so it
# works no matter the launch cwd. On Railway there is no .env file and real env
# vars are already set — load_dotenv is then a harmless no-op.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

RAG_INTERNAL_SECRET = os.environ.get("RAG_INTERNAL_SECRET", "")


def _verify_internal(secret: str | None) -> None:
    """Reject requests that don't carry the shared internal secret."""
    if RAG_INTERNAL_SECRET and secret != RAG_INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import get_settings
    settings = get_settings()

    async def _startup():
        try:
            from app.pipeline.ingestion import rebuild_bm25_from_store
            # BM25 is in-memory, cheap, and needs NO ML model — always rebuild it
            # from the persisted vector store (including a store baked into the
            # image) so sparse retrieval works even when warmup is disabled.
            for ns in ("national", "diu"):
                rebuild_bm25_from_store(ns)
            # Re-embedding the sample corpus requires loading the embedder model.
            # On memory-constrained tiers (Railway 512 MB) set DISABLE_AI_WARMUP=true
            # and ship a prebuilt data/vectors store in the image: the service then
            # boots without loading any model and only loads it on the first query.
            if not settings.disable_ai_warmup:
                from app.pipeline.sample_corpus import load_sample_corpus
                await load_sample_corpus()
                for ns in ("national", "diu"):
                    rebuild_bm25_from_store(ns)
        except Exception as e:
            logger.warning("AI startup tasks skipped: %s", e)

    asyncio.create_task(_startup())
    yield


app = FastAPI(
    title="Anchor RAG Service",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_methods=["POST", "GET", "DELETE"],
    allow_headers=["X-Internal-Secret", "Content-Type"],
)


@app.post("/chat")
async def chat(
    body: dict[str, Any],
    x_internal_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Run the full 7-stage RAG pipeline. Body is passed through as-is."""
    _verify_internal(x_internal_secret)
    try:
        from app.pipeline.models import ChatRequest
        from app.pipeline import pipeline
        request = ChatRequest(**body)
        result = await pipeline.run(request)
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return dict(result)
    except Exception as e:
        logger.error("Pipeline error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="RAG pipeline error — please try again.")


@app.post("/ingest", include_in_schema=False)
async def ingest(
    x_internal_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Load the built-in sample legal corpus into the vector store (dev/demo setup)."""
    _verify_internal(x_internal_secret)
    try:
        from app.pipeline.sample_corpus import load_sample_corpus
        count = await load_sample_corpus()
        return {"status": "ok", "chunks_loaded": count}
    except Exception as e:
        logger.error("Ingest error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/corpus/documents")
async def corpus_documents(
    namespace: str = "national",
    x_internal_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """List corpus documents (grouped by document_id) for a namespace."""
    _verify_internal(x_internal_secret)
    from app.pipeline import vector_store
    return {"namespace": namespace, "documents": vector_store.list_documents(namespace)}


@app.get("/corpus/stats")
async def corpus_stats(
    x_internal_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Per-namespace chunk counts (dense store + sparse index)."""
    _verify_internal(x_internal_secret)
    from app.pipeline import vector_store, bm25_index
    out: dict[str, Any] = {}
    for ns in ("national", "diu"):
        out[ns] = {
            "dense_chunks": vector_store.count(ns),
            "sparse_chunks": bm25_index.index_count(ns),
            "documents": len(vector_store.list_documents(ns)),
        }
    return out


@app.post("/corpus/ingest")
async def corpus_ingest(
    body: dict[str, Any],
    x_internal_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Ingest a custom document into a namespace.

    Body: {namespace, title, document_type?, document_id?, metadata{}, text | chunks[]}
    Either `text` (auto-chunked) or a pre-split `chunks` list must be provided.
    """
    _verify_internal(x_internal_secret)
    try:
        import re
        import hashlib
        from app.pipeline.ingestion import ingest_document, chunk_text

        namespace = body.get("namespace", "national")
        title = (body.get("title") or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="title is required")

        # Deterministic id from the title so re-ingesting the same document
        # overwrites its chunks (upsert by chunk_id) instead of duplicating.
        # The hash suffix keeps it unique even for non-ASCII (e.g. Bangla)
        # titles that slugify to empty.
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
        digest = hashlib.md5(title.encode("utf-8")).hexdigest()[:8]
        document_id = body.get("document_id") or f"{namespace}-{slug}-{digest}".replace("--", "-")
        base_meta = dict(body.get("metadata") or {})
        base_meta.setdefault("document_id", document_id)
        base_meta.setdefault("document_type", body.get("document_type", "statute"))
        base_meta.setdefault("act_name", title)
        base_meta.setdefault("tenant_scope", namespace)
        base_meta.setdefault("language", body.get("language", "en"))

        raw_chunks = body.get("chunks")
        if raw_chunks:
            texts = [c if isinstance(c, str) else c.get("text", "") for c in raw_chunks]
        else:
            texts = chunk_text(body.get("text", ""))
        texts = [t for t in texts if t and t.strip()]
        if not texts:
            raise HTTPException(status_code=400, detail="No chunkable text provided")

        chunks = []
        for i, text in enumerate(texts):
            meta = dict(base_meta)
            cid = f"{document_id}-{i}"
            meta["chunk_id"] = cid
            chunks.append({
                "chunk_id": cid,
                "text": text,
                "metadata": meta,
                "document_title": title,
                "hierarchy": base_meta.get("section", ""),
                "effective_date": base_meta.get("effective_date", ""),
            })

        count = await ingest_document(chunks, namespace=namespace, generate_prefixes=True)
        return {"status": "ok", "document_id": document_id, "chunks_loaded": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Corpus ingest error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/corpus/documents/{document_id}")
async def corpus_delete(
    document_id: str,
    namespace: str = "national",
    x_internal_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Delete a document's chunks from a namespace and rebuild BM25."""
    _verify_internal(x_internal_secret)
    try:
        from app.pipeline import vector_store
        from app.pipeline.ingestion import rebuild_bm25_from_store

        removed = vector_store.delete_document(document_id, namespace)
        rebuild_bm25_from_store(namespace)
        return {"status": "ok", "document_id": document_id, "chunks_removed": removed}
    except Exception as e:
        logger.error("Corpus delete error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health() -> dict[str, Any]:
    """Check RAG subsystem component availability."""
    from app.config import get_settings
    settings = get_settings()

    status: dict[str, Any] = {"pipeline": "ok"}

    if settings.disable_ai_warmup:
        status["embedder"] = "disabled"
        status["vector_store"] = "disabled"
        status["gemini"] = "disabled"
        status["ollama"] = "disabled"
        return status

    try:
        from app.pipeline import embeddings as emb_mod
        embedder = emb_mod._get_embedder()
        status["embedder"] = "ok" if embedder is not None else "unavailable"
    except Exception as e:
        status["embedder"] = f"error: {e}"

    try:
        from app.pipeline import vector_store as vs_mod
        status["vector_store"] = "ok" if vs_mod.is_ready() else "unavailable"
    except Exception as e:
        status["vector_store"] = f"error: {e}"

    try:
        from app.pipeline import llm_client
        # Force a live re-probe: the availability flags are cached for the life of
        # the process, so a transient failure (e.g. ngrok tunnel briefly down at
        # startup) would otherwise pin /health to "unavailable" until restart.
        llm_client.reset_availability_cache()
        gemini_ok = await llm_client._check_gemini_availability()
        # "not configured" distinguishes "no API key set" from a key that fails.
        status["gemini"] = "ok" if gemini_ok else (
            "unavailable" if llm_client._gemini_key() else "not configured"
        )
        available = await llm_client._check_availability()
        status["ollama"] = "ok" if available else "unavailable"
    except Exception as e:
        status["ollama"] = f"error: {e}"

    return status
