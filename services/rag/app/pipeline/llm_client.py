"""
Async LLM client for Anchor AI.
Provider order:
  1. Gemini (Google Generative Language API) — used when GEMINI_API_KEY is set.
  2. Ollama inference (URL from OLLAMA_BASE_URL env var, defaults to localhost:11434).
  3. Deterministic stub when neither is reachable (CI / dev without GPU or API key).
Ollama is intentionally NOT removed — it stays as the fallback generator.
"""
import json
import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)

SMALL_MODEL = "qwen3:1.7b"
MAIN_MODEL = "qwen3:1.7b"


def _ollama_base() -> str:
    return get_settings().ollama_base_url


# ── Gemini ────────────────────────────────────────────────────────────────────
# When GEMINI_API_KEY is configured, Gemini is the primary generator. It degrades
# to Ollama (then the stub) on any error, so the pipeline never hard-fails.
_gemini_available: bool | None = None
# Human-readable reason the last probe/call failed, surfaced by /health so an
# expired key doesn't hide behind a silent stub fallback:
#   "ok" | "invalid_key" | "unavailable" | "not configured"
_gemini_status: str = "not configured"


def _gemini_key() -> str:
    return get_settings().gemini_api_key


def is_studio_key(key: str) -> bool:
    """True when `key` looks like a permanent Google AI Studio API key (AIza…).
    `AQ.`/ephemeral OAuth tokens pass a fresh probe but expire within hours — this
    lets startup/health warn before the chatbot silently degrades to the stub."""
    return key.startswith("AIza")


def gemini_health_status() -> str:
    """Last known Gemini status for /health (set by _check_gemini_availability)."""
    return _gemini_status


def _is_key_error(status_code: int, body: str = "") -> bool:
    """True when an HTTP error is Gemini rejecting the key (expired/invalid/revoked)
    rather than a transient outage. Google returns 401/403 for permission problems
    and — notably — 400 `API_KEY_INVALID` for a bad/expired key, so inspect the body
    for a 400 before blaming the network."""
    if status_code in (401, 403):
        return True
    if status_code == 400:
        b = body.lower()
        return "api_key_invalid" in b or "api key not valid" in b or "api key" in b
    return False


async def _check_gemini_availability() -> bool:
    global _gemini_available, _gemini_status
    if _gemini_available is not None:
        return _gemini_available
    key = _gemini_key()
    if not key:
        _gemini_available = False
        _gemini_status = "not configured"
        return False
    try:
        s = get_settings()
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                f"{s.gemini_base_url}/v1beta/models",
                headers={"x-goog-api-key": key},
            )
            _gemini_available = r.status_code == 200
            # A rejected key (expired/invalid/revoked) is distinct from a network
            # outage — surface it so the fix is obvious. Google returns 400
            # API_KEY_INVALID (not just 401/403) for a bad key.
            _gemini_status = "ok" if r.status_code == 200 else (
                "invalid_key" if _is_key_error(r.status_code, r.text) else "unavailable"
            )
    except Exception:
        _gemini_available = False
        _gemini_status = "unavailable"
    logger.info("Gemini available: %s (%s)", _gemini_available, _gemini_status)
    return _gemini_available


async def _gemini_generate(prompt: str, temperature: float) -> str | None:
    """Call Gemini generateContent. Returns text, or None on any failure (so the
    caller falls through to Ollama)."""
    global _gemini_status
    key = _gemini_key()
    if not key:
        return None
    s = get_settings()
    url = f"{s.gemini_base_url}/v1beta/models/{s.gemini_model}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                url,
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
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
    except httpx.HTTPStatusError as e:
        # Distinguish an auth failure (expired/invalid key) from everything else so
        # "what happened to the gemini api" is unambiguous in the logs.
        body = ""
        try:
            body = e.response.text
        except Exception:
            pass
        if _is_key_error(e.response.status_code, body):
            _gemini_status = "invalid_key"
            logger.error(
                "Gemini rejected the API key (HTTP %s — expired/invalid/revoked). "
                "Check GEMINI_API_KEY (must be a permanent AIza… AI Studio key). "
                "Falling back to Ollama/stub.",
                e.response.status_code,
            )
        else:
            logger.error("Gemini generate HTTP error: %s", e)
        return None
    except Exception as e:
        logger.error("Gemini generate error: %s", e)
        return None

# When OLLAMA_BASE_URL points at an ngrok tunnel, the free tier serves an HTML
# "browser warning" interstitial unless this header is present — which would make
# our JSON parsing fail and silently drop us to the stub. Harmless against a local
# Ollama (it just ignores the header), so we always send it.
_OLLAMA_HEADERS = {"ngrok-skip-browser-warning": "true"}

_available: bool | None = None


async def _check_availability() -> bool:
    global _available
    if _available is not None:
        return _available
    try:
        # 5s (not 2s) because the tunnel adds internet round-trip latency.
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{_ollama_base()}/api/tags", headers=_OLLAMA_HEADERS)
            _available = r.status_code == 200
    except Exception:
        _available = False
    logger.info("Ollama available: %s", _available)
    return _available


async def generate_with_backend(
    prompt: str, model: str = MAIN_MODEL, temperature: float = 0.1
) -> tuple[str, str]:
    """Like generate(), but also returns which backend produced the text:
    "gemini" | "ollama" | "stub". Lets callers surface a degraded (stub) answer
    instead of silently serving templated boilerplate."""
    # 1. Prefer Gemini when an API key is configured.
    gemini_out = await _gemini_generate(prompt, temperature)
    if gemini_out is not None:
        return gemini_out, "gemini"
    # 2. Fall back to Ollama (local / ngrok).
    if not await _check_availability():
        return _stub_response(prompt), "stub"
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{_ollama_base()}/api/generate",
                headers=_OLLAMA_HEADERS,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    # qwen3 defaults to a long hidden reasoning trace before
                    # answering, which dominates latency — especially over the
                    # ngrok tunnel to a remote Ollama. Disable it: the pipeline
                    # already structures reasoning in stages 4/5.
                    "think": False,
                    # Pin the model in memory indefinitely. On CPU-only hosts the
                    # cold reload (after Ollama's default 5-min idle unload) costs
                    # 60s+ and times out the pipeline; warm calls are ~3s.
                    "keep_alive": -1,
                    "options": {"temperature": temperature},
                },
            )
            resp.raise_for_status()
            return resp.json().get("response", ""), "ollama"
    except Exception as e:
        logger.error("Ollama generate error: %s", e)
        return _stub_response(prompt), "stub"


async def generate(prompt: str, model: str = MAIN_MODEL, temperature: float = 0.1) -> str:
    text, _backend = await generate_with_backend(prompt, model, temperature)
    return text


def reset_availability_cache():
    """Call this to re-probe Gemini and Ollama (e.g. after a server restart)."""
    global _available, _gemini_available, _gemini_status
    _available = None
    _gemini_available = None
    _gemini_status = "not configured"


def _stub_response(prompt: str) -> str:
    """
    Deterministic fallback when Ollama is offline.
    Returns structured JSON stubs for classification prompts,
    and a plain-text stub for generation prompts.
    Used in development / CI without GPU.
    """
    pl = prompt.lower()
    if "classify" in pl or "intent" in pl or "characterize" in pl:
        return json.dumps({
            "intent": "rights_query",
            "confidence": 0.70,
            "lang": "en",
            "needs_retrieval": True,
            "complexity": "medium",
            "is_workflow_query": False,
            "historical_law": False,
            "entities": {
                "relationships": [],
                "harm_types": [],
                "named_statutes": [],
                "jurisdiction_hint": "national",
                "temporal": "unclear",
                "user_posture": "inquirer",
            },
        })
    if "claim" in pl or "verify" in pl or "check if" in pl:
        return 'supported\nThe context directly supports this claim.'
    if "rewrite" in pl or "english" in pl and "bangla" in pl:
        return json.dumps({"english": prompt.split("\n")[-1], "bangla": prompt.split("\n")[-1]})
    if "context" in pl or "situation" in pl or "applicable law" in pl:
        return (
            "1. SITUATION: The user is asking about their legal rights and options.\n\n"
            "2. APPLICABLE LAW: The relevant Bangladeshi statutes apply to this situation. [chunk-1]\n\n"
            "3. APPLICATION: Based on the context provided, you have legal recourse available.\n\n"
            "4. PRACTICAL STEP: File a complaint at the nearest police station or relevant authority. "
            "Bring your National ID and a written description of the incident. [wf-gd-filing]\n\n"
            "5. SCOPE LIMITS: This guidance is general. For your specific circumstances, consult a "
            "verified lawyer — especially if the matter involves court proceedings.\n\n"
            "CITATIONS_JSON: []"
        )
    # Generic prefix generation
    return f"This chunk covers {prompt[:80]}... in the context of Bangladeshi law and civic governance."
