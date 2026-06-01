"""
AI Legal Companion router — /ai/chat and supporting endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, Request
from app.limiter import limiter
from app.ai.models import ChatRequest, ChatResponse
from app.ai import pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    body: ChatRequest,
) -> ChatResponse:
    """
    Anchor AI Legal Companion — full 7-stage RAG pipeline.

    Stages:
      0 Safety pre-flight (emergency / crisis / injection detection)
      1 Query understanding (intent + characterizer + entity extraction)
      2 Contextual hybrid retrieval (dense + BM25 + RRF merge)
      3 Corrective RAG (confidence gate + web search + rerank)
      4 Generation (legal reasoning scaffold with citation grounding)
      5 Claim-level verification
      6 Output adaptation (language + register + citations + disclaimer)
    """
    try:
        return await pipeline.run(body)
    except Exception as e:
        logger.error("Pipeline error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="AI pipeline error — please try again.")


@router.post("/ingest", include_in_schema=False)
async def ingest_sample(request: Request):
    """
    Load the built-in sample legal corpus (dev/demo setup).
    Not exposed in production schema.
    """
    try:
        from app.ai.sample_corpus import load_sample_corpus
        count = await load_sample_corpus(generate_prefixes=False)
        return {"status": "ok", "chunks_loaded": count}
    except Exception as e:
        logger.error("Ingest error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def ai_health():
    """Check AI subsystem component availability."""
    from app.ai import embeddings, vector_store, bm25_index, llm_client

    embedder_ok = embeddings._get_embedder() is not None
    reranker_ok = embeddings._get_reranker() is not None
    chroma_ok = vector_store._get_client() is not None
    ollama_ok = await llm_client._check_availability()

    national_count = vector_store.count("national")
    diu_count = vector_store.count("diu")
    bm25_national = bm25_index.index_count("national")
    bm25_diu = bm25_index.index_count("diu")

    return {
        "pipeline": "ok",
        "embedder": "ok" if embedder_ok else "unavailable (stub mode)",
        "reranker": "ok" if reranker_ok else "unavailable (score passthrough)",
        "chromadb": "ok" if chroma_ok else "unavailable",
        "ollama": "ok" if ollama_ok else "unavailable (stub mode)",
        "corpus": {
            "national_chunks": national_count,
            "diu_chunks": diu_count,
            "bm25_national": bm25_national,
            "bm25_diu": bm25_diu,
        },
    }
