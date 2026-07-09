"""
Async LLM client for Anchor AI.

Provider order (each tried in turn; first non-empty answer wins):
  1. Ollama   — local inference (URL from OLLAMA_BASE_URL, e.g. http://192.168.0.111:11434).
                Free, fast on the LAN, and the primary generator.
  2. Gemini   — Google Generative Language API, when GEMINI_API_KEY is set.
  3. Groq     — OpenAI-compatible API, when GROQ_API_KEY is set. The reliable cloud
                fallback (permanent gsk_ keys), so an expired Gemini token never dies.
  4. Stub     — deterministic canned answer when none of the above are reachable
                (CI / dev without a GPU or any API key).

Seamless, fast failover: a provider that just failed is put on a short cooldown
(circuit breaker) so subsequent calls skip it with zero network cost, and tight
connect timeouts mean a powered-off box fails over in ~2s instead of hanging.
The user never perceives that three backends are being tried.
"""
import json
import logging
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

SMALL_MODEL = "qwen3:1.7b"
MAIN_MODEL = "qwen3:1.7b"

# ── Circuit breaker ─────────────────────────────────────────────────────────────
# provider name -> monotonic timestamp until which we skip that provider. A failed
# provider is skipped for a short window so repeated calls stay instant; it self-heals
# once the window passes. Local Ollama recovers fast (short cooldown); cloud longer.
_cooldown_until: dict[str, float] = {}
_OLLAMA_COOLDOWN_S = 30.0
_CLOUD_COOLDOWN_S = 60.0

# Human-readable last-known status for /health, per provider. One of:
#   "ok" | "invalid_key" | "unavailable" | "not configured"
_status: dict[str, str] = {"ollama": "unknown", "gemini": "not configured", "groq": "not configured"}


def _in_cooldown(provider: str) -> bool:
    return time.monotonic() < _cooldown_until.get(provider, 0.0)


def _trip(provider: str, seconds: float) -> None:
    _cooldown_until[provider] = time.monotonic() + seconds


def _clear(provider: str) -> None:
    _cooldown_until.pop(provider, None)


# ── Ollama ──────────────────────────────────────────────────────────────────────
# When OLLAMA_BASE_URL points at an ngrok tunnel, the free tier serves an HTML
# "browser warning" interstitial unless this header is present — which would make
# our JSON parsing fail and silently drop us to the next provider. Harmless against a
# direct/local Ollama (it just ignores the header), so we always send it.
_OLLAMA_HEADERS = {"ngrok-skip-browser-warning": "true"}
# connect fast (a powered-off LAN box should fail over in ~2s, not hang); read stays
# generous because a warm qwen3 still needs a few seconds to answer.
_OLLAMA_TIMEOUT = httpx.Timeout(connect=2.0, read=60.0, write=10.0, pool=2.0)


def _ollama_base() -> str:
    return get_settings().ollama_base_url


async def _ollama_generate(prompt: str, model: str, temperature: float) -> str | None:
    """Call the local Ollama. Returns text, or None on any failure (so the caller
    falls through to Gemini/Groq). Trips the circuit breaker on failure."""
    if _in_cooldown("ollama"):
        return None
    try:
        async with httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT) as client:
            resp = await client.post(
                f"{_ollama_base()}/api/generate",
                headers=_OLLAMA_HEADERS,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    # qwen3 defaults to a long hidden reasoning trace before
                    # answering, which dominates latency. Disable it: the pipeline
                    # already structures reasoning in stages 4/5.
                    "think": False,
                    # Pin the model in memory indefinitely. On CPU-only hosts the
                    # cold reload (after Ollama's default 5-min idle unload) costs
                    # 60s+ and times out; warm calls are ~3s.
                    "keep_alive": -1,
                    "options": {"temperature": temperature},
                },
            )
            resp.raise_for_status()
            text = (resp.json().get("response") or "").strip()
            if text:
                _clear("ollama")
                _status["ollama"] = "ok"
                return text
            # 200 but empty — treat as a soft miss, don't trip the breaker.
            return None
    except Exception as e:
        _status["ollama"] = "unavailable"
        _trip("ollama", _OLLAMA_COOLDOWN_S)
        logger.warning("Ollama generate failed (falling back): %s", e)
        return None


async def _check_ollama_availability() -> bool:
    """Live /api/tags probe for /health (does not affect the generate cooldown)."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=2.0, read=5.0)) as client:
            r = await client.get(f"{_ollama_base()}/api/tags", headers=_OLLAMA_HEADERS)
            ok = r.status_code == 200
    except Exception:
        ok = False
    _status["ollama"] = "ok" if ok else "unavailable"
    logger.info("Ollama available: %s", ok)
    return ok


# ── Gemini ──────────────────────────────────────────────────────────────────────
def _gemini_key() -> str:
    return get_settings().gemini_api_key


def is_studio_key(key: str) -> bool:
    """True when `key` looks like a permanent Google AI Studio API key (AIza…).
    `AQ.`/ephemeral OAuth tokens pass a fresh probe but expire within hours — this
    lets startup/health warn before the chatbot silently degrades."""
    return key.startswith("AIza")


def _gemini_auth_headers(key: str) -> dict[str, str]:
    """Pick the right auth scheme by key shape. A permanent AI Studio key (AIza…)
    authenticates via the `x-goog-api-key` header; an `AQ.`/OAuth *access token*
    is a Bearer credential and is REJECTED on `x-goog-api-key` — it must go in the
    `Authorization` header. Sending an AQ. token on the wrong header is the #1 reason
    Gemini silently 400s and the chatbot "breaks"."""
    if is_studio_key(key):
        return {"x-goog-api-key": key, "Content-Type": "application/json"}
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _is_key_error(status_code: int, body: str = "") -> bool:
    """True when an HTTP error is the provider rejecting the key (expired/invalid/
    revoked) rather than a transient outage. Google returns 401/403 for permission
    problems and — notably — 400 `API_KEY_INVALID` for a bad/expired key."""
    if status_code in (401, 403):
        return True
    if status_code == 400:
        b = body.lower()
        return "api_key_invalid" in b or "api key not valid" in b or "api key" in b
    return False


def gemini_health_status() -> str:
    """Last known Gemini status for /health."""
    return _status["gemini"]


async def _check_gemini_availability() -> bool:
    key = _gemini_key()
    if not key:
        _status["gemini"] = "not configured"
        return False
    try:
        s = get_settings()
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=8.0)) as client:
            r = await client.get(f"{s.gemini_base_url}/v1beta/models", headers=_gemini_auth_headers(key))
            ok = r.status_code == 200
            _status["gemini"] = "ok" if ok else (
                "invalid_key" if _is_key_error(r.status_code, r.text) else "unavailable"
            )
    except Exception:
        _status["gemini"] = "unavailable"
        ok = False
    logger.info("Gemini available: %s (%s)", ok, _status["gemini"])
    return ok


_GEMINI_TIMEOUT = httpx.Timeout(connect=5.0, read=45.0, write=10.0, pool=5.0)


async def _gemini_generate(prompt: str, temperature: float) -> str | None:
    """Call Gemini generateContent. Returns text, or None on any failure (so the
    caller falls through to Groq). Trips the circuit breaker on failure."""
    key = _gemini_key()
    if not key:
        _status["gemini"] = "not configured"
        return None
    if _in_cooldown("gemini"):
        return None
    s = get_settings()
    url = f"{s.gemini_base_url}/v1beta/models/{s.gemini_model}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=_GEMINI_TIMEOUT) as client:
            resp = await client.post(
                url,
                headers=_gemini_auth_headers(key),
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
            if text:
                _clear("gemini")
                _status["gemini"] = "ok"
                return text
            return None
    except httpx.HTTPStatusError as e:
        body = ""
        try:
            body = e.response.text
        except Exception:
            pass
        if _is_key_error(e.response.status_code, body):
            _status["gemini"] = "invalid_key"
            logger.error(
                "Gemini rejected the API key (HTTP %s — expired/invalid/revoked). "
                "Check GEMINI_API_KEY (a permanent AIza… AI Studio key is most reliable; "
                "AQ.… tokens expire within hours). Falling back to Groq/Ollama.",
                e.response.status_code,
            )
        else:
            _status["gemini"] = "unavailable"
            logger.error("Gemini generate HTTP error: %s", e)
        _trip("gemini", _CLOUD_COOLDOWN_S)
        return None
    except Exception as e:
        _status["gemini"] = "unavailable"
        _trip("gemini", _CLOUD_COOLDOWN_S)
        logger.error("Gemini generate error: %s", e)
        return None


# ── Groq (OpenAI-compatible) ────────────────────────────────────────────────────
def _groq_key() -> str:
    return get_settings().groq_api_key


def groq_health_status() -> str:
    """Last known Groq status for /health."""
    return _status["groq"]


async def _check_groq_availability() -> bool:
    key = _groq_key()
    if not key:
        _status["groq"] = "not configured"
        return False
    try:
        s = get_settings()
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=8.0)) as client:
            r = await client.get(
                f"{s.groq_base_url}/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            ok = r.status_code == 200
            _status["groq"] = "ok" if ok else (
                "invalid_key" if _is_key_error(r.status_code, r.text) else "unavailable"
            )
    except Exception:
        _status["groq"] = "unavailable"
        ok = False
    logger.info("Groq available: %s (%s)", ok, _status["groq"])
    return ok


_GROQ_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


async def _groq_generate(prompt: str, temperature: float) -> str | None:
    """Call Groq's OpenAI-compatible chat/completions. Returns text, or None on any
    failure (so the caller falls through to the stub). Trips the breaker on failure."""
    key = _groq_key()
    if not key:
        _status["groq"] = "not configured"
        return None
    if _in_cooldown("groq"):
        return None
    s = get_settings()
    url = f"{s.groq_base_url}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=_GROQ_TIMEOUT) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": s.groq_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                return None
            text = (choices[0].get("message", {}).get("content") or "").strip()
            if text:
                _clear("groq")
                _status["groq"] = "ok"
                return text
            return None
    except httpx.HTTPStatusError as e:
        body = ""
        try:
            body = e.response.text
        except Exception:
            pass
        if _is_key_error(e.response.status_code, body):
            _status["groq"] = "invalid_key"
            logger.error(
                "Groq rejected the API key (HTTP %s). Check GROQ_API_KEY (gsk_…). "
                "Falling back to the stub.", e.response.status_code,
            )
        else:
            _status["groq"] = "unavailable"
            logger.error("Groq generate HTTP error: %s", e)
        _trip("groq", _CLOUD_COOLDOWN_S)
        return None
    except Exception as e:
        _status["groq"] = "unavailable"
        _trip("groq", _CLOUD_COOLDOWN_S)
        logger.error("Groq generate error: %s", e)
        return None


# ── Public API ──────────────────────────────────────────────────────────────────
async def generate_with_backend(
    prompt: str, model: str = MAIN_MODEL, temperature: float = 0.1
) -> tuple[str, str]:
    """Run the provider chain and return (text, backend) where backend is one of
    "ollama" | "gemini" | "groq" | "stub". Lets callers surface a degraded (stub)
    answer instead of silently serving templated boilerplate.

    Order: Ollama (local, primary) → Gemini → Groq → deterministic stub."""
    # 1. Ollama — local/LAN, free, primary.
    out = await _ollama_generate(prompt, model, temperature)
    if out is not None:
        return out, "ollama"
    # 2. Gemini — best-effort cloud.
    out = await _gemini_generate(prompt, temperature)
    if out is not None:
        return out, "gemini"
    # 3. Groq — reliable cloud fallback.
    out = await _groq_generate(prompt, temperature)
    if out is not None:
        return out, "groq"
    # 4. Everything down — deterministic stub.
    return _stub_response(prompt), "stub"


async def generate(prompt: str, model: str = MAIN_MODEL, temperature: float = 0.1) -> str:
    text, _backend = await generate_with_backend(prompt, model, temperature)
    return text


def reset_availability_cache():
    """Clear the circuit breaker and statuses so the next call re-probes every
    provider (e.g. after a server restart, or on each /health hit)."""
    _cooldown_until.clear()
    _status["ollama"] = "unknown"
    _status["gemini"] = "not configured"
    _status["groq"] = "not configured"


def _stub_response(prompt: str) -> str:
    """
    Deterministic fallback when no provider is reachable.
    Returns structured JSON stubs for classification prompts,
    and a plain-text stub for generation prompts.
    Used in development / CI without a GPU or any API key.
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
