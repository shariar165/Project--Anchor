"""
In-memory numpy vector store (replaces ChromaDB).

The corpus is tiny (~2 MB), so each namespace holds a normalised (N, D) float32
matrix in RAM and dense search is a single matmul:
    scores = matrix @ query_vec
    top_k  = scores.argsort()[-k:][::-1]
Vectors are L2-normalised at ingest, so the dot product == cosine similarity.

Persistence (so a restart / BM25 rebuild keeps text + metadata):
    {vector_store_path}/{namespace}.npy   — float32 (N, D) matrix
    {namespace}.json                      — aligned rows: {chunk_id, text, metadata}

Per-tenant namespaces: 'national' (shared) and 'diu' (campus-scoped).
Lazy-initialised and fully fault-tolerant — missing files, dimension mismatch,
or numpy being unavailable all degrade to an empty namespace rather than raising
into the pipeline.

The public surface mirrors the old ChromaDB wrapper so callers are untouched:
    upsert_chunks, query_dense, count, get_all_chunks, list_documents,
    delete_document. `is_ready()` replaces the old `_get_client()` health probe.
"""
import json
import logging
import os
import threading
from typing import Optional

from app.config import get_settings
from app.pipeline.models import ChunkMetadata, RetrievedChunk, DocumentType

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# namespace -> {"matrix": np.ndarray | None, "rows": list[dict]}
# Each row: {"chunk_id": str, "text": str, "metadata": dict, "embedding": list[float]}
_store: dict[str, dict] = {}
_loaded: set[str] = set()


def _base_path() -> str:
    return get_settings().vector_store_path


def _paths(namespace: str) -> tuple[str, str]:
    base = _base_path()
    return (
        os.path.join(base, f"{namespace}.npy"),
        os.path.join(base, f"{namespace}.json"),
    )


def _empty() -> dict:
    return {"matrix": None, "rows": []}


def _load(namespace: str) -> dict:
    """Load a namespace from disk into the in-memory store (once)."""
    if namespace in _loaded:
        return _store.get(namespace, _empty())
    _loaded.add(namespace)
    ns = _empty()
    npy_path, json_path = _paths(namespace)
    try:
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                ns["rows"] = json.load(f)
        if os.path.exists(npy_path) and ns["rows"]:
            import numpy as np

            mat = np.load(npy_path)
            # Guard against a stale matrix written by a previous embedding model
            # (different dim) or a row/matrix length mismatch — treat as empty so
            # warmup re-embeds cleanly instead of returning garbage scores.
            if mat.ndim == 2 and mat.shape[0] == len(ns["rows"]):
                ns["matrix"] = mat.astype(np.float32, copy=False)
            else:
                logger.warning(
                    "Vector matrix for '%s' mismatched (matrix=%s rows=%d) — "
                    "ignoring; will rebuild on next ingest.",
                    namespace, getattr(mat, "shape", None), len(ns["rows"]),
                )
                ns["rows"] = []
        if ns["rows"] and ns["matrix"] is not None:
            logger.info("Vector store loaded '%s': %d chunks", namespace, len(ns["rows"]))
    except Exception as e:
        logger.warning("Vector store load failed for '%s': %s", namespace, e)
        ns = _empty()
    _store[namespace] = ns
    return ns


def _rebuild_matrix(ns: dict) -> None:
    """Rebuild the (N, D) matrix from row embeddings. Caller holds the lock."""
    try:
        import numpy as np

        embs = [r.get("embedding") for r in ns["rows"] if r.get("embedding")]
        if embs and len(embs) == len(ns["rows"]):
            ns["matrix"] = np.asarray(embs, dtype=np.float32)
        else:
            ns["matrix"] = None
    except Exception as e:
        logger.error("Matrix rebuild error: %s", e)
        ns["matrix"] = None


def _persist(namespace: str, ns: dict) -> None:
    """Write the namespace to disk. Caller holds the lock."""
    try:
        import numpy as np

        os.makedirs(_base_path(), exist_ok=True)
        npy_path, json_path = _paths(namespace)
        # JSON sidecar carries text + metadata (+ embedding so BM25/rebuild and a
        # cold start work without re-embedding).
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(ns["rows"], f, ensure_ascii=False)
        if ns["matrix"] is not None:
            np.save(npy_path, ns["matrix"])
        elif os.path.exists(npy_path):
            os.remove(npy_path)
    except Exception as e:
        logger.error("Vector store persist error for '%s': %s", namespace, e)


def is_ready(namespace: str = "national") -> bool:
    """Health probe — replaces the old ChromaDB client check."""
    try:
        import numpy  # noqa: F401
    except Exception:
        return False
    return True


def upsert_chunks(chunks: list[dict], namespace: str = "national"):
    """Upsert pre-embedded chunks. Each chunk: {chunk_id, text, embedding, metadata}."""
    if not chunks:
        return
    with _lock:
        ns = _load(namespace)
        by_id = {r["chunk_id"]: r for r in ns["rows"]}
        for c in chunks:
            emb = c.get("embedding")
            if not emb:
                continue
            cid = c["chunk_id"]
            by_id[cid] = {
                "chunk_id": cid,
                "text": c.get("text", ""),
                "metadata": c.get("metadata", {}) or {},
                "embedding": [float(x) for x in emb],
            }
        ns["rows"] = list(by_id.values())
        _rebuild_matrix(ns)
        _store[namespace] = ns
        _persist(namespace, ns)
        logger.debug("Upserted %d chunks into '%s' (total=%d)",
                     len(chunks), namespace, len(ns["rows"]))


def _matches(meta: dict, where: Optional[dict]) -> bool:
    """Apply the plain filter dict from stage2._build_where.

    Scalar value → equality; list value → membership. Missing key → no match
    for that condition (i.e. excluded), matching ChromaDB's behaviour.
    """
    if not where:
        return True
    for key, cond in where.items():
        val = meta.get(key)
        if isinstance(cond, (list, tuple, set)):
            if val not in cond:
                return False
        else:
            if val != cond:
                return False
    return True


def query_dense(
    query_embedding: list[float],
    n_results: int = 20,
    where: Optional[dict] = None,
    namespace: str = "national",
) -> list[RetrievedChunk]:
    """Dense cosine search (matmul + top-k) over normalised embeddings."""
    ns = _load(namespace)
    rows = ns["rows"]
    mat = ns["matrix"]
    if not rows or mat is None or not query_embedding:
        return []
    try:
        import numpy as np

        q = np.asarray(query_embedding, dtype=np.float32)
        qn = np.linalg.norm(q)
        if qn > 0:
            q = q / qn
        scores = mat @ q  # (N,) cosine similarities

        # Filter by `where` first, then take the top-k of the surviving rows.
        idxs = [i for i in range(len(rows)) if _matches(rows[i].get("metadata", {}), where)]
        if not idxs:
            return []
        idxs.sort(key=lambda i: float(scores[i]), reverse=True)
        idxs = idxs[: min(n_results, len(idxs))]

        chunks: list[RetrievedChunk] = []
        for i in idxs:
            row = rows[i]
            meta = row.get("metadata", {}) or {}
            score = max(0.0, float(scores[i]))
            rc = _to_retrieved(row, meta, score)
            if rc is not None:
                chunks.append(rc)
        return chunks
    except Exception as e:
        logger.error("Dense query error: %s", e)
        return []


def _to_retrieved(row: dict, meta: dict, score: float) -> Optional[RetrievedChunk]:
    try:
        meta_obj = ChunkMetadata(
            chunk_id=meta.get("chunk_id", row.get("chunk_id", "")),
            document_id=meta.get("document_id", ""),
            document_type=DocumentType(meta.get("document_type", "statute")),
            jurisdiction=meta.get("jurisdiction", "bangladesh"),
            authority_rank=int(meta.get("authority_rank", 3)),
            act_name=meta.get("act_name", ""),
            chapter=meta.get("chapter", ""),
            section=meta.get("section", ""),
            effective_date=meta.get("effective_date", ""),
            amendment_status=meta.get("amendment_status", "current"),
            language=meta.get("language", "en"),
            tenant_scope=meta.get("tenant_scope", "national"),
        )
        return RetrievedChunk(
            chunk_id=row.get("chunk_id", ""),
            text=row.get("text", ""),
            score=score,
            metadata=meta_obj,
            source="corpus",
        )
    except Exception:
        return None


def count(namespace: str = "national") -> int:
    return len(_load(namespace)["rows"])


def get_all_chunks(namespace: str = "national") -> list[dict]:
    """Return every stored chunk as {chunk_id, text, metadata}.

    This is the persistent source of truth used to rebuild the in-memory BM25
    index and to list/inspect the corpus.
    """
    out: list[dict] = []
    for r in _load(namespace)["rows"]:
        meta = r.get("metadata", {}) or {}
        out.append({
            "chunk_id": meta.get("chunk_id", r.get("chunk_id", "")),
            "text": r.get("text", ""),
            "metadata": meta,
        })
    return out


def list_documents(namespace: str = "national") -> list[dict]:
    """Group stored chunks by document_id into a corpus document listing."""
    docs: dict[str, dict] = {}
    for c in get_all_chunks(namespace):
        m = c.get("metadata", {})
        doc_id = m.get("document_id") or m.get("chunk_id") or c.get("chunk_id", "")
        if doc_id not in docs:
            docs[doc_id] = {
                "document_id": doc_id,
                "title": m.get("act_name") or m.get("document_title") or doc_id,
                "document_type": m.get("document_type", "statute"),
                "section": m.get("section", ""),
                "language": m.get("language", "en"),
                "effective_date": m.get("effective_date", ""),
                "tenant_scope": m.get("tenant_scope", namespace),
                "chunk_count": 0,
            }
        docs[doc_id]["chunk_count"] += 1
    return sorted(docs.values(), key=lambda d: d["title"].lower())


def delete_document(document_id: str, namespace: str = "national") -> int:
    """Delete all chunks belonging to a document_id. Returns chunks removed."""
    with _lock:
        ns = _load(namespace)
        before = len(ns["rows"])
        ns["rows"] = [
            r for r in ns["rows"]
            if (r.get("metadata", {}) or {}).get("document_id") != document_id
        ]
        removed = before - len(ns["rows"])
        if removed:
            _rebuild_matrix(ns)
            _store[namespace] = ns
            _persist(namespace, ns)
        return max(0, removed)
