"""
Stage 1 — Query Understanding.
Two orthogonal decisions made in parallel:
  1. Intent classifier  → what kind of query is this?
  2. Query characterizer → how much retrieval does it need?
  3. Entity extraction  → what are the key legal entities?
Plus calibrated clarification (ask once, only when answer-changing).
"""
import json
import re
import logging
from app.ai.models import QueryAnalysis, Intent, Complexity
from app.ai import llm_client

logger = logging.getLogger(__name__)

_CLASSIFY_PROMPT = """You are a query classifier for an AI legal assistant serving Bangladesh.
Classify the user query below. Respond ONLY with valid JSON, no markdown, no extra text.

Query: {query}

Output this exact JSON structure:
{{
  "intent": "rights_query|complaint_draft|case_lookup|emergency|general",
  "confidence": 0.0,
  "lang": "bn|en|mixed",
  "needs_retrieval": true,
  "complexity": "simple|medium|hard",
  "is_workflow_query": false,
  "historical_law": false,
  "entities": {{
    "relationships": [],
    "harm_types": [],
    "named_statutes": [],
    "jurisdiction_hint": "campus|national|unclear",
    "temporal": "ongoing|recent|past|unclear",
    "user_posture": "victim|witness|accused|inquirer"
  }}
}}

Classification rules:
- intent "rights_query": user wants to know what the law says or what their rights are
- intent "complaint_draft": user wants to draft FIR / GD / application / formal letter
- intent "case_lookup": user asks about a specific ongoing case
- intent "emergency": immediate physical danger — route to alert system
- intent "general": does not fit above (greeting, unclear, out of scope)
- complexity "simple": no retrieval needed (e.g. "What does FIR stand for?")
- complexity "medium": single statute area, straightforward question
- complexity "hard": multi-statute reasoning, cross-jurisdictional, ambiguous facts
- is_workflow_query: true if the user asks "what should I DO" or "how do I"
- needs_retrieval: false only for definitional questions answerable without docs"""

_REWRITE_PROMPT = """Rewrite the following legal query for document retrieval. Be precise and use legal terminology.
Entity context: {entity_context}
Original query: {query}

Output ONLY JSON (no markdown):
{{"english": "<clean English rewrite with legal terms>", "bangla": "<পরিষ্কার বাংলা পুনর্লেখা>"}}"""

# Rule-based intent patterns (fallback when LLM unavailable)
_INTENT_KEYWORDS: dict[Intent, list[str]] = {
    Intent.emergency: [
        r'\bemergency\b', r'\bdanger\b.*\bnow\b', r'\bবিপদ\b', r'\bহামলা\b',
    ],
    Intent.complaint_draft: [
        r'\bdraft\b', r'\bwrite\b', r'\bapplication\b', r'\bfir\b', r'\bgd\b',
        r'\bgeneral\s+diary\b', r'\bলিখ', r'\bড্রাফট', r'\bআবেদন',
    ],
    Intent.case_lookup: [
        r'\bcase\s+status\b', r'\bmy\s+case\b', r'\btracking\b',
        r'\bcmp-\d', r'\bntl-\d',
    ],
    Intent.rights_query: [
        r'\brights?\b', r'\blaw\b', r'\bpunishment\b', r'\bsection\b',
        r'\bact\b', r'\bwhat\s+(can|should|if)\b', r'\bঅধিকার\b', r'\bআইন\b',
        r'\bধারা\b', r'\bশাস্তি\b', r'\bকী\s+করব',
    ],
}


async def analyze_query(query: str, mode: str = "national") -> QueryAnalysis:
    """
    Two-axis classification: intent + retrieval characterization.
    LLM-primary with rule-based fallback.
    """
    prompt = _CLASSIFY_PROMPT.format(query=query)
    raw = await llm_client.generate(prompt, model=llm_client.SMALL_MODEL)

    analysis: QueryAnalysis | None = None
    try:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            analysis = QueryAnalysis(
                intent=Intent(data.get("intent", "general")),
                intent_confidence=float(data.get("confidence", 0.5)),
                lang=data.get("lang", "en"),
                needs_retrieval=bool(data.get("needs_retrieval", True)),
                complexity=Complexity(data.get("complexity", "medium")),
                is_workflow_query=bool(data.get("is_workflow_query", False)),
                historical_law=bool(data.get("historical_law", False)),
                entities=data.get("entities", {}),
            )
    except Exception as e:
        logger.debug("LLM classify parse failed (%s) — rule-based fallback", e)

    if analysis is None:
        analysis = _rule_based_analyze(query, mode)

    # Override jurisdiction from app mode
    if not analysis.entities.get("jurisdiction_hint") or analysis.entities["jurisdiction_hint"] == "unclear":
        analysis.entities["jurisdiction_hint"] = "campus" if mode == "campus" else "national"

    # Calibrated clarification — only when a missing fact would change the legal answer
    if analysis.complexity == Complexity.hard and analysis.intent_confidence < 0.6:
        who = _ambiguous_who(query)
        if who:
            analysis.clarification_needed = who

    return analysis


async def rewrite_query(
    query: str,
    lang: str,
    entities: dict,
) -> tuple[str, str]:
    """
    Dual-language query rewrite for maximum retrieval recall.
    Returns (english_rewrite, bangla_rewrite).
    Both are used for dense + sparse retrieval.
    """
    entity_context = ", ".join(filter(None, [
        *entities.get("harm_types", []),
        *entities.get("named_statutes", []),
        *entities.get("relationships", []),
    ]))
    prompt = _REWRITE_PROMPT.format(entity_context=entity_context or "none", query=query)
    raw = await llm_client.generate(prompt, model=llm_client.SMALL_MODEL)
    try:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            d = json.loads(m.group())
            return d.get("english", query), d.get("bangla", query)
    except Exception:
        pass
    return query, query


# ── Fallback rule-based classifier ──────────────────────────────

def _rule_based_analyze(query: str, mode: str) -> QueryAnalysis:
    ql = query.lower()
    detected_lang = _detect_lang(query)

    intent = Intent.general
    for candidate, patterns in _INTENT_KEYWORDS.items():
        if any(re.search(p, ql) for p in patterns):
            intent = candidate
            break

    legal_terms = ['act', 'section', 'statute', 'crpc', 'penal', 'tribunal',
                   'আইন', 'ধারা', 'আদালত', 'মামলা', 'অভিযোগ']
    has_legal = any(t in ql for t in legal_terms)
    words = len(query.split())

    if words < 10 and not has_legal:
        complexity = Complexity.simple
    elif words > 40 or (has_legal and words > 20):
        complexity = Complexity.hard
    else:
        complexity = Complexity.medium

    workflow_words = ['how', 'steps', 'what should', 'what to do', 'procedure',
                      'কীভাবে', 'কী করব', 'কি করতে হবে', 'পদ্ধতি']
    is_workflow = any(w in ql for w in workflow_words)

    return QueryAnalysis(
        intent=intent,
        intent_confidence=0.65,
        lang=detected_lang,
        needs_retrieval=(complexity != Complexity.simple),
        complexity=complexity,
        is_workflow_query=is_workflow,
        historical_law=False,
        entities={
            "relationships": [],
            "harm_types": [],
            "named_statutes": [],
            "jurisdiction_hint": "campus" if mode == "campus" else "national",
            "temporal": "unclear",
            "user_posture": "inquirer",
        },
    )


def _detect_lang(text: str) -> str:
    bangla = len(re.findall(r'[ঀ-৿]', text))
    ascii_ = len(re.findall(r'[a-zA-Z]', text))
    if bangla > ascii_ * 0.5:
        return "mixed" if ascii_ > 5 else "bn"
    return "en"


def _ambiguous_who(query: str) -> str | None:
    """Return a clarifying question if the query has ambiguous subjects."""
    ambiguous = re.search(r'\b(he|she|they|someone|person|him|her)\b', query.lower())
    if ambiguous:
        return ("Could you clarify who did this to you (relationship to them) and "
                "approximately when it happened? This helps me find the most relevant legal provision.")
    return None
