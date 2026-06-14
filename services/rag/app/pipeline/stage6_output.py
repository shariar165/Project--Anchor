"""
Stage 6 — Output Adaptation.

- Language: respond in user's input language
- Register: match the user's formality level
- Citations: attach formatted source references
- Web-source notice: clearly marked if corrective web search fired
- Disclaimer: always injected (last line of defence)

Also contains: safety response templates, exit ramp responses.
"""
from app.pipeline.models import RetrievedChunk

DISCLAIMER_EN = (
    "\n\n---\n*AI-generated legal guidance — not a substitute for advice from a "
    "licensed professional. For your specific situation, consult a verified lawyer.*"
)
DISCLAIMER_BN = (
    "\n\n---\n*এটি AI-নির্মিত আইনি পরামর্শ — লাইসেন্সপ্রাপ্ত আইনজীবীর পরামর্শের বিকল্প নয়। "
    "আপনার নির্দিষ্ট পরিস্থিতিতে একজন যাচাইকৃত আইনজীবীর সাথে পরামর্শ করুন।*"
)

_EXIT_RAMP_EN = """I'm not able to give you a reliable answer to this specific question from my legal corpus.

**Why:** The available sources don't cover this situation with enough confidence to guide you safely.

**What to do next:**
1. Connect with a verified lawyer from the Anchor directory who specialises in this area
2. If urgent, contact the nearest legal aid office
3. For free legal aid: Bangladesh Legal Aid Services Trust (BLAST) — 02-9880064

A lawyer who can review your specific documents and circumstances will give you much better guidance than I can here.

*This is an AI system — it should not be your only source of legal advice.*"""

_EXIT_RAMP_BN = """এই নির্দিষ্ট প্রশ্নের জন্য আমার আইনি কর্পাস থেকে নির্ভরযোগ্য উত্তর দিতে পারছি না।

**কারণ:** উপলব্ধ উৎসগুলি এই পরিস্থিতি পর্যাপ্ত আস্থার সাথে কভার করে না।

**পরবর্তী পদক্ষেপ:**
১. Anchor ডিরেক্টরি থেকে বিশেষজ্ঞ একজন যাচাইকৃত আইনজীবীর সাথে যোগাযোগ করুন
২. বিনামূল্যে আইনি সহায়তা: বাংলাদেশ লিগ্যাল এইড সার্ভিসেস ট্রাস্ট (BLAST) — 02-9880064

*এটি একটি AI সিস্টেম — এটি আপনার একমাত্র আইনি পরামর্শের উৎস হওয়া উচিত নয়।*"""

_EMERGENCY_EN = """**EMERGENCY DETECTED** — Please use the Alert feature immediately.

1. Tap the red **Hold** button on the Home screen
2. Hold for 4 seconds to broadcast your location to trusted contacts
3. Your nearest verified responder will be notified

**Call now if in immediate danger:**
- Police: **999**
- Women & Child Affairs: **109**
- National Emergency: **999**

*I am routing you to emergency resources — not answering as a legal query right now.*"""

_CRISIS_EN = """I hear you, and I want you to know you are not alone.

Please reach out right now:
- **Kaan Pete Roi** (emotional support, 24/7): 01779-554391
- **National Mental Health Helpline**: 16789
- A trusted friend, family member, or teacher

You can also use the Anchor trusted contacts feature to quietly alert someone you trust.

*I'm an AI and cannot provide crisis support. Please call one of the numbers above.*"""


def build_safety_response(verdict: str, lang: str = "en") -> str:
    if verdict == "emergency":
        return _EMERGENCY_EN
    if verdict == "crisis":
        return _CRISIS_EN
    if verdict == "injection":
        return "I can only answer questions about Bangladeshi law and campus governance."
    if verdict == "minor":
        return (
            "It sounds like you may be a young person in a difficult situation. "
            "Please talk to a trusted adult — a teacher, counsellor, or family member. "
            "You can also call: **Child Helpline: 1098** (Bangladesh, free)."
        )
    if verdict == "coercion":
        return (
            "You are not alone. If someone is watching, you can tap anywhere on screen to close this. "
            "When you are safe, use the Alert feature or contact: **Police 999** or **Women's Helpline 109**."
        )
    return "I'm unable to process this request. Please contact support or call emergency services."


def build_exit_ramp(lang: str = "en") -> str:
    return _EXIT_RAMP_BN if lang == "bn" else _EXIT_RAMP_EN


def adapt_output(
    answer: str,
    citations: list[dict],
    lang: str,
    web_search_fired: bool,
) -> str:
    """
    Final output adaptation:
    1. Web-source notice (if corrective web search fired)
    2. Formatted citations block
    3. Injected disclaimer (always)
    """
    # Web source notice
    web_cites = [c for c in citations if c.get("source") == "web"]
    if web_search_fired and web_cites:
        note_en = (
            "\n\n*Note: Some information above is sourced from the web "
            "(lower authority than the curated legal corpus). Verify before acting.*"
        )
        note_bn = (
            "\n\n*দ্রষ্টব্য: উপরের কিছু তথ্য ওয়েব থেকে নেওয়া হয়েছে "
            "(আইনি কর্পাসের চেয়ে কম কর্তৃপক্ষ)। ব্যবস্থা নেওয়ার আগে যাচাই করুন।*"
        )
        answer += note_bn if lang == "bn" else note_en

    # Citations block
    corpus_cites = [c for c in citations if c.get("source") != "web"]
    if corpus_cites:
        cite_block = "\n\n**Sources:**"
        for c in corpus_cites:
            title = c.get("title") or c.get("id", "")
            cite_block += f"\n- {title}"
        if web_cites:
            cite_block += "\n- *(web sources — lower authority)*"
        answer += cite_block

    # Disclaimer (always last)
    answer += DISCLAIMER_BN if lang == "bn" else DISCLAIMER_EN

    return answer
