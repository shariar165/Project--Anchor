"""
Notice generation service — drafts campus notices with Ollama (the same local LLM
that powers the main app's chatbot), grounded in Daffodil International University
notice conventions.

Mirrors the Ollama-call pattern in `services/timetable_solver.py` and
`services/rag/app/pipeline/llm_client.py`: a single `/api/generate` call with a low
temperature and a graceful fallback so the feature never hard-fails when Ollama is
offline (CI / dev without a GPU). The DIU drafting knowledge embedded below is the
same body documented in `skills/diu-notice-generator.skill` — keep them in sync.
"""
import json
import logging
import re

import httpx

from app.config import get_settings
from app.services import skill_loader

logger = logging.getLogger(__name__)

# ── DIU notice-drafting knowledge ──
# The canonical copy lives in skills/src/diu-notice-generator/references/grounding.md and is
# loaded at runtime by skill_loader (single source of truth). This literal is kept only as the
# offline fallback for when the skill tree isn't shipped alongside the service.
_DIU_STYLE = """\
You draft official notices for Daffodil International University (DIU), a private \
university in Dhaka, Bangladesh. Follow these conventions:

- Voice: formal, institutional, and clear — issued by the Registrar's Office.
- Open with a salutation ("Dear Students," or in Bangla "প্রিয় শিক্ষার্থীবৃন্দ,").
- State the key facts first: what, when (dates/times), where, and any action required.
- Keep it concise: 1–3 short paragraphs. No emojis, no marketing language.
- Common notice categories: examination, library, holiday/closure, fee/payment,
  event/seminar, hostel, and general administrative.
- Always close with the sign-off:
      Registrar's Office
      Daffodil International University
  (in Bangla: "রেজিস্ট্রার কার্যালয়\\nড্যাফোডিল ইন্টারন্যাশনাল ইউনিভার্সিটি")
"""


def _build_prompt(*, prompt: str, language: str, tone: str | None,
                  audience: str | None, subject: str | None) -> str:
    out_lang = "Bangla (Bengali)" if language == "bn" else "English"
    tone_line = f"Tone: {tone}.\n" if tone else ""
    audience_line = f"Audience: {audience}.\n" if audience else ""
    subject_line = (
        f'A working subject line is: "{subject}". Refine it if helpful.\n'
        if subject else ""
    )
    style = skill_loader.grounding("diu-notice-generator", fallback=_DIU_STYLE)
    return (
        f"{style}\n"
        f"Write the notice entirely in {out_lang}.\n"
        f"{tone_line}{audience_line}{subject_line}"
        f"\nThe administrator describes the notice as:\n{prompt}\n\n"
        'Return ONLY a single JSON object, no commentary, in this exact shape:\n'
        '{"subject": "<short subject line>", "body": "<the full notice text>"}\n'
        "The body must include the salutation and the Registrar sign-off. "
        "Use \\n for line breaks inside the JSON strings."
    )


def _strip_think(text: str) -> str:
    """qwen3 emits <think>…</think> reasoning blocks — remove them."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _fallback(*, prompt: str, language: str, subject: str | None) -> dict:
    """Templated notice used when Ollama is unreachable, so the button still works."""
    if language == "bn":
        body = (
            "প্রিয় শিক্ষার্থীবৃন্দ,\n\n"
            f"{prompt.strip()}\n\n"
            "বিস্তারিত জানার জন্য সংশ্লিষ্ট কার্যালয়ে যোগাযোগ করুন।\n\n"
            "রেজিস্ট্রার কার্যালয়\nড্যাফোডিল ইন্টারন্যাশনাল ইউনিভার্সিটি"
        )
        subj = subject or "ড্যাফোডিল ইন্টারন্যাশনাল ইউনিভার্সিটি — বিজ্ঞপ্তি"
    else:
        body = (
            "Dear Students,\n\n"
            f"{prompt.strip()}\n\n"
            "For further details, please contact the relevant office.\n\n"
            "Registrar's Office\nDaffodil International University"
        )
        subj = subject or "Daffodil International University — Notice"
    return {"subject": subj, "body": body, "language": language, "ai_generated": False}


async def generate_notice(*, prompt: str, language: str = "en", tone: str | None = None,
                          audience: str | None = None, subject: str | None = None) -> dict:
    """Draft a DIU notice. Returns {subject, body, language, ai_generated}."""
    settings = get_settings()
    model = getattr(settings, "notice_ai_model", "qwen3:1.7b")
    ollama_url = getattr(settings, "ollama_base_url", "http://localhost:11434")
    full_prompt = _build_prompt(
        prompt=prompt, language=language, tone=tone, audience=audience, subject=subject
    )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": 0.3},
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")
    except Exception as exc:
        logger.warning("Notice generation falling back (Ollama unavailable): %s", exc)
        return _fallback(prompt=prompt, language=language, subject=subject)

    cleaned = _strip_think(raw)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            body = (data.get("body") or "").strip()
            if body:
                return {
                    "subject": (data.get("subject") or subject or "").strip()
                    or ("ড্যাফোডিল ইন্টারন্যাশনাল ইউনিভার্সিটি — বিজ্ঞপ্তি"
                        if language == "bn"
                        else "Daffodil International University — Notice"),
                    "body": body,
                    "language": language,
                    "ai_generated": True,
                }
        except json.JSONDecodeError:
            pass

    # Model returned prose instead of JSON — treat the cleaned text as the body.
    if cleaned:
        return {
            "subject": subject or (
                "ড্যাফোডিল ইন্টারন্যাশনাল ইউনিভার্সিটি — বিজ্ঞপ্তি"
                if language == "bn" else "Daffodil International University — Notice"
            ),
            "body": cleaned,
            "language": language,
            "ai_generated": True,
        }
    return _fallback(prompt=prompt, language=language, subject=subject)
