"""
Stage 2 — Contextual Hybrid Retrieval + Cross-Encoder Reranking.

Pipeline per query:
  dense (multilingual embed, both lang variants)
  + sparse (contextual BM25 with synonym expansion, both lang variants)
  → RRF merge (60/40 dense/sparse)
  → cross-encoder rerank (CENTRAL — runs on every path)
"""
import logging
from app.ai.models import RetrievedChunk, QueryAnalysis
from app.ai import embeddings, vector_store, bm25_index

logger = logging.getLogger(__name__)


# ── Reciprocal Rank Fusion ───────────────────────────────────────

def rrf_merge(
    results_a: list[RetrievedChunk],
    results_b: list[RetrievedChunk],
    k: int = 60,
) -> list[RetrievedChunk]:
    """Merge two ranked lists with Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    by_id: dict[str, RetrievedChunk] = {}

    for rank, chunk in enumerate(results_a):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank + 1)
        by_id[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(results_b):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank + 1)
        by_id[chunk.chunk_id] = chunk

    ranked = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    merged = []
    for cid in ranked:
        chunk = by_id[cid].model_copy()
        chunk.score = scores[cid]
        merged.append(chunk)
    return merged


# ── Metadata filter builder ──────────────────────────────────────

def _build_where(analysis: QueryAnalysis) -> dict | None:
    """Translate query analysis into a ChromaDB metadata filter."""
    conditions: list[dict] = []

    if not analysis.historical_law:
        conditions.append({"amendment_status": {"$eq": "current"}})

    hint = analysis.entities.get("jurisdiction_hint", "national")
    if hint == "campus":
        # Campus queries can hit both campus-scoped and national docs
        conditions.append({"tenant_scope": {"$in": ["diu", "national"]}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


# ── Cross-encoder reranking (CENTRAL) ───────────────────────────

def rerank_chunks(
    query: str,
    chunks: list[RetrievedChunk],
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """
    Cross-encoder reranker — the single highest-leverage retrieval step.
    Runs on every path (medium and hard) and again after corrective web merge.
    """
    if not chunks:
        return []
    passages = [c.text[:512] for c in chunks]  # truncate to avoid OOM
    scores = embeddings.rerank(query, passages)
    scored = [(chunk, score) for chunk, score in zip(chunks, scores)]
    scored.sort(key=lambda x: x[1], reverse=True)
    result = []
    for chunk, score in scored[:top_k]:
        c = chunk.model_copy()
        c.score = float(score)
        result.append(c)
    return result


# ── Main retrieval entry point ───────────────────────────────────

async def retrieve(
    query: str,
    query_en: str,
    query_bn: str,
    analysis: QueryAnalysis,
    n_candidates: int = 20,
    namespace: str = "national",
) -> list[RetrievedChunk]:
    """
    Hybrid contextual retrieval over contextual chunks.
    Dense: paraphrase-multilingual-mpnet-base-v2 over both language rewrites.
    Sparse: contextual BM25 with Bangla/English synonym expansion, both rewrites.
    Merge: RRF with 60/40 dense/sparse bias.
    """
    where = _build_where(analysis)

    # ── Dense retrieval ──────────────────────────────────────────
    queries_to_embed = list({query_en, query_bn} - {""})
    all_embeddings = embeddings.embed(queries_to_embed) if queries_to_embed else None

    dense_combined: list[RetrievedChunk] = []
    if all_embeddings:
        for emb in all_embeddings:
            hits = vector_store.query_dense(
                query_embedding=emb,
                n_results=n_candidates,
                where=where,
                namespace=namespace,
            )
            dense_combined = rrf_merge(dense_combined, hits) if dense_combined else hits

    # ── Sparse retrieval ────────────────────────────────────────
    bm25_en = bm25_index.query_bm25(query_en, n_results=n_candidates, namespace=namespace)
    bm25_bn = (
        bm25_index.query_bm25(query_bn, n_results=n_candidates, namespace=namespace)
        if query_bn and query_bn != query_en else []
    )
    bm25_combined = rrf_merge(bm25_en, bm25_bn) if bm25_bn else bm25_en

    # ── 60/40 RRF merge ─────────────────────────────────────────
    if dense_combined and bm25_combined:
        # Weight by taking top-60% dense + top-40% sparse before RRF
        n_dense = max(1, int(n_candidates * 0.6))
        n_sparse = max(1, int(n_candidates * 0.4))
        combined = rrf_merge(dense_combined[:n_dense], bm25_combined[:n_sparse])
    elif dense_combined:
        combined = dense_combined
    else:
        combined = bm25_combined

    logger.debug(
        "Retrieved: dense=%d sparse=%d merged=%d",
        len(dense_combined), len(bm25_combined), len(combined),
    )
    return combined[:n_candidates]
