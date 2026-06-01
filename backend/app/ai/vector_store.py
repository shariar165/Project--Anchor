"""
ChromaDB vector store wrapper.
Per-tenant namespaces: 'national' (shared) and 'diu' (campus-scoped).
Lazy-initialised — safe to import before ChromaDB is installed.
"""
import logging
import os
import threading
from typing import Optional
from app.ai.models import ChunkMetadata, RetrievedChunk, DocumentType

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_client = None
_collections: dict = {}

# Relative to backend/ working directory
CHROMA_PATH = os.environ.get("CHROMADB_PATH", "data/chromadb")


def _get_client():
    global _client
    if _client is not None:
        return _client
    with _lock:
        if _client is None:
            try:
                import chromadb
                os.makedirs(CHROMA_PATH, exist_ok=True)
                _client = chromadb.PersistentClient(path=CHROMA_PATH)
                logger.info("ChromaDB initialised at %s", CHROMA_PATH)
            except Exception as e:
                logger.warning("ChromaDB unavailable: %s", e)
    return _client


def get_collection(namespace: str = "national"):
    client = _get_client()
    if client is None:
        return None
    key = f"anchor_{namespace}"
    if key not in _collections:
        try:
            col = client.get_or_create_collection(
                name=key,
                metadata={"hnsw:space": "cosine"},
            )
            _collections[key] = col
        except Exception as e:
            logger.error("Collection error: %s", e)
            return None
    return _collections[key]


def upsert_chunks(chunks: list[dict], namespace: str = "national"):
    """Upsert pre-embedded chunks into ChromaDB."""
    col = get_collection(namespace)
    if col is None:
        return
    try:
        # Flatten metadata: ChromaDB only accepts str/int/float/bool
        flat_metas = []
        for c in chunks:
            m = c.get("metadata", {})
            flat = {
                k: (v if isinstance(v, (str, int, float, bool)) else str(v))
                for k, v in m.items()
                if v is not None
            }
            flat_metas.append(flat)

        col.upsert(
            ids=[c["chunk_id"] for c in chunks],
            embeddings=[c["embedding"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=flat_metas,
        )
        logger.debug("Upserted %d chunks into '%s'", len(chunks), namespace)
    except Exception as e:
        logger.error("Upsert error: %s", e)


def query_dense(
    query_embedding: list[float],
    n_results: int = 20,
    where: Optional[dict] = None,
    namespace: str = "national",
) -> list[RetrievedChunk]:
    """Dense cosine-similarity search over contextual embeddings."""
    col = get_collection(namespace)
    if col is None:
        return []
    try:
        count = col.count()
        if count == 0:
            return []
        n = min(n_results, count)
        kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": n,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        results = col.query(**kwargs)

        chunks = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            try:
                score = max(0.0, 1.0 - float(dist))
                meta_obj = ChunkMetadata(
                    chunk_id=meta.get("chunk_id", ""),
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
                chunks.append(RetrievedChunk(
                    chunk_id=meta.get("chunk_id", ""),
                    text=doc,
                    score=score,
                    metadata=meta_obj,
                    source="corpus",
                ))
            except Exception:
                continue
        return chunks
    except Exception as e:
        logger.error("Dense query error: %s", e)
        return []


def count(namespace: str = "national") -> int:
    col = get_collection(namespace)
    if col is None:
        return 0
    try:
        return col.count()
    except Exception:
        return 0
