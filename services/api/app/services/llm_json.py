"""Extract structured JSON from LLM responses (Gemini / local Ollama)."""
import json
import re


def extract_json_object(raw: str) -> dict | None:
    """Pull the first parseable JSON object out of an LLM response.

    Reasoning models (qwen3) wrap output in <think>…</think> blocks that can
    themselves contain braces, so those are stripped first. The remainder is
    scanned for brace-balanced candidates and the first one that parses as a
    JSON object wins — prose or stray braces around the object don't break it.
    """
    if not raw:
        return None
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    depth = 0
    start = None
    for i, ch in enumerate(cleaned):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj = json.loads(cleaned[start:i + 1])
                    if isinstance(obj, dict):
                        return obj
                except Exception:
                    pass
                start = None
    return None
