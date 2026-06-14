"""Quick smoke tests for the AI engine (run from backend/)."""
import asyncio
import sys

async def test_corpus_and_bm25():
    from app.ai.sample_corpus import load_sample_corpus
    from app.ai.bm25_index import query_bm25, index_count

    count = await load_sample_corpus(generate_prefixes=False)
    assert count > 0, "No chunks loaded"
    print(f"Corpus loaded: {count} chunks total")

    nat = index_count("national")
    diu = index_count("diu")
    print(f"BM25 national={nat}  diu={diu}")
    assert nat > 0 and diu > 0, "BM25 index empty"

    results = query_bm25("phone theft robbery file GD", n_results=3, namespace="national")
    print(f"BM25 query: {len(results)} results")
    for r in results:
        print(f"  [{r.chunk_id}] {r.metadata.act_name} score={r.score:.3f}")
    assert len(results) > 0, "BM25 returned nothing"
    return True


async def test_stage1_rule_based():
    from app.ai.stage1_query import _rule_based_analyze, _detect_lang
    from app.ai.models import Intent, Complexity

    a = _rule_based_analyze("how do I file a GD for phone theft", "national")
    assert a.intent == Intent.complaint_draft, f"Expected complaint_draft, got {a.intent}"
    assert a.is_workflow_query, "Expected is_workflow=True"
    print(f"Stage1 rule-based: intent={a.intent.value} complexity={a.complexity.value}")

    lang = _detect_lang("My phone was stolen at Mirpur-10")
    assert lang == "en", f"Expected en, got {lang}"
    print(f"Lang detect: '{lang}'")
    return True


async def test_pipeline_stub():
    """Full pipeline run with Ollama stub (no GPU needed)."""
    from app.ai.pipeline import run
    from app.ai.models import ChatRequest

    req = ChatRequest(
        query="My phone was snatched at Mirpur-10. How do I file a GD?",
        mode="national",
        lang="EN",
    )
    result = await run(req)
    print(f"Pipeline result: confidence={result.confidence} exit_ramp={result.exit_ramp}")
    print(f"Answer preview: {result.answer[:120]}...")
    assert result.answer, "Empty answer"
    assert not result.exit_ramp, f"Unexpected exit ramp: {result.answer[:100]}"
    return True


async def main():
    results = {}
    for name, coro in [
        ("corpus+bm25", test_corpus_and_bm25()),
        ("stage1_rules", test_stage1_rule_based()),
        ("pipeline_stub", test_pipeline_stub()),
    ]:
        try:
            ok = await coro
            results[name] = "PASS" if ok else "FAIL"
        except Exception as e:
            results[name] = f"ERROR: {e}"
        print()

    print("=" * 50)
    for k, v in results.items():
        print(f"  {v:35s} {k}")
    if any("ERROR" in v or "FAIL" in v for v in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
