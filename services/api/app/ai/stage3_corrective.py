"""
Stage 3 — Corrective RAG (RETAINED & CENTRAL).

Confidence gate with multi-signal scoring → web-search fallback when needed
→ re-merge with corpus docs → cross-encoder rerank again.

The corrective loop is the self-correction mechanism: it prevents generating
a confident answer off thin retrieval, and always re-runs the reranker on
the merged web+doc pool.
"""
import math
import logging
from app.ai.models import RetrievedChunk, QueryAnalysis
from app.ai import stage2_retrieval

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.70  # Below this → trigger web search
ABSOLUTE_FLOOR = 0.35        # Below this even after web → exit ramp


# ── Multi-signal confidence gate ────────────────────────────────

def compute_confidence(
    chunks: list[RetrievedChunk],
    analysis: QueryAnalysis,
) -> float:
    """
    Five-signal confidence score:
    1. Top-1 rerank score normalised via sigmoid
    2. Top-1 vs top-5 gap (clear winner → higher confidence)
    3. Entity coverage (do top chunks address query entities?)
    4. Contradiction flag (chunks disagree → lower confidence)
    5. Workflow availability bonus/penalty
    """
    if not chunks:
        return 0.0

    scores = [c.score for c in chunks]
    top1_raw = scores[0]

    # Sigmoid normalisation for cross-encoder logits (range roughly -10 to +10)
    def _sig(s: float) -> float:
        try:
            return 1.0 / (1.0 + math.exp(-s * 0.3))
        except OverflowError:
            return 0.0 if s < 0 else 1.0

    # If score is already in [0,1] (BM25 path / fallback), pass through
    top1_norm = _sig(top1_raw) if (top1_raw > 1.0 or top1_raw < 0) else top1_raw

    # Gap: large gap between top-1 and top-2 → clear winner
    gap_signal = 0.5
    if len(scores) >= 2:
        raw_gap = scores[0] - scores[1]
        gap_signal = min(1.0, max(0.0, raw_gap * 0.4 + 0.5)) if raw_gap > 0 else 0.3

    # Coverage: do the top-3 chunks mention the query entities?
    entity_targets = (
        analysis.entities.get("named_statutes", []) +
        analysis.entities.get("harm_types", [])
    )
    coverage_signal = 0.65  # neutral prior
    if entity_targets:
        top3_text = " ".join(c.text.lower() for c in chunks[:3])
        matched = sum(1 for e in entity_targets if e.lower() in top3_text)
        coverage_signal = matched / len(entity_targets)

    # Contradiction: superseded chunks mixed with current ones → lower trust
    has_superseded = any(c.metadata.amendment_status == "superseded" for c in chunks[:3])
    contradiction_penalty = -0.10 if has_superseded else 0.0

    # Workflow availability: if user asked "what to do" but no workflow doc found
    workflow_signal = 0.0
    if analysis.is_workflow_query:
        has_workflow = any(c.metadata.document_type.value == "workflow" for c in chunks[:5])
        workflow_signal = 0.08 if has_workflow else -0.08

    confidence = (
        top1_norm * 0.40
        + gap_signal * 0.25
        + coverage_signal * 0.30
        + contradiction_penalty
        + workflow_signal
    )
    return min(1.0, max(0.0, confidence))


# ── Web search fallback ─────────────────────────────────────────

async def _web_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo self-hosted web search fallback."""
    try:
        # Support both old (duckduckgo_search) and new (ddgs) package names
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS  # type: ignore[no-redef]
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(f"{query} Bangladesh law legal rights", max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "href": r.get("href", ""),
                })
        logger.info("Web search returned %d results", len(results))
        return results
    except Exception as e:
        logger.warning("Web search failed: %s", e)
        return []


def _web_to_chunks(web_results: list[dict]) -> list[RetrievedChunk]:
    from app.ai.models import ChunkMetadata, DocumentType
    chunks = []
    for i, r in enumerate(web_results):
        text = f"{r.get('title', '')}\n{r.get('body', '')}".strip()[:1000]
        if not text:
            continue
        cid = f"web_{i}_{abs(hash(text)) % 999999}"
        chunks.append(RetrievedChunk(
            chunk_id=cid,
            text=text,
            score=0.4 - i * 0.05,
            metadata=ChunkMetadata(
                chunk_id=cid,
                document_id=f"web_{i}",
                document_type=DocumentType.commentary,
                authority_rank=9,     # Low — web is lower authority than corpus
                amendment_status="current",
                language="en",
                tenant_scope="national",
            ),
            source="web",
        ))
    return chunks


# ── Main corrective loop ────────────────────────────────────────

async def corrective_rag(
    query: str,
    query_en: str,
    query_bn: str,
    initial_chunks: list[RetrievedChunk],
    analysis: QueryAnalysis,
    namespace: str = "national",
) -> tuple[list[RetrievedChunk], float, bool]:
    """
    The v1 corrective RAG loop — retained and central.

    Returns: (final_chunks, confidence, web_search_fired)
    """
    top_k = 3 if analysis.complexity.value == "medium" else 5

    # Step 1: Rerank initial candidates
    reranked = stage2_retrieval.rerank_chunks(query, initial_chunks, top_k=top_k)
    confidence = compute_confidence(reranked, analysis)
    logger.info("Initial confidence: %.3f (threshold=%.2f)", confidence, CONFIDENCE_THRESHOLD)

    if confidence >= CONFIDENCE_THRESHOLD:
        return reranked, confidence, False

    # Step 2: Confidence < 70% → web search fallback
    logger.info("Triggering corrective web search for low confidence (%.3f)", confidence)
    web_results = await _web_search(query_en)
    web_chunks = _web_to_chunks(web_results)

    # Step 3: Merge web + corpus, then re-rerank (reranker runs again)
    merged = stage2_retrieval.rrf_merge(initial_chunks[:10], web_chunks)
    reranked_final = stage2_retrieval.rerank_chunks(query, merged, top_k=top_k)
    confidence_final = compute_confidence(reranked_final, analysis)
    logger.info("Post-corrective confidence: %.3f", confidence_final)

    return reranked_final, confidence_final, True
