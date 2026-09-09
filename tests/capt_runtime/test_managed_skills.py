from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from capt_runtime.managed_skills import (
    ManagedSkillPackViolation,
    import_managed_skill_pack,
    verify_managed_skill_pack,
)


def _skill(name: str, description: str, body: str = "# Skill\n") -> str:
    return f"---\nname: {name}\ndescription: {description}\nversion: 1.0.0\n---\n\n{body}"


def test_imports_directory_flat_markdown_and_skill_bundle(tmp_path: Path):
    source = tmp_path / "source"; source.mkdir()
    d = source / "alpha"; d.mkdir()
    (d / "SKILL.md").write_text(_skill("alpha", "Use for alpha work."))
    (d / "references").mkdir(); (d / "references" / "notes.md").write_text("support")
    (source / "flat.md").write_text(_skill("flat-skill", "Use for flat work."))
    bundle = source / "bundle.skill"
    with zipfile.ZipFile(bundle, "w") as z:
        z.writestr("bundled/SKILL.md", _skill("bundled", "Use for bundled work."))
        z.writestr("bundled/scripts/run.py", "print('ok')\n")
    dest = tmp_path / "state" / "skills" / "ultimate"
    result = import_managed_skill_pack(source, dest, pack_name="ultimate")
    assert [s["name"] for s in result["skills"]] == ["alpha", "bundled", "flat-skill"]
    assert (dest / "skills" / "alpha" / "references" / "notes.md").read_text() == "support"
    assert (dest / "skills" / "bundled" / "scripts" / "run.py").exists()
    verified = verify_managed_skill_pack(dest)
    assert verified["manifestDigest"].startswith("sha256:")
    assert verified["skillCount"] == 3


def test_identical_duplicate_collapses_and_records_origins(tmp_path: Path):
    source = tmp_path / "source"; source.mkdir()
    for parent in (source / "one", source / "two"):
        parent.mkdir(); (parent / "SKILL.md").write_text(_skill("same", "Use for same work."))
    dest = tmp_path / "pack"
    result = import_managed_skill_pack(source, dest, pack_name="ultimate")
    assert len(result["skills"]) == 1
    assert result["skills"][0]["name"] == "same"
    assert len(result["skills"][0]["sourceOrigins"]) == 2


def test_conflicting_duplicate_name_fails_closed(tmp_path: Path):
    source = tmp_path / "source"; source.mkdir()
    for idx, desc in enumerate(("first", "second")):
        parent = source / str(idx); parent.mkdir()
        (parent / "SKILL.md").write_text(_skill("same", desc))
    with pytest.raises(ManagedSkillPackViolation, match="conflicting duplicate skill"):
        import_managed_skill_pack(source, tmp_path / "pack", pack_name="ultimate")


def test_skill_zip_path_traversal_is_rejected(tmp_path: Path):
    source = tmp_path / "source"; source.mkdir()
    with zipfile.ZipFile(source / "evil.skill", "w") as z:
        z.writestr("../escape/SKILL.md", _skill("evil", "bad"))
    with pytest.raises(ManagedSkillPackViolation, match="unsafe archive path"):
        import_managed_skill_pack(source, tmp_path / "pack", pack_name="ultimate")


def test_verification_detects_post_import_tampering(tmp_path: Path):
    source = tmp_path / "source"; source.mkdir()
    d = source / "alpha"; d.mkdir(); (d / "SKILL.md").write_text(_skill("alpha", "Use for alpha."))
    dest = tmp_path / "pack"; import_managed_skill_pack(source, dest, pack_name="ultimate")
    (dest / "skills" / "alpha" / "SKILL.md").write_text(_skill("alpha", "tampered"))
    with pytest.raises(ManagedSkillPackViolation, match="digest mismatch"):
        verify_managed_skill_pack(dest)


def test_oversized_skill_installs_but_is_marked_not_inlineable(tmp_path: Path):
    source = tmp_path / "source"; source.mkdir()
    d = source / "big"; d.mkdir()
    (d / "SKILL.md").write_text(_skill("big-skill", "Use for huge work.", "x" * 40000))
    result = import_managed_skill_pack(source, tmp_path / "pack", pack_name="ultimate")
    item = result["skills"][0]
    assert item["inlineable"] is False
    assert item["contentBytes"] > 32768


def test_install_merges_new_skills_without_dropping_verified_existing_pack(tmp_path: Path):
    from capt_runtime.managed_skills import install_managed_skill_source

    initial = tmp_path / "initial"; initial.mkdir()
    a = initial / "alpha"; a.mkdir()
    (a / "SKILL.md").write_text(_skill("alpha", "Use for alpha work."))
    dest = tmp_path / "state" / "skills" / "ultimate"
    import_managed_skill_pack(initial, dest, pack_name="ultimate")

    incoming = tmp_path / "incoming"; incoming.mkdir()
    b = incoming / "beta"; b.mkdir()
    (b / "SKILL.md").write_text(_skill("beta", "Use for beta work."))
    result = install_managed_skill_source(incoming, dest, pack_name="ultimate")

    assert [item["name"] for item in result["skills"]] == ["alpha", "beta"]
    assert (dest / "skills" / "alpha" / "SKILL.md").exists()
    assert (dest / "skills" / "beta" / "SKILL.md").exists()


def test_install_conflict_fails_atomically_and_preserves_prior_pack(tmp_path: Path):
    from capt_runtime.managed_skills import install_managed_skill_source

    initial = tmp_path / "initial"; initial.mkdir()
    a = initial / "alpha"; a.mkdir()
    original = _skill("alpha", "Original alpha description.")
    (a / "SKILL.md").write_text(original)
    dest = tmp_path / "state" / "skills" / "ultimate"
    before = import_managed_skill_pack(initial, dest, pack_name="ultimate")

    incoming = tmp_path / "incoming"; incoming.mkdir()
    other = incoming / "alpha"; other.mkdir()
    (other / "SKILL.md").write_text(_skill("alpha", "Conflicting alpha description."))
    with pytest.raises(ManagedSkillPackViolation, match="conflicting duplicate skill"):
        install_managed_skill_source(incoming, dest, pack_name="ultimate")

    after = verify_managed_skill_pack(dest)
    assert after["manifestDigest"] == before["manifestDigest"]
    assert (dest / "skills" / "alpha" / "SKILL.md").read_text() == original


def test_create_managed_skill_builds_real_verified_skill_and_preserves_existing(tmp_path: Path):
    from capt_runtime.managed_skills import create_managed_skill

    initial = tmp_path / "initial"; initial.mkdir()
    a = initial / "alpha"; a.mkdir()
    (a / "SKILL.md").write_text(_skill("alpha", "Use for alpha work."))
    dest = tmp_path / "state" / "skills" / "ultimate"
    import_managed_skill_pack(initial, dest, pack_name="ultimate")

    result = create_managed_skill(
        dest,
        name="capt-ui-review",
        description="Use when reviewing CAPT native macOS interface changes.",
        version="1.2.0",
        body="## When to Use\n\nReview native macOS UI changes with evidence.\n",
    )
    assert [item["name"] for item in result["skills"]] == ["alpha", "capt-ui-review"]
    created = (dest / "skills" / "capt-ui-review" / "SKILL.md").read_text()
    assert "name: capt-ui-review" in created
    assert "version: 1.2.0" in created
    assert "Review native macOS UI changes with evidence." in created
    verified = verify_managed_skill_pack(dest)
    assert verified["skillCount"] == 2
    assert "created://local/capt-ui-review" in verified["sourceRoots"]
    created_meta = next(item for item in verified["skills"] if item["name"] == "capt-ui-review")
    assert any(origin.startswith("created://local/capt-ui-review:") for origin in created_meta["sourceOrigins"])


def test_create_first_managed_skill_records_durable_created_origin(tmp_path: Path):
    from capt_runtime.managed_skills import create_managed_skill

    dest = tmp_path / "state" / "skills" / "ultimate"
    result = create_managed_skill(
        dest,
        name="first-skill",
        description="Use when proving first-skill provenance.",
        version="1.0.0",
        body="# First Skill\n\nDo the bounded thing.\n",
    )
    assert result["sourceRoots"] == ["created://local/first-skill"]
    assert result["skills"][0]["sourceOrigins"] == [
        "created://local/first-skill:first-skill/SKILL.md"
    ]
