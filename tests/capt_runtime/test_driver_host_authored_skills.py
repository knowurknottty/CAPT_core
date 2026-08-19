"""DriverHost integration for explicitly selected authored skills."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from capt_runtime.authored_skills import (
    AuthoredSkillPackViolation,
    load_capt_skills_lock,
)
from capt_runtime.driver_host import DriverHost
from capt_runtime.drivers.registry import DriverRegistry


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _pack(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "CAPT_Skills"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "CAPT Tests")
    _git(root, "remote", "add", "origin",
         "https://github.com/knowurknottty/CAPT_Skills.git")
    name = "inversion-creative-critic"
    path = root / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    content = (
        "---\n"
        f"name: {name}\n"
        "version: 0.1.0\n"
        "---\n\n"
        "# Critic\n\nOnly claim what evidence supports.\n"
    )
    path.write_text(content)
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    lock = {
        "schemaVersion": "1.0.0",
        "packName": "CAPT_Skills",
        "packVersion": "0.1.0",
        "repository": "https://github.com/knowurknottty/CAPT_Skills.git",
        "ref": "v0.1.0",
        "commit": _git(root, "rev-parse", "HEAD"),
        "tree": _git(root, "rev-parse", "HEAD^{tree}"),
        "skills": [{
            "name": name,
            "version": "0.1.0",
            "path": f"skills/{name}/SKILL.md",
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
        }],
    }
    return root, lock


def _lease():
    return {
        "leaseId": "l1", "operations": ["RepositoryRead"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": True},
        "validFrom": "2026-01-01T00:00:00Z", "validUntil": "2030-01-01T00:00:00Z",
    }


def test_packaged_lock_pins_capt_skills_v010():
    lock = load_capt_skills_lock()
    assert lock["packName"] == "CAPT_Skills"
    assert lock["packVersion"] == "0.1.0"
    assert lock["commit"] == "080446e2e8b8774ece41285e50d1c9c903984ba2"
    assert {s["name"] for s in lock["skills"]} == {
        "inversion-creative-critic", "inversion-creative-director",
        "inversion-interface-craft", "inversion-motion-craft",
    }


def test_driver_host_build_context_verifies_and_embeds_explicit_skill(tmp_path):
    root, lock = _pack(tmp_path)
    host = DriverHost(
        DriverRegistry(), str(tmp_path / "staging"), "/tmp",
        authored_skill_pack_root=str(root), authored_skill_pack_lock=lock,
    )
    ctx = host.build_context(
        _lease(), [], {"maxSeconds": 30}, [], {"onUnexpectedWrite": "fail"},
        skill_names=["inversion-creative-critic"],
    )
    assert ctx["skillContext"]["trust"] == "pinned_external"
    assert ctx["skillContext"]["skills"][0]["name"] == "inversion-creative-critic"
    assert "Only claim what evidence supports" in ctx["skillContext"]["skills"][0]["content"]


def test_driver_host_refuses_skill_selection_without_configured_pack_root(tmp_path):
    host = DriverHost(DriverRegistry(), str(tmp_path / "staging"), "/tmp")
    with pytest.raises(AuthoredSkillPackViolation, match="pack root"):
        host.build_context(
            _lease(), [], {"maxSeconds": 30}, [], {"onUnexpectedWrite": "fail"},
            skill_names=["inversion-creative-critic"],
        )


def test_runtime_composition_hermes_host_propagates_authored_pack(tmp_path):
    from capt_runtime.composition import create_runtime

    root, lock = _pack(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        host = runtime.hermes_host(
            target_repo=str(target), staging_root=str(tmp_path / "staging"),
            executable="/bin/echo", enforce_memory=False,
            authored_skill_pack_root=str(root), authored_skill_pack_lock=lock,
        )
        ctx = host.build_context(
            _lease(), [], {"maxSeconds": 30}, [], {"onUnexpectedWrite": "fail"},
            skill_names=["inversion-creative-critic"],
        )
        assert ctx["skillContext"]["sourceCommit"] == lock["commit"]
        assert ctx["skillContext"]["skills"][0]["name"] == "inversion-creative-critic"
    finally:
        runtime.close()


def test_model_operator_helper_binds_payload_selection_to_verified_host(tmp_path):
    from capt_runtime.composition import create_runtime
    from desktop.capt_runtime_service import _prepare_hermes_host_with_authored_skills

    root, lock = _pack(tmp_path)
    target = tmp_path / "target-operator"
    target.mkdir()
    runtime = create_runtime(str(tmp_path / "operator-ledger.db"))
    try:
        host, names = _prepare_hermes_host_with_authored_skills(
            runtime,
            {"skillPackRoot": str(root), "skillNames": ["inversion-creative-critic"]},
            target_repo=str(target), staging_root=str(tmp_path / "operator-staging"),
            executable="/bin/echo", authored_skill_pack_lock=lock,
        )
        assert names == ["inversion-creative-critic"]
        ctx = host.build_context(
            _lease(), [], {"maxSeconds": 30}, [], {"onUnexpectedWrite": "fail"},
            skill_names=names,
        )
        assert ctx["skillContext"]["sourceCommit"] == lock["commit"]
    finally:
        runtime.close()


def test_prepared_authored_skills_freeze_verified_snapshot_before_dispatch(tmp_path):
    root, lock = _pack(tmp_path)
    host = DriverHost(
        DriverRegistry(), str(tmp_path / "staging-prepared"), "/tmp",
        authored_skill_pack_root=str(root), authored_skill_pack_lock=lock,
    )
    summary = host.prepare_authored_skills(["inversion-creative-critic"])
    assert summary["skills"][0]["name"] == "inversion-creative-critic"

    # Change the checkout after preflight. Context construction must use the
    # already verified immutable snapshot rather than silently re-reading disk.
    skill_file = root / lock["skills"][0]["path"]
    skill_file.write_text(skill_file.read_text() + "\nPOST_PREFLIGHT_TAMPER\n")
    ctx = host.build_context(
        _lease(), [], {"maxSeconds": 30}, [], {"onUnexpectedWrite": "fail"},
    )
    body = ctx["skillContext"]["skills"][0]["content"]
    assert "POST_PREFLIGHT_TAMPER" not in body
    assert ctx["skillContext"]["manifestDigest"] == summary["manifestDigest"]


def test_model_operator_skill_preflight_failure_leaves_ledger_untouched(tmp_path):
    from capt_runtime.composition import create_runtime
    from desktop.capt_runtime_service import _prepare_hermes_host_with_authored_skills

    root, lock = _pack(tmp_path)
    skill_file = root / lock["skills"][0]["path"]
    skill_file.write_text(skill_file.read_text() + "\nTAMPER_BEFORE_PREFLIGHT\n")
    target = tmp_path / "target-preflight-fail"
    target.mkdir()
    runtime = create_runtime(str(tmp_path / "preflight-ledger.db"))
    try:
        assert runtime.store.head_sequence() == 0
        with pytest.raises(AuthoredSkillPackViolation):
            _prepare_hermes_host_with_authored_skills(
                runtime,
                {"skillPackRoot": str(root), "skillNames": ["inversion-creative-critic"]},
                target_repo=str(target), staging_root=str(tmp_path / "preflight-staging"),
                executable="/bin/echo", authored_skill_pack_lock=lock,
            )
        assert runtime.store.head_sequence() == 0
    finally:
        runtime.close()
