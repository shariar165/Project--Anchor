"""AI pre-screening gate for Verification Feed posts."""
import asyncio
import re
from app.config import get_settings

# Keywords that trigger an immediate block (safety)
_BLOCK_PATTERNS = [
    re.compile(r"\b(kill\s+yourself|kys|suicide\s+method|how\s+to\s+die)\b", re.I),
    re.compile(r"\b(child\s+porn|cp\s+link|csam)\b", re.I),
    re.compile(r"(ignore\s+previous\s+instructions|disregard\s+all\s+prior)", re.I),
    re.compile(r"\b(nigger|faggot|chink|spic)\b", re.I),
]

# Per-category keyword hints — at least one must appear (very lenient)
_CATEGORY_HINTS: dict[str, list[str]] = {
    "incident": [
        "accident", "fire", "collapse", "explosion", "robbery", "crash", "collision",
        "flood", "injured", "victim", "emergency", "ambulance", "police", "হামলা",
        "আগুন", "দুর্ঘটনা",
    ],
    "missing_person": [
        "missing", "lost", "disappeared", "last seen", "search", "kidnap", "abduct",
        "নিখোঁজ", "হারিয়ে", "খোঁজ",
    ],
    "road": [
        "road", "traffic", "highway", "street", "bridge", "jam", "block", "lane",
        "pothole", "signal", "রাস্তা", "যানজট", "সড়ক",
    ],
    "safety": [
        "danger", "hazard", "unsafe", "warning", "suspicious", "threat", "gas",
        "leak", "alert", "beware", "সতর্ক", "বিপদ",
    ],
    "civic_event": [
        "event", "drive", "campaign", "announcement", "notice", "program",
        "community", "public", "initiative", "কর্মসূচি", "অনুষ্ঠান",
    ],
}

_URL_RE = re.compile(r"https?://\S+")


def _keyword_safety_check(text: str) -> dict | None:
    for pat in _BLOCK_PATTERNS:
        if pat.search(text):
            return {"verdict": "block", "reason": "content_policy_violation", "flags": ["safety"]}
    return None


def _spam_check(text: str) -> dict | None:
    words = text.split()
    if len(words) < 10:
        return {"verdict": "manual_review", "reason": "too_short", "flags": ["spam"]}
    urls = _URL_RE.findall(text)
    if len(urls) > 5:
        return {"verdict": "manual_review", "reason": "excessive_urls", "flags": ["spam"]}
    if text == text.upper() and len(words) > 5:
        return {"verdict": "manual_review", "reason": "all_caps", "flags": ["spam"]}
    return None


def _category_check(text: str, category: str) -> dict | None:
    hints = _CATEGORY_HINTS.get(category, [])
    text_lower = text.lower()
    if hints and not any(h in text_lower for h in hints):
        return {"verdict": "manual_review", "reason": "category_mismatch", "flags": ["category"]}
    return None


async def _run(title: str, body: str, category: str) -> dict:
    combined = f"{title} {body}"

    result = _keyword_safety_check(combined)
    if result:
        return result

    result = _spam_check(body)
    if result:
        return result

    result = _category_check(combined, category)
    if result:
        return result

    return {"verdict": "pass", "reason": "", "flags": []}


async def run_prescreen(title: str, body: str, category: str) -> dict:
    settings = get_settings()
    try:
        return await asyncio.wait_for(
            _run(title, body, category),
            timeout=settings.ai_prescreen_timeout_seconds,
        )
    except asyncio.TimeoutError:
        return {"verdict": "manual_review", "reason": "timeout", "flags": []}
