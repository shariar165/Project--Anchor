import os
from functools import lru_cache


class RAGSettings:
    ollama_base_url: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    chromadb_path: str = os.environ.get("CHROMADB_PATH", "data/chromadb")
    disable_ai_warmup: bool = os.environ.get("DISABLE_AI_WARMUP", "").lower() in ("true", "1", "yes")
    # Override path to the unzipped skill source tree (skills/src). Blank = repo default
    # resolved relative to this service; see app/pipeline/skill_loader.py.
    skills_dir: str = os.environ.get("SKILLS_DIR", "")


@lru_cache
def get_settings() -> RAGSettings:
    return RAGSettings()
