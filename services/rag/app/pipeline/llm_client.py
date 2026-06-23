"""
Async LLM client for Anchor AI.
Primary: Ollama inference (URL from OLLAMA_BASE_URL env var, defaults to localhost:11434).
Fallback: Deterministic stub when Ollama is unreachable (CI / dev without GPU).
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


async def generate(prompt: str, model: str = MAIN_MODEL, temperature: float = 0.1) -> str:
    if not await _check_availability():
        return _stub_response(prompt)
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
            return resp.json().get("response", "")
    except Exception as e:
        logger.error("Ollama generate error: %s", e)
        return _stub_response(prompt)


def reset_availability_cache():
    """Call this to re-probe Ollama (e.g. after a server restart)."""
    global _available
    _available = None


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
