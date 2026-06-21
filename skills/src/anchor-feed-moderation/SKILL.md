---
name: anchor-feed-moderation
description: >
  Use this skill when moderating Anchor's community Verification Feed — pre-screening a new
  post before publish, reviewing a flagged/queued post, or explaining a moderation verdict.
  Triggers: "moderate this post", "should this be published", "pre-screen", "is this safe",
  "verification feed", "feed report", "why was my post blocked", "flagged post". Defines the
  feed's categories, the immediate-block safety patterns, the spam heuristics, and the
  block/manual-review/pass decision. It is the CANONICAL source that the backend gate
  services/api/app/services/feed_prescreen.py mirrors — when the patterns or categories
  change in one, update the other (references/grounding.md tracks the rules).
---

# Anchor Verification Feed Moderation

The Verification Feed is a community board where people post local incidents, missing
persons, road conditions, safety hazards, and civic events for others to verify and act on.
Because posts can trigger real-world response, moderation balances **speed** (don't slow the
report of a real emergency) against **safety** (block harmful content and obvious abuse).

The backend pre-screen (`feed_prescreen.py`) is intentionally a fast, deterministic gate
(regex + keyword + spam heuristics, with a timeout) — not an LLM call — so it never adds
latency to a genuine report. This skill is the human-readable specification of that gate and
the playbook for human moderators reviewing the queue.

---

## Decision verdicts

Every post resolves to one of three verdicts:

- **block** — content-policy violation; never publish. (Safety patterns below.)
- **manual_review** — queued for a human; not auto-published. (Spam/quality/category signals.)
- **pass** — clears the gate and publishes.

Order of checks: safety block → spam/quality → category fit. The first hit wins.

See `references/block-patterns.md` for the exact immediate-block patterns and
`references/categories.md` for the category definitions and keyword hints.

---

## Human review playbook (for the queue)

When reviewing a `manual_review` post, weigh:

1. **Is it real and actionable?** A specific place, time, and concrete detail raise trust.
2. **Is it harmful or abusive?** Doxxing, targeted harassment, defamation, incitement →
   reject. Hate slurs and self-harm/CSAM content → reject (these should already be blocked).
3. **Is it the right category?** A mismatch (e.g. an "event" with no civic content) → ask
   the poster to recategorise or downrank, don't necessarily reject.
4. **Is it spam?** Too short, link-stuffed, all-caps shouting, or repetitive → reject/hold.
5. **PII of others.** Phone numbers, NID, home addresses of third parties → redact or reject.

Lean toward letting genuine safety reports through quickly; lean toward holding anything that
targets a private individual.

---

## Trust signals

Trust is earned: a poster's history (confirmed-true vs false-alarm posts) feeds the
false-alarm strike system and trust-tier promotions (`feed_moderation_svc.py`). Weight a
report from a high-trust poster higher, but never let trust override a hard safety block.
