"""
Contextual BM25 sparse retrieval with Bangla-English legal synonym expansion.
Runs in-memory per namespace. Rebuilt on each ingestion batch.
"""
import re
import logging
import threading
from app.pipeline.models import ChunkMetadata, RetrievedChunk, DocumentType

logger = logging.getLogger(__name__)

_lock = threading.Lock()
# namespace -> (BM25Okapi, list[dict])
_indices: dict[str, tuple] = {}

# Bangla-English legal synonym map for query expansion
SYNONYM_MAP: dict[str, list[str]] = {
    # Bangla → English equivalents
    "মারধর":   ["violence", "assault", "abuse", "beat"],
    "নির্যাতন": ["torture", "abuse", "violence", "harassment", "persecution"],
    "অত্যাচার": ["oppression", "abuse", "violence", "atrocity"],
    "হয়রানি":   ["harassment", "intimidation", "abuse"],
    "অধিকার":   ["rights", "entitlement"],
    "অভিযোগ":   ["complaint", "allegation", "case"],
    "নালিশ":    ["complaint", "case"],
    "মামলা":    ["case", "lawsuit", "FIR"],
    "জিডি":     ["GD", "general diary"],
    "এফআইআর":   ["FIR", "first information report"],
    "থানা":     ["thana", "police station"],
    "আদালত":    ["court", "tribunal"],
    "আইন":      ["law", "act", "statute"],
    "ধারা":     ["section", "clause"],
    "কীভাবে":   ["how", "procedure", "steps"],
    "সহিংসতা":  ["violence", "assault"],
    "গৃহহিংসা":  ["domestic violence", "family violence"],
    # English → Bangla equivalents
    "harassment": ["নির্যাতন", "হয়রানি"],
    "abuse":      ["নির্যাতন", "অত্যাচার", "মারধর"],
    "violence":   ["সহিংসতা", "মারধর", "নির্যাতন"],
    "complaint":  ["অভিযোগ", "নালিশ"],
    "rights":     ["অধিকার"],
    "fir":        ["এফআইআর", "মামলা"],
    "gd":         ["জিডি"],
    "law":        ["আইন"],
    "court":      ["আদালত"],
}


def _tokenize(text: str) -> list[str]:
    """
    Bilingual tokeniser: Bangla unicode blocks + ASCII words.
    Expands tokens via the synonym map for cross-language recall.
    """
    tokens = re.findall(r'[ঀ-৿]+|[a-zA-Z0-9]+', text.lower())
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        for syn in SYNONYM_MAP.get(token, []):
            expanded.extend(syn.lower().split())
    return expanded


def build_index(chunks: list[dict], namespace: str = "national"):
    """Build (or rebuild) the BM25 index for the given namespace."""
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        logger.warning("rank-bm25 not installed — sparse retrieval disabled")
        return

    if not chunks:
        return
    tokenized = [_tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized)
    with _lock:
        _indices[namespace] = (bm25, chunks)
    logger.info("BM25 index built: namespace=%s docs=%d", namespace, len(chunks))


def query_bm25(
    query: str,
    n_results: int = 20,
    namespace: str = "national",
) -> list[RetrievedChunk]:
    """Sparse BM25 query with synonym expansion."""
    if namespace not in _indices:
        return []
    bm25, chunks = _indices[namespace]
    try:
        tokens = _tokenize(query)
        scores = bm25.get_scores(tokens)
        scored = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:n_results]
        results = []
        for idx, score in scored:
            if score <= 0:
                continue
            c = chunks[idx]
            m = c.get("metadata", {})
            try:
                meta = ChunkMetadata(
                    chunk_id=m.get("chunk_id", c.get("chunk_id", "")),
                    document_id=m.get("document_id", ""),
                    document_type=DocumentType(m.get("document_type", "statute")),
                    jurisdiction=m.get("jurisdiction", "bangladesh"),
                    authority_rank=int(m.get("authority_rank", 3)),
                    act_name=m.get("act_name", ""),
                    chapter=m.get("chapter", ""),
                    section=m.get("section", ""),
                    effective_date=m.get("effective_date", ""),
                    amendment_status=m.get("amendment_status", "current"),
                    language=m.get("language", "en"),
                    tenant_scope=m.get("tenant_scope", "national"),
                )
                results.append(RetrievedChunk(
                    chunk_id=c.get("chunk_id", ""),
                    text=c.get("text", ""),
                    score=float(score),
                    metadata=meta,
                    source="corpus",
                ))
            except Exception:
                continue
        return results
    except Exception as e:
        logger.error("BM25 query error: %s", e)
        return []


def index_count(namespace: str = "national") -> int:
    return len(_indices.get(namespace, (None, []))[1] or [])
