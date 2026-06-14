"""
Stage 0 — Safety Pre-Flight.
Runs before any routing. Fast keyword pre-filter + optional small-LLM pass.
Some queries must never reach the RAG pipeline.
"""
import re
from app.pipeline.models import SafetyVerdict

# Pattern lists (Bangla + English). Each list is low-latency regex.
_EMERGENCY = [
    r'\bসাহায্য\s+কর\b', r'\bসাহায্য\s+করুন\b',   # Bangla help (urgent forms)
    r'\bhelp\s+me\s+(?:now|please|fast|quick)\b',      # "help me now/fast" only
    r'\battack(ing|ed)?\b',
    r'\bবিপদ\b', r'\bhe\s+is\s+here\b', r'\bshe\s+is\s+here\b',
    r'\bchasing\s+me\b', r'\bfollowing\s+me\b', r'\bdanger\b.*\bnow\b',
    r'\bsomeone\s+is\s+(?:hurting|attacking|threatening)\b',
]

_CRISIS = [
    r'\bsuicide\b', r'\bkill\s+myself\b', r'\bself[- ]harm\b',
    r'\bআত্মহত্যা\b', r'\bজীবন\s+শেষ\b', r'\bবাঁচতে\s+চাই\s+না\b',
    r'\bwant\s+to\s+die\b', r'\bend\s+my\s+life\b',
]

_MINOR = [
    r'\b(?:i\s+am|i\'m)\s+(?:only\s+)?\d{1,2}(?:\s+years?\s+old)?\b',
    r'\bchild\b.{0,20}\babuse\b', r'\bminor\b.{0,20}\bvictim\b',
    r'\bশিশু\b.{0,20}\bনির্যাতন\b',
]

_COERCION = [
    r'\bhe(?:\'s|\s+is)\s+making\s+me\b',
    r'\bwatching\s+me\s+type\b',
    r'\bcan(?:\'t|\s+not)\s+talk\b.{0,20}\bsafe\b',
]

_INJECTION = [
    r'ignore\s+(?:previous|all|your)\s+instructions?',
    r'you\s+are\s+now\s+(?:a\s+)?(?:different|new)',
    r'pretend\s+(?:you\s+are|to\s+be)',
    r'system\s+prompt',
    r'disregard\s+(?:all|your)',
    r'act\s+as\s+(?:a\s+)?(?:different|evil|unrestricted)',
    r'jailbreak',
    r'DAN\b',
]


def _matches(text: str, patterns: list[str]) -> bool:
    tl = text.lower()
    return any(re.search(p, tl) for p in patterns)


def check_safety(query: str) -> tuple[SafetyVerdict, str]:
    """
    Returns (verdict, reason).
    SafetyVerdict.safe → proceed with RAG pipeline.
    All other verdicts → short-circuit to specialised handlers.
    Runs in <1 ms for keyword hits.
    """
    if _matches(query, _INJECTION):
        return SafetyVerdict.injection, "Prompt injection attempt detected."
    if _matches(query, _EMERGENCY):
        return SafetyVerdict.emergency, "Emergency signal detected."
    if _matches(query, _CRISIS):
        return SafetyVerdict.crisis, "Crisis signal detected."
    if _matches(query, _MINOR):
        return SafetyVerdict.minor, "Minor in distress signal detected."
    if _matches(query, _COERCION):
        return SafetyVerdict.coercion, "Coercion signal detected."
    return SafetyVerdict.safe, ""
