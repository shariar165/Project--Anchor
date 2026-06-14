"""
Lazy-loaded sentence-transformers models.
- Embedder: paraphrase-multilingual-mpnet-base-v2  (dense retrieval)
- Reranker: cross-encoder/ms-marco-MiniLM-L-6-v2  (CENTRAL — runs on every path)

Thread-safe via double-checked locking.
Falls back gracefully when models aren't downloaded yet.
"""
import logging
import threading

logger = logging.getLogger(__name__)

EMBED_MODEL = "paraphrase-multilingual-mpnet-base-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_lock = threading.Lock()
_embedder = None
_reranker = None
_embed_tried = False
_rerank_tried = False


def _get_embedder():
    global _embedder, _embed_tried
    if _embed_tried:
        return _embedder
    with _lock:
        if not _embed_tried:
            _embed_tried = True
            try:
                from sentence_transformers import SentenceTransformer
                _embedder = SentenceTransformer(EMBED_MODEL)
                logger.info("Embedder loaded: %s", EMBED_MODEL)
            except Exception as e:
                logger.warning("Embedder unavailable: %s — dense retrieval disabled", e)
    return _embedder


def _get_reranker():
    global _reranker, _rerank_tried
    if _rerank_tried:
        return _reranker
    with _lock:
        if not _rerank_tried:
            _rerank_tried = True
            try:
                from sentence_transformers.cross_encoder import CrossEncoder
                _reranker = CrossEncoder(RERANK_MODEL)
                logger.info("Reranker loaded: %s", RERANK_MODEL)
            except Exception as e:
                logger.warning("Reranker unavailable: %s — using score passthrough", e)
    return _reranker


def embed(texts: list[str]) -> list[list[float]] | None:
    """Embed a list of texts. Returns None if model unavailable."""
    embedder = _get_embedder()
    if embedder is None:
        return None
    try:
        vecs = embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()
    except Exception as e:
        logger.error("Embed error: %s", e)
        return None


def rerank(query: str, passages: list[str]) -> list[float]:
    """
    Cross-encoder reranking — CENTRAL to every retrieval path.
    Falls back to descending scores if model unavailable.
    """
    reranker = _get_reranker()
    if not passages:
        return []
    if reranker is None:
        return [1.0 - i * 0.05 for i in range(len(passages))]
    try:
        pairs = [[query, p] for p in passages]
        scores = reranker.predict(pairs)
        return scores.tolist()
    except Exception as e:
        logger.error("Rerank error: %s", e)
        return [1.0 - i * 0.05 for i in range(len(passages))]
