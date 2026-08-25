from __future__ import annotations

from pathlib import Path

import pytest

from capt_runtime.managed_skills import (
    ManagedSkillPackViolation,
    import_managed_skill_pack,
    prepare_managed_skill_context,
    select_managed_skills,
    verify_managed_skill_pack,
)


def _write(root: Path, name: str, description: str, extra: str = "") -> None:
    p = root / name; p.mkdir(parents=True)
    p.joinpath("SKILL.md").write_text(
        f"---\nname: {name}\ndescription: >\n  {description}\nversion: 1.0.0\n---\n\n# {name}\n{extra}\n"
    )


def _pack(tmp_path: Path) -> Path:
    source = tmp_path / "source"; source.mkdir()
    _write(source, "inversion-execute-now", "Use when the user says proceed, continue, apply it, fix it, do it, approved, or ship it.")
    _write(source, "inversion-release-closure", "Use when work is done, ready, mergeable, shippable, or release-candidate.")
    _write(source, "inversion-interface-craft", "Use for Inversion Labs interface work combining design systems across marketing and product surfaces.")
    _write(source, "backend-only", "Use for backend database migrations. Not for frontend interface or visual design work.")
    dest = tmp_path / "pack"; import_managed_skill_pack(source, dest, pack_name="ultimate")
    return dest


def test_contextual_selection_composes_relevant_skills_stably(tmp_path: Path):
    pack = verify_managed_skill_pack(_pack(tmp_path))
    selected = select_managed_skills("Proceed and ship the release candidate once it is mergeable", pack, limit=4)
    assert selected[:2] == ["inversion-execute-now", "inversion-release-closure"]


def test_interface_prompt_prefers_interface_skill_and_penalizes_negative_applicability(tmp_path: Path):
    pack = verify_managed_skill_pack(_pack(tmp_path))
    selected = select_managed_skills("Design an Inversion Labs frontend interface and visual system", pack, limit=4)
    assert selected[0] == "inversion-interface-craft"
    assert "backend-only" not in selected


def test_no_match_returns_empty_selection(tmp_path: Path):
    pack = verify_managed_skill_pack(_pack(tmp_path))
    assert select_managed_skills("calculate sodium chloride molar mass", pack) == []


def test_explicit_names_override_contextual_ranking(tmp_path: Path):
    root = _pack(tmp_path)
    context, names = prepare_managed_skill_context(
        root, "Design a frontend", explicit_names=["inversion-release-closure"]
    )
    assert names == ["inversion-release-closure"]
    assert [s["name"] for s in context["skills"]] == names
    assert context["trust"] == "managed_local"


def test_explicit_oversized_skill_fails_instead_of_truncating(tmp_path: Path):
    source = tmp_path / "source"; source.mkdir()
    _write(source, "huge", "Use for huge work", "x" * 40000)
    root = tmp_path / "pack"; import_managed_skill_pack(source, root, pack_name="ultimate")
    with pytest.raises(ManagedSkillPackViolation, match="too large for inline authored-skill context"):
        prepare_managed_skill_context(root, "huge work", explicit_names=["huge"])
