# Immediate-block & spam patterns

These mirror `_BLOCK_PATTERNS` and the spam heuristics in `feed_prescreen.py`. They are the
hard, deterministic part of the gate — applied before any quality or category judgement.

## Immediate block (verdict: block, reason: content_policy_violation)
A post is blocked outright — never published, not queued — if it matches any of:

| Class | Matches (case-insensitive) |
|---|---|
| Self-harm promotion | "kill yourself", "kys", "suicide method", "how to die" |
| CSAM | "child porn", "cp link", "csam" |
| Prompt injection | "ignore previous instructions", "disregard all prior" |
| Hate slurs | racial / ethnic / sexual slurs |

These are deliberately narrow (high-precision) so legitimate reports are never blocked by
accident — e.g. a post *reporting* a crime is not the same as a post *promoting* harm.
Broader judgement (defamation, targeted harassment, doxxing) is left to human review, where
context can be weighed.

## Spam / quality (verdict: manual_review)
Held for a human, not published automatically:

- **too_short** — body under ~10 words.
- **excessive_urls** — more than 5 links in the body.
- **all_caps** — more than 5 words and the body is entirely uppercase.
- **timeout** — the gate exceeded its time budget (fail safe to review, never auto-publish).

## Why a fast deterministic gate
The pre-screen runs on the post-submit hot path with a timeout. An LLM call here would add
latency to genuine emergency reports and could itself be prompt-injected. The deterministic
gate handles the unambiguous cases instantly; everything nuanced goes to `manual_review` for
a human moderator using the playbook in `SKILL.md`.
