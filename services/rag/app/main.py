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
from typing import Any

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
    if not settings.disable_ai_warmup:
        try:
            from app.pipeline.sample_corpus import load_sample_corpus
            asyncio.create_task(load_sample_corpus())
        except Exception as e:
            logger.warning("AI warmup skipped: %s", e)
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
    allow_methods=["POST", "GET"],
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
    """Load the built-in sample legal corpus into ChromaDB (dev/demo setup)."""
    _verify_internal(x_internal_secret)
    try:
        from app.pipeline.sample_corpus import load_sample_corpus
        count = await load_sample_corpus()
        return {"status": "ok", "chunks_loaded": count}
    except Exception as e:
        logger.error("Ingest error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health() -> dict[str, Any]:
    """Check RAG subsystem component availability."""
    from app.config import get_settings
    settings = get_settings()

    status: dict[str, Any] = {"pipeline": "ok"}

    if settings.disable_ai_warmup:
        status["embedder"] = "disabled"
        status["chromadb"] = "disabled"
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
        client = vs_mod._get_client()
        status["chromadb"] = "ok" if client is not None else "unavailable"
    except Exception as e:
        status["chromadb"] = f"error: {e}"

    try:
        from app.pipeline import llm_client
        available = await llm_client._check_availability()
        status["ollama"] = "ok" if available else "unavailable"
    except Exception as e:
        status["ollama"] = f"error: {e}"

    return status
