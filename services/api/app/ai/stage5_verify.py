"""
Stage 5 — Claim-Level Verification.

Upgrade from v1 "ask the same LLM if it was correct" (weak).
Instead: decompose answer into atomic claims → verify each claim against
retrieved chunks via LLM entailment check.

Decision rules:
  all supported            → pass
  ≤1 minor unsupported    → strip that claim, pass
  several unsupported      → regenerate once
  any contradicted         → regenerate once
  still failing            → exit ramp
"""
import json
import re
import logging
from app.ai.models import RetrievedChunk, VerificationResult
from app.ai import llm_client

logger = logging.getLogger(__name__)

_DECOMPOSE_PROMPT = """Extract the atomic factual and legal claims from the following answer.
Each claim must be a single, independently verifiable statement.
Output ONLY a JSON array of strings (one claim per element). No markdown, no explanation.
Maximum 6 claims.

Answer: {answer}

Example output: ["Section 354 covers assault on women", "The penalty is 2 years imprisonment"]"""

_VERIFY_PROMPT = """You are a legal fact-checker for Bangladesh. Check if the claim is supported by the context.

Claim: {claim}

Context:
{context}

Output ONLY one of these exact words on line 1: supported | unsupported | contradicted
Then one sentence of explanation on line 2."""


async def decompose_claims(answer: str) -> list[str]:
    """Extract atomic claims from the generated answer."""
    prompt = _DECOMPOSE_PROMPT.format(answer=answer[:2000])
    raw = await llm_client.generate(prompt, model=llm_client.SMALL_MODEL)
    try:
        m = re.search(r'\[.*\]', raw, re.DOTALL)
        if m:
            claims = json.loads(m.group())
            if isinstance(claims, list):
                return [str(c) for c in claims[:6]]
    except Exception:
        pass
    # Fallback: split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', answer)
    return [s.strip() for s in sentences if len(s.strip()) > 25][:5]


async def verify_claims(
    claims: list[str],
    chunks: list[RetrievedChunk],
) -> list[VerificationResult]:
    """Verify each atomic claim against the top retrieved chunks."""
    if not claims or not chunks:
        return []

    context_text = "\n\n".join(
        f"[{c.chunk_id}] {c.text[:500]}" for c in chunks[:5]
    )

    results: list[VerificationResult] = []
    for claim in claims[:5]:      # cap at 5 to control latency
        prompt = _VERIFY_PROMPT.format(claim=claim, context=context_text)
        raw = await llm_client.generate(prompt, model=llm_client.SMALL_MODEL)
        first_line = raw.strip().lower().split("\n")[0].strip()

        if first_line.startswith("supported"):
            label = "supported"
        elif first_line.startswith("contradicted"):
            label = "contradicted"
        else:
            label = "unsupported"

        lines = raw.strip().split("\n", 1)
        evidence = lines[1].strip() if len(lines) > 1 else ""
        results.append(VerificationResult(claim=claim, label=label, evidence=evidence))

    supported = sum(1 for r in results if r.label == "supported")
    unsupported = sum(1 for r in results if r.label == "unsupported")
    contradicted = sum(1 for r in results if r.label == "contradicted")
    logger.info(
        "Verification: supported=%d unsupported=%d contradicted=%d",
        supported, unsupported, contradicted,
    )
    return results


def verification_decision(results: list[VerificationResult]) -> str:
    """
    Returns: "pass" | "strip_and_pass" | "regenerate" | "exit_ramp"
    """
    if not results:
        return "pass"

    total = len(results)
    contradicted = sum(1 for r in results if r.label == "contradicted")
    unsupported = sum(1 for r in results if r.label == "unsupported")

    if contradicted > 0:
        return "regenerate"
    if unsupported == 0:
        return "pass"
    if unsupported == 1 and total >= 3:
        return "strip_and_pass"
    if unsupported >= 2:
        return "regenerate"
    return "pass"
