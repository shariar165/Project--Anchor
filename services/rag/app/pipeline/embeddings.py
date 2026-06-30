"""
Lazy-loaded embedding model — fastembed (ONNX, no torch).

- Embedder: paraphrase-multilingual-MiniLM-L12-v2 (dense retrieval, Bangla +
  English; model id comes from config.embedding_model). Smallest multilingual
  fastembed model (~0.22 GB) — chosen for Railway's free-tier RAM budget.

The cross-encoder reranker was removed to keep the retrieval service inside
Railway's free-tier RAM budget. `rerank()` is retained with its original
signature but now returns a deterministic descending-score fallback, so
`stage2_retrieval.rerank_chunks()` keeps working unchanged.

Query/document prefixing: this model does not require e5-style prefixes, but we
keep separate embed() (documents) and embed_query() (queries) entry points so an
e5-family model can be swapped in via EMBEDDING_MODEL without touching callers.
The prefix strings below are empty for non-e5 models. Output vectors are
L2-normalised so the numpy store's dot product == cosine.

Thread-safe via double-checked locking. Falls back gracefully (returns None)
when the model isn't downloaded / available yet.
"""
import logging
import math
import threading

from app.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_embedder = None
_embed_tried = False


def _model_name() -> str:
    return get_settings().embedding_model


def _get_embedder():
    global _embedder, _embed_tried
    if _embed_tried:
        return _embedder
    with _lock:
        if not _embed_tried:
            _embed_tried = True
            try:
                from fastembed import TextEmbedding

                model = _model_name()
                # Fail loudly with a useful message if the configured id isn't a
                # known fastembed model, instead of an opaque ValueError deep in
                # the loader.
                try:
                    supported = {
                        m["model"] for m in TextEmbedding.list_supported_models()
                    }
                    if model not in supported:
                        logger.error(
                            "Embedding model %r is not in fastembed's supported "
                            "models — dense retrieval disabled. Set EMBEDDING_MODEL "
                            "to a supported multilingual model.",
                            model,
                        )
                        return None
                except Exception:
                    # list_supported_models() failing shouldn't block a valid id.
                    pass

                cache_dir = get_settings().fastembed_cache_path or None
                # Memory squeeze for Railway's 512 MB tier:
                #  - threads=1 → onnxruntime keeps a single intra/inter-op thread
                #    pool instead of one per CPU (each pool reserves an arena).
                #  - enable_cpu_mem_arena=False → onnxruntime doesn't pre-allocate
                #    and retain a large reusable memory arena; resident RAM tracks
                #    actual use. Costs a little latency, irrelevant at our QPS.
                _embedder = TextEmbedding(
                    model_name=model,
                    cache_dir=cache_dir,
                    threads=1,
                    enable_cpu_mem_arena=False,
                )
                logger.info("Embedder loaded: %s (threads=1, mem_arena=off)", model)
            except Exception as e:
                logger.warning("Embedder unavailable: %s — dense retrieval disabled", e)
    return _embedder


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0.0:
        return vec
    return [v / norm for v in vec]


def _is_e5() -> bool:
    """e5-family models require 'query: ' / 'passage: ' prefixes; others must NOT
    get them (the literal prefix would pollute the embedding)."""
    return "e5" in _model_name().lower()


def _embed_with_prefix(texts: list[str], prefix: str) -> list[list[float]] | None:
    """Embed texts (optionally prefixed); L2-normalise; return lists.

    Returns None if the model is unavailable (callers already handle None).
    """
    embedder = _get_embedder()
    if embedder is None:
        return None
    if not texts:
        return []
    try:
        prefixed = [f"{prefix}{t}" for t in texts] if prefix else texts
        # fastembed returns a generator of numpy arrays.
        vecs = list(embedder.embed(prefixed))
        return [_normalize([float(x) for x in v]) for v in vecs]
    except Exception as e:
        logger.error("Embed error: %s", e)
        return None


def embed(texts: list[str]) -> list[list[float]] | None:
    """Embed documents. Returns None if the model is unavailable."""
    return _embed_with_prefix(texts, "passage: " if _is_e5() else "")


def embed_query(texts: list[str]) -> list[list[float]] | None:
    """Embed queries. Returns None if the model is unavailable."""
    return _embed_with_prefix(texts, "query: " if _is_e5() else "")


def rerank(query: str, passages: list[str]) -> list[float]:
    """
    Reranking shim. The cross-encoder was removed for memory reasons; this now
    returns deterministic descending scores so retrieval order is preserved.
    Kept with the original signature so callers (stage2.rerank_chunks) are
    untouched.
    """
    if not passages:
        return []
    return [1.0 - i * 0.05 for i in range(len(passages))]
