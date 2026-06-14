"""
Anchor AI — 7-Stage RAG Pipeline Orchestrator.

STAGE 0 → Safety Pre-Flight
STAGE 1 → Query Understanding (intent + characterizer + entities)
STAGE 2 → Contextual Hybrid Retrieval (dense + BM25 + RRF)
STAGE 3 → Corrective RAG (confidence gate + web search + rerank)
STAGE 3b→ Exit Ramp (graceful refusal + lawyer referral)
STAGE 4 → Generation (legal reasoning scaffold)
STAGE 5 → Claim-Level Verification
STAGE 6 → Output Adaptation (language + citations + disclaimer)
STAGE 7 → Audit Log (anonymised)
"""
import asyncio
import logging
import uuid
from app.pipeline.models import ChatRequest, ChatResponse, SafetyVerdict
from app.pipeline import (
    stage0_safety,
    stage1_query,
    stage2_retrieval,
    stage3_corrective,
    stage4_generation,
    stage5_verify,
    stage6_output,
)

logger = logging.getLogger(__name__)

ABSOLUTE_FLOOR = stage3_corrective.ABSOLUTE_FLOOR


async def run(request: ChatRequest) -> ChatResponse:
    """
    Execute the full Anchor AI pipeline for one user query.
    Each stage logs to stage_log for the anonymised audit trail.
    """
    query = request.query.strip()
    mode = request.mode                          # campus | national
    lang = request.lang.upper()                 # EN | BN
    lang_code = "bn" if lang == "BN" else "en"
    output_lang = "Bengali" if lang_code == "bn" else "English"
    namespace = "diu" if mode == "campus" else "national"
    conv_id = request.conversation_id or str(uuid.uuid4())
    stage_log: dict = {}

    # ── STAGE 0: SAFETY PRE-FLIGHT ────────────────────────────────────────
    verdict, safety_reason = stage0_safety.check_safety(query)
    stage_log["stage0"] = {"verdict": verdict.value, "reason": safety_reason}
    logger.debug("[S0] verdict=%s", verdict.value)

    if verdict != SafetyVerdict.safe:
        answer = stage6_output.build_safety_response(verdict.value, lang_code)
        return ChatResponse(
            answer=answer,
            citations=[],
            confidence=0.0,
            exit_ramp=(verdict == SafetyVerdict.injection),
            lawyer_referral=(verdict in (SafetyVerdict.emergency, SafetyVerdict.coercion)),
            lang=lang_code,
            conversation_id=conv_id,
        )

    # ── STAGE 1: QUERY UNDERSTANDING ─────────────────────────────────────
    analysis = await stage1_query.analyze_query(query, mode)
    stage_log["stage1"] = {
        "intent": analysis.intent.value,
        "confidence": analysis.intent_confidence,
        "complexity": analysis.complexity.value,
        "needs_retrieval": analysis.needs_retrieval,
        "lang": analysis.lang,
        "is_workflow": analysis.is_workflow_query,
    }
    logger.debug("[S1] intent=%s complexity=%s", analysis.intent.value, analysis.complexity.value)

    # Calibrated clarification — single targeted question when needed
    if analysis.clarification_needed:
        return ChatResponse(
            answer=analysis.clarification_needed,
            citations=[],
            confidence=1.0,
            exit_ramp=False,
            lawyer_referral=False,
            lang=lang_code,
            conversation_id=conv_id,
        )

    # Simple path: no retrieval needed
    if not analysis.needs_retrieval:
        from app.pipeline import llm_client
        answer_raw = await llm_client.generate(
            f"Answer concisely in {output_lang}: {query}",
            model=llm_client.MAIN_MODEL,
        )
        answer = answer_raw + (
            stage6_output.DISCLAIMER_BN if lang_code == "bn" else stage6_output.DISCLAIMER_EN
        )
        return ChatResponse(
            answer=answer,
            citations=[],
            confidence=0.9,
            exit_ramp=False,
            lawyer_referral=False,
            lang=lang_code,
            conversation_id=conv_id,
        )

    # ── STAGE 2: CONTEXTUAL RETRIEVAL ────────────────────────────────────
    query_en, query_bn = await stage1_query.rewrite_query(query, analysis.lang, analysis.entities)
    stage_log["stage2"] = {"query_en": query_en[:80], "query_bn": query_bn[:80]}

    n_candidates = 10 if analysis.complexity.value == "medium" else 20
    initial_chunks = await stage2_retrieval.retrieve(
        query=query,
        query_en=query_en,
        query_bn=query_bn,
        analysis=analysis,
        n_candidates=n_candidates,
        namespace=namespace,
    )
    stage_log["stage2"]["initial_hits"] = len(initial_chunks)
    logger.debug("[S2] retrieved=%d chunks", len(initial_chunks))

    # ── STAGE 3: CORRECTIVE RAG ───────────────────────────────────────────
    final_chunks, confidence, web_fired = await stage3_corrective.corrective_rag(
        query=query,
        query_en=query_en,
        query_bn=query_bn,
        initial_chunks=initial_chunks,
        analysis=analysis,
        namespace=namespace,
    )
    stage_log["stage3"] = {
        "confidence": round(confidence, 3),
        "web_search_fired": web_fired,
        "final_chunks": len(final_chunks),
    }
    logger.debug("[S3] confidence=%.3f web=%s chunks=%d", confidence, web_fired, len(final_chunks))

    # ── STAGE 3b: EXIT RAMP (confidence too low) ──────────────────────────
    if confidence < ABSOLUTE_FLOOR or not final_chunks:
        answer = stage6_output.build_exit_ramp(lang_code)
        stage_log["stage3b"] = {"exit_ramp": True, "reason": "below_floor"}
        _audit(query, stage_log, exit_ramp=True)
        return ChatResponse(
            answer=answer,
            citations=[],
            confidence=confidence,
            exit_ramp=True,
            lawyer_referral=True,
            lang=lang_code,
            conversation_id=conv_id,
        )

    # ── STAGE 4: GENERATION ───────────────────────────────────────────────
    answer, citations = await stage4_generation.generate_response(
        query=query,
        chunks=final_chunks,
        analysis=analysis,
        mode=mode,
        output_lang=output_lang,
    )
    stage_log["stage4"] = {"citations": len(citations)}
    logger.debug("[S4] generated answer (%d chars, %d cites)", len(answer), len(citations))

    # ── STAGE 5: CLAIM-LEVEL VERIFICATION ────────────────────────────────
    claims = await stage5_verify.decompose_claims(answer)
    verification = await stage5_verify.verify_claims(claims, final_chunks)
    decision = stage5_verify.verification_decision(verification)
    stage_log["stage5"] = {
        "claims": len(claims),
        "decision": decision,
        "labels": [v.label for v in verification],
    }
    logger.debug("[S5] claims=%d decision=%s", len(claims), decision)

    if decision == "regenerate":
        answer, citations = await stage4_generation.generate_strict(
            query=query, chunks=final_chunks, output_lang=output_lang
        )
        claims2 = await stage5_verify.decompose_claims(answer)
        verification2 = await stage5_verify.verify_claims(claims2, final_chunks)
        decision2 = stage5_verify.verification_decision(verification2)
        stage_log["stage5"]["retry_decision"] = decision2

        if decision2 in ("regenerate", "exit_ramp"):
            answer = stage6_output.build_exit_ramp(lang_code)
            _audit(query, stage_log, exit_ramp=True)
            return ChatResponse(
                answer=answer,
                citations=[],
                confidence=confidence * 0.5,
                exit_ramp=True,
                lawyer_referral=True,
                lang=lang_code,
                conversation_id=conv_id,
            )

    # ── STAGE 6: OUTPUT ADAPTATION ────────────────────────────────────────
    final_answer = stage6_output.adapt_output(
        answer=answer,
        citations=citations,
        lang=lang_code,
        web_search_fired=web_fired,
    )

    # Offer lawyer referral if confidence is marginal
    lawyer_referral = confidence < 0.60

    _audit(query, stage_log, exit_ramp=False)
    return ChatResponse(
        answer=final_answer,
        citations=citations,
        confidence=round(confidence, 3),
        exit_ramp=False,
        lawyer_referral=lawyer_referral,
        lang=lang_code,
        conversation_id=conv_id,
    )


def _audit(query: str, stage_log: dict, exit_ramp: bool):
    """
    Stage 7 — anonymised audit log.
    Logs pipeline decisions and chunk ids — never raw query text in production.
    """
    logger.info(
        "[AUDIT] exit_ramp=%s stage0=%s stage1=%s confidence=%s web=%s",
        exit_ramp,
        stage_log.get("stage0", {}).get("verdict"),
        stage_log.get("stage1", {}).get("intent"),
        stage_log.get("stage3", {}).get("confidence"),
        stage_log.get("stage3", {}).get("web_search_fired"),
    )
