"""
Shared Gemini (Google Generative Language API) client for the Core API.

Used as the PRIMARY generator by the API's own AI features — notice drafting
(`notice_ai_svc`), routine NL edits (`routine_svc`), and timetable NL edits
(`timetable_solver`). Each call site tries Gemini first and falls back to Ollama
(and then to a templated/None result) so a missing key or a transient failure
never hard-fails the feature.

Mirrors the Gemini path in `services/rag/app/pipeline/llm_client.py`.
"""
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    """True when a GEMINI_API_KEY is set, so callers can prefer Gemini."""
    return bool(get_settings().gemini_api_key)


def _auth_headers(key: str) -> dict[str, str]:
    """Pick the auth scheme by key shape. A permanent AI Studio key ("AIza…")
    authenticates via `x-goog-api-key`; an "AQ.…"/OAuth *access token* is a Bearer
    credential and is REJECTED on `x-goog-api-key` — it must go in `Authorization`.
    Sending an AQ. token on the wrong header is why Gemini silently 400s."""
    if key.startswith("AIza"):
        return {"x-goog-api-key": key, "Content-Type": "application/json"}
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


async def generate(prompt: str, *, temperature: float = 0.2, timeout: float = 60.0) -> str | None:
    """Run a single Gemini generateContent call.

    Returns the generated text, or None on any failure (no key, network error,
    empty/blocked response) so the caller can fall back to Ollama.
    """
    settings = get_settings()
    key = settings.gemini_api_key
    if not key:
        return None
    url = f"{settings.gemini_base_url}/v1beta/models/{settings.gemini_model}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                headers=_auth_headers(key),
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": temperature},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return None
            parts = candidates[0].get("content", {}).get("parts", []) or []
            text = "".join(p.get("text", "") for p in parts).strip()
            return text or None
    except httpx.HTTPStatusError as exc:
        # An auth failure (expired/invalid/revoked key) is distinct from a transient
        # outage — surface it clearly so it's actionable, not a generic warning.
        # Google returns 400 API_KEY_INVALID (not just 401/403) for a bad key.
        _body = ""
        try:
            _body = exc.response.text.lower()
        except Exception:
            pass
        _key_error = exc.response.status_code in (401, 403) or (
            exc.response.status_code == 400
            and ("api_key_invalid" in _body or "api key not valid" in _body or "api key" in _body)
        )
        if _key_error:
            logger.error(
                "Gemini rejected the API key (HTTP %s — expired/invalid/revoked). "
                "Check GEMINI_API_KEY (must be a permanent AIza… AI Studio key). "
                "Falling back to Ollama.",
                exc.response.status_code,
            )
        else:
            logger.warning("Gemini generate failed (falling back): %s", exc)
        return None
    except Exception as exc:
        logger.warning("Gemini generate failed (falling back): %s", exc)
        return None
