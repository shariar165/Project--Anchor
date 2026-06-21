"""
Skill grounding loader — single source of truth for AI prompt grounding.

Anchor's AI surfaces run on a small local model (qwen3 via Ollama), so the dominant
quality lever is *prompt grounding*: injecting compact, domain-specific knowledge into
the prompt. That knowledge lives in versioned skill bundles under `skills/src/<name>/`
(see `skills/pack-skills.ps1`), and this loader reads it at runtime so the skill is the
single source of truth instead of being hand-copied into each service (which drifts).

Resolution order for `grounding(name, fallback)`:
  1. {skills_dir}/{name}/references/grounding.md  — terse, model-sized distillation
  2. {skills_dir}/{name}/SKILL.md                 — full skill, YAML frontmatter stripped
  3. the caller's `fallback` string              — used in prod when the tree isn't shipped

The result is cached (`@lru_cache`), mirroring the `get_settings()` pattern, so reads are
zero-cost after the first. A missing tree never raises — it degrades to `fallback`. This
matters in container deploys, where the build context may not include the repo-root
`skills/` tree.

(Verbatim twin of services/api/app/services/skill_loader.py — the two services deploy
independently and cannot import each other.)
"""
import logging
import re
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)


def _default_skills_dir() -> Path | None:
    """Locate the repo's skills/src by walking up from this file. Returns None when it
    isn't found (e.g. a container that doesn't ship the tree) so callers fall back.
    Never raises — must not index parents blindly (depth varies by deploy layout)."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "skills" / "src"
        if candidate.is_dir():
            return candidate
    return None


def _skills_dir() -> Path | None:
    try:
        from app.config import get_settings
        configured = (getattr(get_settings(), "skills_dir", "") or "").strip()
    except Exception:
        configured = ""
    if configured:
        return Path(configured)
    return _default_skills_dir()


@lru_cache(maxsize=64)
def grounding(skill_name: str, fallback: str = "") -> str:
    """Return compact backend grounding text for a skill, or `fallback` if unavailable."""
    base_dir = _skills_dir()
    if base_dir is None:
        return fallback
    base = base_dir / skill_name
    try:
        grounding_md = base / "references" / "grounding.md"
        if grounding_md.is_file():
            return grounding_md.read_text(encoding="utf-8").strip()
        skill_md = base / "SKILL.md"
        if skill_md.is_file():
            body = _FRONTMATTER_RE.sub("", skill_md.read_text(encoding="utf-8"), count=1)
            return body.strip()
        logger.info("skill_loader: no source for '%s' — using fallback", skill_name)
    except Exception as exc:
        logger.warning("skill_loader: failed reading '%s' (%s) — using fallback", skill_name, exc)
    return fallback


def clear_cache() -> None:
    """Drop the in-memory cache (used by tests and after editing skill sources)."""
    grounding.cache_clear()
