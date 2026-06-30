import os
from functools import lru_cache


class RAGSettings:
    ollama_base_url: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    # Gemini (Google Generative Language API) — used as the PRIMARY generator when
    # GEMINI_API_KEY is set; Ollama remains the fallback when it is blank/unreachable.
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
    gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_base_url: str = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")
    # Dense embedder (fastembed, ONNX — no torch). Must be a multilingual model
    # that covers Bangla; verified against TextEmbedding.list_supported_models()
    # at load time. paraphrase-multilingual-MiniLM-L12-v2 is the smallest such
    # model (~0.22 GB) — chosen for Railway's free-tier RAM budget.
    embedding_model: str = os.environ.get(
        "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    # In-memory numpy vector store persistence dir (replaces ChromaDB).
    vector_store_path: str = os.environ.get("VECTOR_STORE_PATH", "data/vectors")
    # Baked fastembed model cache (set in the Dockerfile so the model isn't
    # re-downloaded — and re-spiking RAM — on every restart). Blank = default.
    fastembed_cache_path: str = os.environ.get("FASTEMBED_CACHE_PATH", "")
    disable_ai_warmup: bool = os.environ.get("DISABLE_AI_WARMUP", "").lower() in ("true", "1", "yes")
    # Override path to the unzipped skill source tree (skills/src). Blank = repo default
    # resolved relative to this service; see app/pipeline/skill_loader.py.
    skills_dir: str = os.environ.get("SKILLS_DIR", "")


@lru_cache
def get_settings() -> RAGSettings:
    return RAGSettings()
