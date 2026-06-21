"""Shared helpers for proxying to the internal RAG service.

The RAG service authenticates callers with a shared X-Internal-Secret header
(never the user JWT). Used by routers/ai.py (chat) and routers/super_corpus.py
(corpus management).
"""
from app.config import get_settings


def rag_url() -> str:
    return get_settings().rag_service_url


def rag_headers() -> dict[str, str]:
    h: dict[str, str] = {
        "Content-Type": "application/json",
        # When RAG is reached through ngrok (RAG-on-PC topology), this skips
        # ngrok's HTML interstitial so we always get the JSON body back.
        # Harmless when RAG is reached directly (unknown header is ignored).
        "ngrok-skip-browser-warning": "true",
    }
    secret = get_settings().rag_internal_secret
    if secret:
        h["X-Internal-Secret"] = secret
    return h
