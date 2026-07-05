"""Shared helpers for proxying to the internal RAG service.

The RAG service authenticates callers with a shared X-Internal-Secret header
(never the user JWT). Used by routers/ai.py (chat), routers/super_corpus.py
(corpus management), and the service layer (application/filing AI drafting).
"""
import httpx

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


async def rag_chat(query: str, mode: str, lang: str, timeout: float = 60.0) -> str:
    """Run the RAG /chat pipeline over HTTP and return the answer text.

    The 7-stage pipeline lives in the standalone RAG service (services/rag); the
    Core API reaches it over HTTP exactly like routers/ai.py does. Raises on any
    transport / HTTP / parse error so callers keep their own try/except fallback
    (skeleton letter, manual-review message) when RAG is unreachable.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{rag_url()}/chat",
            json={"query": query, "mode": mode, "lang": lang},
            headers=rag_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
    return (data.get("answer") or "").strip()
