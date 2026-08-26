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
