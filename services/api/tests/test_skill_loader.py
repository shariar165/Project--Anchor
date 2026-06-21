"""
Tests for the skill grounding loader and a sync-guard that prevents the historical drift
between backend prompts and their canonical skill bundles.
"""
from pathlib import Path

import pytest

from app.services import skill_loader


@pytest.fixture(autouse=True)
def _clear_skill_cache():
    skill_loader.clear_cache()
    yield
    skill_loader.clear_cache()


def test_grounding_reads_grounding_md():
    """A skill with references/grounding.md returns that compact block."""
    text = skill_loader.grounding("bd-legal-answer")
    assert "Anchor AI" in text
    assert "DISCLAIMER" in text  # the grounding block carries the disclaimer guidance
    # frontmatter must not leak through
    assert not text.lstrip().startswith("---")


def test_grounding_falls_back_to_skill_md_body():
    """A skill without grounding.md falls back to SKILL.md with frontmatter stripped."""
    base = skill_loader._skills_dir() / "uni-admin-application"
    assert (base / "SKILL.md").is_file()
    assert not (base / "references" / "grounding.md").exists()

    text = skill_loader.grounding("uni-admin-application")
    assert text  # non-empty
    assert not text.lstrip().startswith("---")  # YAML frontmatter stripped
    assert "name: uni-admin-application" not in text


def test_grounding_returns_fallback_when_skill_missing():
    """An unknown skill degrades gracefully to the caller's fallback string."""
    assert skill_loader.grounding("no-such-skill-xyz", fallback="FALLBACK") == "FALLBACK"
    assert skill_loader.grounding("no-such-skill-xyz") == ""


def test_grounding_is_cached(monkeypatch):
    """Repeated reads are served from cache (no second filesystem hit)."""
    calls = {"n": 0}
    real_read = Path.read_text

    def counting_read(self, *a, **k):
        if self.name == "grounding.md":
            calls["n"] += 1
        return real_read(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", counting_read)
    skill_loader.clear_cache()
    a = skill_loader.grounding("bd-legal-answer")
    b = skill_loader.grounding("bd-legal-answer")
    assert a == b
    assert calls["n"] == 1  # second call hit the lru_cache, not the disk


# ── Sync guard ──────────────────────────────────────────────────────────────
# Each backend AI surface grounds its prompt from a skill; assert the canonical source
# exists with a compact grounding.md so a service can never reference a missing skill.
_GROUNDED_SURFACES = {
    "diu-notice-generator": "services/api/app/services/notice_ai_svc.py",
    "bd-legal-answer": "services/rag/app/pipeline/stage4_generation.py",
    "timetable-nl-edit": "services/api/app/services/timetable_solver.py",
    "anchor-feed-moderation": "services/api/app/services/feed_prescreen.py",
}


@pytest.mark.parametrize("skill_name,consumer", sorted(_GROUNDED_SURFACES.items()))
def test_grounded_surface_has_grounding_md(skill_name, consumer):
    base = skill_loader._skills_dir() / skill_name
    assert (base / "SKILL.md").is_file(), f"{skill_name}: missing SKILL.md (used by {consumer})"
    grounding_md = base / "references" / "grounding.md"
    assert grounding_md.is_file(), f"{skill_name}: missing references/grounding.md (used by {consumer})"
    assert grounding_md.read_text(encoding="utf-8").strip(), f"{skill_name}: grounding.md is empty"


def test_every_source_skill_has_skill_md():
    """Every skill under skills/src/ is a valid bundle (has a SKILL.md)."""
    src = skill_loader._skills_dir()
    assert src.is_dir(), f"skill source tree not found at {src}"
    for d in src.iterdir():
        if d.is_dir():
            assert (d / "SKILL.md").is_file(), f"{d.name}: missing SKILL.md"
