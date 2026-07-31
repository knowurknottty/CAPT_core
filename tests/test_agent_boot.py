"""Focused boot tests for the standalone CAPT Agent Runner (ADR-0001, Outcome C).

All tests use an ISOLATED temporary RuntimeConfiguration + workspace; none touch
the canonical owner CAPT home. Boot must be fail-closed and must never reach a
provider.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from capt_solo.agent import (
    EXECUTION_MODE_BLOCKED,
    EXECUTION_MODE_BOOTSTRAP_DEGRADED,
    EXECUTION_MODE_GOVERNED,
    AgentBootRequest,
)
from capt_solo.agent import boot as boot_mod
from capt_solo.agent.boot import boot
from capt_solo.evidence import CheckpointStore, MissionCheckpoint
from capt_solo.runtime import CAPTRuntime, RuntimeConfiguration


def _git(ws: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ws), *args], capture_output=True, text=True, check=False
    ).stdout.strip()


@pytest.fixture
def ws(tmp_path):
    # workspace dir name must match project_id (foreign-workspace check)
    d = tmp_path / "capt-solo"
    d.mkdir()
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    (d / "f.txt").write_text("x")
    subprocess.run(["git", "-C", str(d), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(d), "-c", "user.email=a@b.c", "-c", "user.name=t",
         "commit", "-qm", "init"], check=True,
    )
    return d


@pytest.fixture
def rt(tmp_path):
    cfg = RuntimeConfiguration(
        db_path=tmp_path / "memory.db", journal_dir=tmp_path / "ctp",
        evidence_dir=tmp_path / "evidence", event_log_path=tmp_path / "khsb" / "events.jsonl",
    )
    r = CAPTRuntime.load(cfg)
    yield r
    r.close()


def _save_mission(ws: Path, mission_id="mission-x", *, status="active",
                  objective="Implement the canonical CAPT Agent Runner",
                  decisions=None, phase="3", head=None, **kw):
    store = CheckpointStore(str(ws))
    head = head if head is not None else _git(ws, "rev-parse", "HEAD")
    cp = MissionCheckpoint(
        mission_id=mission_id, project_id="capt-solo", objective=objective,
        current_phase=phase, latest_verified_state=head, status=status,
        next_safe_action=kw.pop("next_safe_action", "add canonical boot path"),
        decisions_made=decisions if decisions is not None else [
            "Outcome C accepted (ADR-0001)",
            "Outcome A rejected; superseded by ADR-0001",
        ],
        **kw,
    )
    store.save(cp)
    return cp


# --- mission resolution -----------------------------------------------------

def test_explicit_mission_resolution(rt, ws):
    _save_mission(ws)
    res = boot(AgentBootRequest(workspace_path=str(ws), mission_id="mission-x"), runtime=rt)
    assert res.execution_mode == EXECUTION_MODE_GOVERNED
    assert res.mission_id == "mission-x"
    assert res.gate_result == "PASS"


def test_checkpoint_derived_mission_resolution(rt, ws):
    # session-bound mission id (recovered from an applicable session checkpoint)
    _save_mission(ws, mission_id="mission-sess")
    res = boot(
        AgentBootRequest(workspace_path=str(ws)),
        runtime=rt, session_bound_mission_id="mission-sess",
    )
    assert res.execution_mode == EXECUTION_MODE_GOVERNED
    assert res.mission_id == "mission-sess"


def test_discovery_single_active_mission(rt, ws):
    _save_mission(ws, mission_id="only-active")
    res = boot(AgentBootRequest(workspace_path=str(ws)), runtime=rt)
    assert res.execution_mode == EXECUTION_MODE_GOVERNED
    assert res.mission_id == "only-active"


def test_missing_mission_blocks(rt, ws):
    res = boot(AgentBootRequest(workspace_path=str(ws), mission_id="nope"), runtime=rt)
    assert res.execution_mode == EXECUTION_MODE_BLOCKED
    assert "MISSION_NOT_FOUND" in res.block_codes


def test_ambiguous_mission_blocks_and_records_candidates(rt, ws):
    _save_mission(ws, mission_id="alpha")
    _save_mission(ws, mission_id="beta")
    res = boot(AgentBootRequest(workspace_path=str(ws)), runtime=rt)
    assert res.execution_mode == EXECUTION_MODE_BLOCKED
    assert "MISSION_AMBIGUOUS" in res.block_codes
    assert "alpha" in res.block_reason and "beta" in res.block_reason


def test_newest_is_not_auto_selected(rt, ws):
    # two active missions -> ambiguous, must NOT pick the newest
    _save_mission(ws, mission_id="older")
    _save_mission(ws, mission_id="newer")
    res = boot(AgentBootRequest(workspace_path=str(ws)), runtime=rt)
    assert res.execution_mode == EXECUTION_MODE_BLOCKED


# --- checkpoint validation --------------------------------------------------

def test_corrupted_checkpoint_blocks(rt, ws):
    _save_mission(ws, mission_id="corrupt")
    path = Path(ws) / ".capt" / "checkpoints" / "corrupt.json"
    data = json.loads(path.read_text())
    data["objective"] = "TAMPERED after digest was computed"  # digest now mismatches
    path.write_text(json.dumps(data, indent=2))
    res = boot(AgentBootRequest(workspace_path=str(ws), mission_id="corrupt"), runtime=rt)
    assert res.execution_mode == EXECUTION_MODE_BLOCKED
    assert "CHECKPOINT_INTEGRITY" in res.block_codes


def test_foreign_workspace_checkpoint_blocks(rt, ws):
    # project_id != workspace dir name
    store = CheckpointStore(str(ws))
    cp = MissionCheckpoint(
        mission_id="foreign", project_id="some-other-project",
        objective="x", current_phase="1", latest_verified_state=_git(ws, "rev-parse", "HEAD"),
    )
    store.save(cp)
    res = boot(AgentBootRequest(workspace_path=str(ws), mission_id="foreign"), runtime=rt)
    assert res.execution_mode == EXECUTION_MODE_BLOCKED
    assert "FOREIGN_WORKSPACE" in res.block_codes


def test_stale_checkpoint_still_boots_but_records_divergence(rt, ws):
    # head recorded that != current HEAD -> divergence recorded, still GOVERNED
    _save_mission(ws, mission_id="stale", head="0" * 40)
    res = boot(AgentBootRequest(workspace_path=str(ws), mission_id="stale"), runtime=rt)
    assert res.execution_mode == EXECUTION_MODE_GOVERNED
    assert res.boot_trace is not None


def test_missing_workspace_blocks(rt, tmp_path):
    res = boot(
        AgentBootRequest(workspace_path=str(tmp_path / "does-not-exist"), mission_id="m"),
        runtime=rt,
    )
    assert res.execution_mode == EXECUTION_MODE_BLOCKED
    assert "WORKSPACE_MISSING" in res.block_codes


# --- directives -------------------------------------------------------------

def test_active_directive_retrieval_and_supersession(rt, ws):
    _save_mission(ws, mission_id="dir", decisions=[
        "Outcome C accepted (ADR-0001)",
        "Outcome A rejected; superseded by ADR-0001",
        "milestone corrected to GOVERNED_EXTERNAL_TURN_TRANSACTION_PROVEN",
    ])
    res = boot(AgentBootRequest(workspace_path=str(ws), mission_id="dir"), runtime=rt)
    assert res.execution_mode == EXECUTION_MODE_GOVERNED
    assert "Outcome C accepted (ADR-0001)" in res.active_directive_ids
    # superseded/rejected/corrected are NOT active
    assert all("rejected" not in d.lower() for d in res.active_directive_ids)
    assert res.boot_trace.superseded_directive_ids  # captured


# --- gate + degraded --------------------------------------------------------

def test_gate_denial_blocks_by_default(rt, ws, monkeypatch):
    _save_mission(ws, mission_id="gate")

    class _Blocked:
        allowed = False
        block_codes = ["FIDELITY_BLOCK"]
        pack = None
        retrieved = {}
    monkeypatch.setattr(rt.gate, "prepare", lambda *a, **k: _Blocked())
    res = boot(AgentBootRequest(workspace_path=str(ws), mission_id="gate"), runtime=rt)
    assert res.execution_mode == EXECUTION_MODE_BLOCKED
    assert "FIDELITY_BLOCK" in res.block_codes


def test_degraded_requires_durable_authorization(rt, ws, monkeypatch):
    # durable-state marker authorizes degraded mode on a gate miss
    _save_mission(ws, mission_id="deg", decisions=[
        "Outcome C accepted (ADR-0001)",
        "BOOTSTRAP_DEGRADED_AUTHORIZED by owner for bootstrap phase",
    ])

    class _Blocked:
        allowed = False
        block_codes = ["FIDELITY_BLOCK"]
        pack = None
        retrieved = {}
    monkeypatch.setattr(rt.gate, "prepare", lambda *a, **k: _Blocked())
    res = boot(AgentBootRequest(workspace_path=str(ws), mission_id="deg"), runtime=rt)
    assert res.execution_mode == EXECUTION_MODE_BOOTSTRAP_DEGRADED
    assert res.gate_result == "DEGRADED"


def test_request_flag_cannot_grant_degraded(rt, ws, monkeypatch):
    # authorize_bootstrap_degraded on the REQUEST must NOT be enough
    _save_mission(ws, mission_id="deg2")

    class _Blocked:
        allowed = False
        block_codes = ["FIDELITY_BLOCK"]
        pack = None
        retrieved = {}
    monkeypatch.setattr(rt.gate, "prepare", lambda *a, **k: _Blocked())
    res = boot(
        AgentBootRequest(workspace_path=str(ws), mission_id="deg2",
                         authorize_bootstrap_degraded=True),
        runtime=rt,
    )
    assert res.execution_mode == EXECUTION_MODE_BLOCKED


# --- output policy ----------------------------------------------------------

def test_cavecapt_is_default_output(rt, ws):
    _save_mission(ws, mission_id="cave")
    res = boot(AgentBootRequest(workspace_path=str(ws), mission_id="cave"), runtime=rt)
    assert res.output_policy.mode == "cave"
    assert res.output_policy.show_narration is False


def test_explicit_output_mode_override(rt, ws):
    _save_mission(ws, mission_id="verbose")
    res = boot(
        AgentBootRequest(workspace_path=str(ws), mission_id="verbose", output_mode="verbose"),
        runtime=rt,
    )
    assert res.output_policy.mode == "verbose"
    assert res.output_policy.show_narration is True


# --- trace shape + intent ---------------------------------------------------

def test_deterministic_boot_trace_shape(rt, ws):
    _save_mission(ws, mission_id="trace")
    res = boot(AgentBootRequest(workspace_path=str(ws), mission_id="trace"), runtime=rt)
    t = res.boot_trace
    assert t is not None
    for field_name in (
        "agent_run_id", "mission_id", "session_id", "checkpoint_id", "workspace_path",
        "git_branch", "git_sha", "intent_id", "intent_digest", "contextpack_digest",
        "memory_use_decision_id", "gate_result", "execution_mode", "output_mode",
        "next_justified_action", "artifact_hash",
    ):
        assert getattr(t, field_name) is not None
    assert t.intent_id.startswith("intent-")
    assert t.artifact_hash.startswith("sha256:")
    assert t.execution_mode == EXECUTION_MODE_GOVERNED


def test_boot_persists_trace_artifact(rt, ws):
    _save_mission(ws, mission_id="persist")
    res = boot(AgentBootRequest(workspace_path=str(ws), mission_id="persist"), runtime=rt)
    art = Path(rt.config.evidence_dir) / "agent-boot" / f"{res.boot_trace.agent_run_id}.json"
    assert art.exists()
    saved = json.loads(art.read_text())
    assert saved["mission_id"] == "persist"
    assert saved["intent_id"] == res.boot_trace.intent_id


# --- no provider reachable from boot ---------------------------------------

def test_no_provider_reachable_from_boot():
    src = Path(boot_mod.__file__).read_text()
    # boot must not import or invoke a ModelProvider / .invoke(
    assert "ModelProvider" not in src
    assert "provider.invoke" not in src
    assert "OpenAICompatibleLocalProvider" not in src


def test_boot_does_not_construct_second_runtime():
    src = Path(boot_mod.__file__).read_text()
    # boot composes an injected runtime; it must not call CAPTRuntime.load / construct one
    assert "CAPTRuntime.load(" not in src
    assert "CAPTRuntime(" not in src
