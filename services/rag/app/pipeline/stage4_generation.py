"""
Stage 4 — Generation with Legal Reasoning Scaffold.

Forces the LLM to reason step by step:
  SITUATION → APPLICABLE LAW → APPLICATION → PRACTICAL STEP → SCOPE LIMITS.

Restating the situation first grounds generation in the actual question (anti-hallucination).
Every claim must cite a chunk ID in [brackets].
"""
import json
import re
import logging
from app.pipeline.models import RetrievedChunk, QueryAnalysis
from app.pipeline import llm_client
from app.pipeline import skill_loader

logger = logging.getLogger(__name__)


def _ground(prompt: str) -> str:
    """Prepend the bd-legal-answer skill grounding (statute cues, citation + authority rules,
    disclaimer) ahead of the reasoning-scaffold prompt. No-op when the skill tree is absent."""
    ground = skill_loader.grounding("bd-legal-answer")
    return f"{ground}\n\n{prompt}" if ground else prompt

_GENERATION_PROMPT = """You are Anchor AI — a knowledgeable, compassionate legal companion for Bangladesh.
Using ONLY the provided context documents, analyze the user's situation step by step.
Cite each legal claim with the source chunk ID in [brackets].
If the context does not support a step, say so explicitly — never guess or confabulate.

User query: {query}
Context ({mode} mode):

{context}

Respond in {output_lang}. Analyze using exactly this structure:

1. SITUATION: Restate the user's situation in neutral, precise terms.

2. APPLICABLE LAW: Which statute, rule, or precedent applies? [cite chunk_id]

3. APPLICATION: Apply the law to the user's specific facts. Note any missing facts that would change the analysis.

4. PRACTICAL STEP: What should the user do next, concretely and immediately? [cite workflow chunk if available]

5. SCOPE LIMITS: What this answer does NOT cover; when a lawyer is necessary.

After your analysis (on a separate line), output:
CITATIONS_JSON: [array of {{"id": "chunk_id", "title": "Act Name § Section", "source": "corpus or web"}}]

Tone: knowledgeable friend, not a search engine. Be direct and actionable."""

_STRICT_PROMPT = """You are Anchor AI — a legal assistant for Bangladesh.
Answer ONLY from the provided context. Every single claim must be directly supported by the context.
If you cannot find support, write: "I cannot find reliable information on this in my legal corpus."
Do not add anything not in the context.

Query: {query}

Context:
{context}

Respond in {output_lang}. Cite sources as [chunk_id] after each claim.
After your answer, output:
CITATIONS_JSON: [array of {{"id": "chunk_id", "title": "Act Name § Section", "source": "corpus or web"}}]"""


def _format_context(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks for prompt injection."""
    parts = []
    for chunk in chunks:
        m = chunk.metadata
        header = f"[{chunk.chunk_id}] {m.act_name}"
        if m.chapter:
            header += f" › Chapter {m.chapter}"
        if m.section:
            header += f" § {m.section}"
        header += f" | rank={m.authority_rank} | status={m.amendment_status}"
        if chunk.source == "web":
            header += " | ⚠ WEB SOURCE (lower authority)"
        parts.append(f"{header}\n{chunk.text[:800]}")
    return "\n\n---\n\n".join(parts)


def _extract_citations(raw: str, chunks: list[RetrievedChunk]) -> list[dict]:
    """Extract CITATIONS_JSON block; fallback to inline [chunk_id] references."""
    # Try structured block first
    m = re.search(r'CITATIONS_JSON:\s*(\[.*?\])', raw, re.DOTALL | re.IGNORECASE)
    if m:
        try:
            cites = json.loads(m.group(1))
            if isinstance(cites, list):
                return cites
        except Exception:
            pass

    # Fallback: find inline [chunk_id] references
    chunk_map = {c.chunk_id: c for c in chunks}
    seen: set[str] = set()
    cites = []
    for cid in re.findall(r'\[([a-zA-Z0-9_\-]+)\]', raw):
        if cid in chunk_map and cid not in seen:
            c = chunk_map[cid]
            title = c.metadata.act_name
            if c.metadata.section:
                title += f" § {c.metadata.section}"
            cites.append({"id": cid, "title": title, "source": c.source})
            seen.add(cid)
    return cites


def _clean_output(raw: str) -> str:
    """Strip CITATIONS_JSON block from the user-facing answer."""
    cleaned = re.sub(r'CITATIONS_JSON:.*', '', raw, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


async def generate_response(
    query: str,
    chunks: list[RetrievedChunk],
    analysis: QueryAnalysis,
    mode: str = "national",
    output_lang: str = "English",
) -> tuple[str, list[dict], str]:
    """Primary generation: legal reasoning scaffold with citation grounding.
    Returns (answer, citations, backend) — backend is "gemini"|"ollama"|"stub"."""
    context = _format_context(chunks)
    prompt = _ground(_GENERATION_PROMPT.format(
        query=query,
        mode=mode,
        output_lang=output_lang,
        context=context,
    ))
    raw, backend = await llm_client.generate_with_backend(
        prompt, model=llm_client.MAIN_MODEL, temperature=0.15
    )
    citations = _extract_citations(raw, chunks)
    answer = _clean_output(raw)
    return answer, citations, backend


async def generate_strict(
    query: str,
    chunks: list[RetrievedChunk],
    output_lang: str = "English",
) -> tuple[str, list[dict], str]:
    """Stricter re-generation after claim verification fails first attempt.
    Returns (answer, citations, backend) — backend is "gemini"|"ollama"|"stub"."""
    context = _format_context(chunks)
    prompt = _ground(_STRICT_PROMPT.format(query=query, context=context, output_lang=output_lang))
    raw, backend = await llm_client.generate_with_backend(
        prompt, model=llm_client.MAIN_MODEL, temperature=0.05
    )
    citations = _extract_citations(raw, chunks)
    answer = _clean_output(raw)
    return answer, citations, backend
