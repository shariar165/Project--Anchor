"""
Unified LLM client for the Core API's own AI features.

Provider order (each tried in turn; first non-empty answer wins):
  1. Ollama — local inference (OLLAMA_BASE_URL, e.g. http://192.168.0.111:11434).
              Free, fast on the LAN, and the primary generator.
  2. Gemini — Google Generative Language API, via `gemini_client` (handles the
              AIza… vs AQ.… Bearer-auth distinction).
  3. Groq   — OpenAI-compatible API (GROQ_API_KEY, permanent gsk_ keys). The reliable
              cloud fallback so an expired Gemini token never dies.
  4. None   — every provider unreachable; callers fall back to their own template.

Seamless, fast failover: a provider that just failed is put on a short cooldown
(circuit breaker) so subsequent calls skip it with zero network cost, and tight
connect timeouts mean a powered-off box fails over in ~2s instead of hanging.

Mirrors services/rag/app/pipeline/llm_client.py — kept in sync intentionally.
"""
import logging
import time

import httpx

from app.config import get_settings
from app.services import gemini_client

logger = logging.getLogger(__name__)

# ── Circuit breaker ─────────────────────────────────────────────────────────────
_cooldown_until: dict[str, float] = {}
_OLLAMA_COOLDOWN_S = 30.0
_CLOUD_COOLDOWN_S = 60.0

# Ollama serves an HTML interstitial behind an ngrok free tunnel without this header;
# harmless against a direct/local Ollama.
_OLLAMA_HEADERS = {"ngrok-skip-browser-warning": "true"}


def _in_cooldown(provider: str) -> bool:
    return time.monotonic() < _cooldown_until.get(provider, 0.0)


def _trip(provider: str, seconds: float) -> None:
    _cooldown_until[provider] = time.monotonic() + seconds


def _clear(provider: str) -> None:
    _cooldown_until.pop(provider, None)


def _is_key_error(status_code: int, body: str = "") -> bool:
    if status_code in (401, 403):
        return True
    if status_code == 400:
        b = body.lower()
        return "api_key_invalid" in b or "api key not valid" in b or "api key" in b
    return False


async def _ollama_generate(prompt: str, model: str, temperature: float, read_timeout: float) -> str | None:
    if _in_cooldown("ollama"):
        return None
    ollama_url = getattr(get_settings(), "ollama_base_url", "http://localhost:11434")
    timeout = httpx.Timeout(connect=2.0, read=read_timeout, write=10.0, pool=2.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{ollama_url}/api/generate",
                headers=_OLLAMA_HEADERS,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                    "keep_alive": -1,
                    "options": {"temperature": temperature},
                },
            )
            resp.raise_for_status()
            text = (resp.json().get("response") or "").strip()
            if text:
                _clear("ollama")
                return text
            return None
    except Exception as exc:
        _trip("ollama", _OLLAMA_COOLDOWN_S)
        logger.warning("Ollama generate failed (falling back): %s", exc)
        return None


async def _groq_generate(prompt: str, temperature: float, read_timeout: float) -> str | None:
    settings = get_settings()
    key = getattr(settings, "groq_api_key", "")
    if not key:
        return None
    if _in_cooldown("groq"):
        return None
    base = getattr(settings, "groq_base_url", "https://api.groq.com/openai/v1")
    model = getattr(settings, "groq_model", "llama-3.3-70b-versatile")
    timeout = httpx.Timeout(connect=5.0, read=read_timeout, write=10.0, pool=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            choices = resp.json().get("choices") or []
            if not choices:
                return None
            text = (choices[0].get("message", {}).get("content") or "").strip()
            if text:
                _clear("groq")
                return text
            return None
    except httpx.HTTPStatusError as exc:
        _body = ""
        try:
            _body = exc.response.text
        except Exception:
            pass
        if _is_key_error(exc.response.status_code, _body):
            logger.error(
                "Groq rejected the API key (HTTP %s). Check GROQ_API_KEY (gsk_…).",
                exc.response.status_code,
            )
        else:
            logger.warning("Groq generate failed (falling back): %s", exc)
        _trip("groq", _CLOUD_COOLDOWN_S)
        return None
    except Exception as exc:
        _trip("groq", _CLOUD_COOLDOWN_S)
        logger.warning("Groq generate failed (falling back): %s", exc)
        return None


async def generate(
    prompt: str,
    *,
    temperature: float = 0.2,
    timeout: float | None = None,
    model: str = "qwen3:1.7b",
) -> str | None:
    """Run the provider chain: Ollama → Gemini → Groq. Returns the generated text, or
    None when every provider is unreachable (callers fall back to their own template).

    `timeout` is the per-provider read timeout (connect stays tight for fast failover);
    defaults to 45s. `model` is the Ollama model tag.
    """
    read_timeout = timeout if timeout is not None else 45.0

    # 1. Ollama — local/LAN, free, primary.
    out = await _ollama_generate(prompt, model, temperature, read_timeout)
    if out is not None:
        return out
    # 2. Gemini — best-effort cloud (gemini_client applies the AQ. Bearer fix).
    if not _in_cooldown("gemini"):
        out = await gemini_client.generate(prompt, temperature=temperature, timeout=min(read_timeout, 45.0))
        if out is not None:
            _clear("gemini")
            return out
        # gemini_client returns None on a bad key too; back off briefly so we don't
        # re-hit an expired token on every call.
        if gemini_client.is_configured():
            _trip("gemini", _CLOUD_COOLDOWN_S)
    # 3. Groq — reliable cloud fallback.
    out = await _groq_generate(prompt, temperature, min(read_timeout, 30.0))
    if out is not None:
        return out
    # 4. Everything down.
    return None
