"""Contract tests for pinned external authored skill packs."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from capt_runtime.authored_skills import (
    AuthoredSkillPackViolation,
    build_skill_context,
    verify_skill_pack,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True
    ).strip()


def _make_pack(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "CAPT_Skills"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "CAPT Tests")
    _git(root, "remote", "add", "origin",
         "https://github.com/knowurknottty/CAPT_Skills.git")
    skills = {
        "inversion-interface-craft": "interface-owner",
        "inversion-motion-craft": "motion-owner",
    }
    locked = []
    for name, role in skills.items():
        path = root / "skills" / name / "SKILL.md"
        path.parent.mkdir(parents=True)
        content = (
            "---\n"
            f"name: {name}\n"
            "version: 0.1.0\n"
            "metadata:\n"
            "  author: Inversion Labs\n"
            f"  role: {role}\n"
            "---\n\n"
            f"# {name}\n\nPinned guidance for {name}.\n"
        )
        path.write_text(content)
        locked.append({
            "name": name,
            "version": "0.1.0",
            "path": f"skills/{name}/SKILL.md",
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
        })
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture pack")
    lock = {
        "schemaVersion": "1.0.0",
        "packName": "CAPT_Skills",
        "packVersion": "0.1.0",
        "repository": "https://github.com/knowurknottty/CAPT_Skills.git",
        "ref": "v0.1.0",
        "commit": _git(root, "rev-parse", "HEAD"),
        "tree": _git(root, "rev-parse", "HEAD^{tree}"),
        "skills": locked,
    }
    return root, lock


def test_verify_skill_pack_accepts_exact_clean_pinned_checkout(tmp_path):
    root, lock = _make_pack(tmp_path)
    verified = verify_skill_pack(root, lock)
    assert verified["packName"] == "CAPT_Skills"
    assert verified["commit"] == lock["commit"]
    assert [s["name"] for s in verified["skills"]] == [
        "inversion-interface-craft", "inversion-motion-craft"
    ]
    assert all(s["contentDigest"].startswith("sha256:")
               for s in verified["skills"])


def test_verify_skill_pack_fails_closed_on_dirty_or_tampered_checkout(tmp_path):
    root, lock = _make_pack(tmp_path)
    target = root / lock["skills"][0]["path"]
    target.write_text(target.read_text() + "\nTAMPERED\n")
    with pytest.raises(AuthoredSkillPackViolation, match="dirty|tamper|digest"):
        verify_skill_pack(root, lock)


def test_verify_skill_pack_fails_closed_on_wrong_origin(tmp_path):
    root, lock = _make_pack(tmp_path)
    _git(root, "remote", "set-url", "origin", "https://example.com/not-capt-skills.git")
    with pytest.raises(AuthoredSkillPackViolation, match="repository|origin"):
        verify_skill_pack(root, lock)


def test_build_skill_context_is_explicitly_selected_and_provenance_bearing(tmp_path):
    root, lock = _make_pack(tmp_path)
    context = build_skill_context(
        root, lock, selected_names=["inversion-motion-craft"]
    )
    assert context["packName"] == "CAPT_Skills"
    assert context["sourceCommit"] == lock["commit"]
    assert context["trust"] == "pinned_external"
    assert len(context["skills"]) == 1
    skill = context["skills"][0]
    assert skill["name"] == "inversion-motion-craft"
    assert skill["version"] == "0.1.0"
    assert "Pinned guidance for inversion-motion-craft" in skill["content"]
    assert skill["contentDigest"].startswith("sha256:")


def test_build_skill_context_rejects_unknown_selection(tmp_path):
    root, lock = _make_pack(tmp_path)
    with pytest.raises(AuthoredSkillPackViolation, match="unknown skill"):
        build_skill_context(root, lock, selected_names=["does-not-exist"])


def test_symlinked_skill_file_is_rejected_even_when_path_resolves_inside_pack(tmp_path):
    root, lock = _make_pack(tmp_path)
    target = root / lock["skills"][0]["path"]
    real = target.with_name("REAL.md")
    target.rename(real)
    target.symlink_to(real.name)
    # Update Git/tree pins so this test isolates the symlink policy itself.
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "symlink fixture")
    lock["commit"] = _git(root, "rev-parse", "HEAD")
    lock["tree"] = _git(root, "rev-parse", "HEAD^{tree}")
    lock["skills"][0]["sha256"] = hashlib.sha256(real.read_bytes()).hexdigest()
    with pytest.raises(AuthoredSkillPackViolation, match="symlink"):
        verify_skill_pack(root, lock)


def test_parse_authored_skill_request_requires_root_and_explicit_unique_names():
    from capt_runtime.authored_skills import parse_authored_skill_request

    assert parse_authored_skill_request({}) == (None, [])
    root, names = parse_authored_skill_request({
        "skillPackRoot": "/tmp/CAPT_Skills",
        "skillNames": ["inversion-interface-craft", "inversion-motion-craft"],
    })
    assert root == "/tmp/CAPT_Skills"
    assert names == ["inversion-interface-craft", "inversion-motion-craft"]

    for payload in (
        {"skillNames": ["inversion-interface-craft"]},
        {"skillPackRoot": "/tmp/CAPT_Skills"},
        {"skillPackRoot": "/tmp/CAPT_Skills", "skillNames": []},
        {"skillPackRoot": "/tmp/CAPT_Skills", "skillNames": ["x", "x"]},
        {"skillPackRoot": "/tmp/CAPT_Skills", "skillNames": "x"},
    ):
        with pytest.raises(AuthoredSkillPackViolation):
            parse_authored_skill_request(payload)


def test_summarize_skill_context_excludes_instruction_body():
    from capt_runtime.authored_skills import summarize_skill_context

    root = {
        "packName": "CAPT_Skills", "packVersion": "0.1.0",
        "sourceCommit": "0" * 40, "manifestDigest": "sha256:" + "1" * 64,
        "skills": [{"name": "x", "version": "1", "contentDigest": "sha256:" + "2" * 64,
                    "content": "SECRET INSTRUCTION BODY"}],
    }
    summary = summarize_skill_context(root)
    assert summary["skills"] == [{"name": "x", "version": "1",
                                  "contentDigest": "sha256:" + "2" * 64}]
    assert "SECRET INSTRUCTION BODY" not in str(summary)


def test_authored_skill_errors_use_runtime_taxonomy():
    from capt_runtime.authored_skills import AuthoredSkillRequestViolation
    from capt_runtime.errors import CaptRuntimeError

    assert issubclass(AuthoredSkillPackViolation, CaptRuntimeError)
    assert AuthoredSkillPackViolation.category == "integrity"
    assert issubclass(AuthoredSkillRequestViolation, AuthoredSkillPackViolation)
    assert AuthoredSkillRequestViolation.category == "validation"


def _approval_meta(label: str):
    from capt_runtime import commands

    return commands.command(
        command_id="cmd-" + label, idempotency_key="idem-" + label,
        operation_fingerprint=commands.fingerprint("approval", {"label": label}),
        correlation_id="corr-" + label, actor_id="operator-test", actor_kind="human",
        issued_at="2026-08-19T10:00:00Z", replay_policy="never",
    )


def test_prompt_approval_binds_verified_authored_skill_provenance(tmp_path, monkeypatch):
    import capt_runtime.authored_skills as authored
    from capt_runtime.prompt_approval import request_model_prompt_approval
    from capt_runtime.services import RuntimeService
    from capt_runtime.store import EventStore

    root, lock = _make_pack(tmp_path)
    monkeypatch.setattr(authored, "load_capt_skills_lock", lambda _path=None: lock)
    store = EventStore(str(tmp_path / "approval-skill.db"))
    try:
        result = request_model_prompt_approval(
            RuntimeService(store),
            {"objective": "Review UI", "targetRoot": "/tmp/project",
             "provider": "local-openai", "model": "qwen",
             "skillPackRoot": str(root), "skillNames": ["inversion-interface-craft"]},
            _approval_meta("skill"),
        )
        state = store.require_state("human_approval-" + result["requestId"])
        summary = state["scope"]["approvalBinding"]["authoredSkills"]
        assert summary["sourceCommit"] == lock["commit"]
        assert summary["skills"][0]["name"] == "inversion-interface-craft"
        assert "content" not in summary["skills"][0]
        assert result["authoredSkills"] == summary
    finally:
        store.close()


def test_prompt_approval_skill_tamper_fails_before_authority_mutation(tmp_path, monkeypatch):
    import capt_runtime.authored_skills as authored
    from capt_runtime.prompt_approval import request_model_prompt_approval
    from capt_runtime.services import RuntimeService
    from capt_runtime.store import EventStore

    root, lock = _make_pack(tmp_path)
    monkeypatch.setattr(authored, "load_capt_skills_lock", lambda _path=None: lock)
    skill_file = root / lock["skills"][0]["path"]
    skill_file.write_text(skill_file.read_text() + "\nTAMPER_BEFORE_APPROVAL\n")
    store = EventStore(str(tmp_path / "approval-tamper.db"))
    try:
        with pytest.raises(AuthoredSkillPackViolation):
            request_model_prompt_approval(
                RuntimeService(store),
                {"objective": "Review UI", "targetRoot": "/tmp/project",
                 "skillPackRoot": str(root), "skillNames": ["inversion-interface-craft"]},
                _approval_meta("tamper"),
            )
        assert store.head_sequence() == 0
    finally:
        store.close()
