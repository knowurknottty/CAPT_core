"""CAPT-UPG-025 / CAPT-UPG-026: Skill Foundry authority boundaries.

025: the validation harness must never execute workflow text. Workflow steps are
model-authorable data; running them belongs behind ToolBroker with a governed
approval, not in a validation stage.

026: the model-facing Hermes plugin must not be able to approve or publish a
skill, and SkillFoundry.approve must refuse non-human reviewer identities.
"""
from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

import pytest

from capt_solo.foundry import ProofEngine, SkillFoundry, ValidationHarness
from capt_solo.lifecycle.procedures import ProcedureStore
from capt_solo.memory.engine import MemoryEngine, MemoryError_
from capt_solo.plugin import get_plugin

REPO = Path(__file__).resolve().parents[1]
FOUNDRY = REPO / "capt_solo" / "foundry"


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path / "solo"))
    return tmp_path


def _validated_skill_id(sf: SkillFoundry, ps: ProcedureStore) -> str:
    pid = ps.create("op", steps="echo hello", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    return sf.build_skill(sf.create_candidate(pid), name="op-skill")


# --- CAPT-UPG-025 --------------------------------------------------------

def test_harness_starts_no_process_for_any_workflow_step(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launched: list[str] = []

    def refuse(*args: object, **kwargs: object) -> None:
        launched.append(repr(args[:1]))
        raise AssertionError("validation harness attempted to start a process")

    monkeypatch.setattr(os, "system", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)

    eng = MemoryEngine()
    try:
        ps = ProcedureStore(eng)
        pe = ProofEngine(eng._conn)
        sf = SkillFoundry(eng._conn, pe, ps)
        sid = _validated_skill_id(sf, ps)
        report = sf.validate(sid, ValidationHarness(pe))
    finally:
        eng.close()

    assert launched == []
    execution = next(s for s in report.to_dict()["stages"] if s["name"] == "execution")
    assert execution["status"] != "fail"
    assert any("not executed" in w for w in execution["warnings"])


def test_foundry_source_has_no_shell_or_process_execution() -> None:
    offenders: list[str] = []
    for path in sorted(FOUNDRY.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            if name in {"os.system", "os.popen"} or name.startswith(("subprocess.", "os.exec", "os.spawn")):
                offenders.append(f"{path.relative_to(REPO)}:{node.lineno}: {name}")
    assert offenders == []


# --- CAPT-UPG-026 --------------------------------------------------------

def test_plugin_exposes_no_approve_or_publish_tool() -> None:
    plugin = get_plugin()
    assert not hasattr(plugin, "capt_publish_skill")
    assert not hasattr(plugin, "capt_approve_skill")
    manifest = (REPO / "capt_solo" / "plugin" / "plugin.json").read_text(encoding="utf-8")
    assert "capt_publish_skill" not in manifest


def test_plugin_review_request_stops_at_reviewing(isolated_home: Path) -> None:
    eng = MemoryEngine()
    try:
        ps = ProcedureStore(eng)
        pe = ProofEngine(eng._conn)
        sf = SkillFoundry(eng._conn, pe, ps)
        sid = _validated_skill_id(sf, ps)
        sf.validate(sid, ValidationHarness(pe))
    finally:
        eng.close()
    result = get_plugin().capt_request_skill_review(sid)
    assert result == {"ok": True, "lifecycle": "reviewing"}


@pytest.mark.parametrize("reviewer", ["hermes", "Hermes", "skill_foundry", "agent", "  model "])
def test_approve_refuses_non_human_reviewer(isolated_home: Path, reviewer: str) -> None:
    eng = MemoryEngine()
    try:
        ps = ProcedureStore(eng)
        pe = ProofEngine(eng._conn)
        sf = SkillFoundry(eng._conn, pe, ps)
        sid = _validated_skill_id(sf, ps)
        sf.validate(sid, ValidationHarness(pe))
        sf.submit_for_review(sid)
        with pytest.raises(MemoryError_, match="non-human reviewer"):
            sf.approve(sid, reviewer=reviewer)
        sf.approve(sid, reviewer="captain")
        assert sf.get(sid).lifecycle_state == "approved"
    finally:
        eng.close()
