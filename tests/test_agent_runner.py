"""Focused runner + output tests for the CAPT Agent Runner (ADR-0001).

Uses an isolated temporary RuntimeConfiguration and a deterministic in-process
ModelProvider TEST-DOUBLE (a real ModelProvider implementation — this doubles
the model transport only; all CAPT governance runs for real). No network, no
owner CAPT home mutation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from capt_solo.agent import (
    EXECUTION_MODE_GOVERNED,
    AgentBootRequest,
    AgentRunner,
    AgentTurnRequest,
    IntentRecord,
    OutputPolicy,
)
from capt_solo.agent import output as output_mod
from capt_solo.agent.runner import resume_report
from capt_solo.evidence import CheckpointStore, MissionCheckpoint
from capt_solo.foundry import ProofRequirement
from capt_solo.model_task import ModelIdentity, ModelTaskRequest, ModelTaskResult
from capt_solo.runtime import RuntimeConfiguration


# --- deterministic in-process provider (ModelProvider test-double) ----------
class FakeProvider:
    def __init__(self, text="Next action: add canonical boot path.", tool_calls=()):
        self._text = text
        self._tool_calls = tuple(tool_calls)
        self.invoke_count = 0
        self.last_request = None

    def identity(self) -> ModelIdentity:
        return ModelIdentity(provider="fake", model_id="fake-1", local=True)

    def invoke(self, request: ModelTaskRequest) -> ModelTaskResult:
        self.invoke_count += 1
        self.last_request = request
        return ModelTaskResult(
            task_id=request.task_id, provider="fake", model_id="fake-1",
            request_artifact_id="", response_artifact_id="", response_text=self._text,
            tool_calls=self._tool_calls, finish_reason="stop",
            input_tokens=10, output_tokens=5, latency_ms=1,
        )


def _git(ws, *a):
    return subprocess.run(["git", "-C", str(ws), *a], capture_output=True, text=True).stdout.strip()


@pytest.fixture
def env(tmp_path):
    ws = tmp_path / "capt-solo"
    ws.mkdir()
    subprocess.run(["git", "init", "-q", str(ws)], check=True)
    (ws / "f.txt").write_text("x")
    subprocess.run(["git", "-C", str(ws), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(ws), "-c", "user.email=a@b.c", "-c", "user.name=t",
         "commit", "-qm", "init"], check=True,
    )
    store = CheckpointStore(str(ws))
    store.save(MissionCheckpoint(
        mission_id="mission-x", project_id="capt-solo",
        objective="Implement the canonical CAPT Agent Runner",
        current_phase="3", latest_verified_state=_git(ws, "rev-parse", "HEAD"),
        next_safe_action="add canonical boot path",
        decisions_made=["Outcome C accepted (ADR-0001)", "Outcome A rejected; superseded by ADR-0001"],
    ))
    cfg = RuntimeConfiguration(
        db_path=tmp_path / "memory.db", journal_dir=tmp_path / "ctp",
        evidence_dir=tmp_path / "evidence", event_log_path=tmp_path / "khsb" / "events.jsonl",
    )
    return ws, cfg


def _intent(state):
    return IntentRecord.mint(
        mission_id=state.mission_id, session_id=state.session_id,
        turn_id=state.next_turn_id(), requested_goal="Resume the active mission.",
        current_goal="Report the next justified action.",
        completion_criteria=("report next action",), output_policy=state.output_policy,
    )


# --- one governed turn ------------------------------------------------------

def test_one_governed_turn_invokes_provider_exactly_once(env):
    ws, cfg = env
    runner = AgentRunner.load(cfg)
    try:
        br = runner.boot(AgentBootRequest(workspace_path=str(ws), mission_id="mission-x"))
        assert br.execution_mode == EXECUTION_MODE_GOVERNED
        state = runner.run_state(br)
        provider = FakeProvider()
        # acceptance input does NOT contain the recovered next action
        req = AgentTurnRequest(intent=_intent(state), user_input="Resume the active mission. Report the next justified action.")
        res = runner.run_turn(state, req, provider=provider)
        assert res.ok is True
        assert provider.invoke_count == 1
        assert res.tx_id
        assert res.checkpoint_id
        assert res.gate_result == "PASS"
        # selected memory / recovered state rendered into the ACTUAL request
        assert "mission-x" in provider.last_request.system_prompt
        # no transcript supplied
        assert "Resume the active mission" not in provider.last_request.system_prompt
    finally:
        runner.close()


def test_gate_runs_before_provider_on_blocked_pack(env, monkeypatch):
    ws, cfg = env
    runner = AgentRunner.load(cfg)
    try:
        br = runner.boot(AgentBootRequest(workspace_path=str(ws), mission_id="mission-x"))
        state = runner.run_state(br)
        provider = FakeProvider()
        # force the gate to block inside execute_model_task
        from capt_solo.runtime import GateDecision

        def _blocked(*a, **k):
            class V:
                status = "BLOCK"
                blocks = []
            return GateDecision(allowed=False, pack=None, validation=V(), retrieved={})
        monkeypatch.setattr(runner.rt.gate, "prepare", _blocked)
        res = runner.run_turn(state, AgentTurnRequest(intent=_intent(state), user_input="x"), provider=provider)
        assert res.ok is False
        assert provider.invoke_count == 0  # provider never reached
        assert res.gate_result == "BLOCKED"
    finally:
        runner.close()


def test_tool_calls_are_reported_not_executed(env):
    ws, cfg = env
    runner = AgentRunner.load(cfg)
    try:
        br = runner.boot(AgentBootRequest(workspace_path=str(ws), mission_id="mission-x"))
        state = runner.run_state(br)
        provider = FakeProvider(tool_calls=({"name": "shell", "args": {"cmd": "rm -rf /"}},))
        res = runner.run_turn(state, AgentTurnRequest(intent=_intent(state), user_input="x"), provider=provider)
        assert res.ok is True
        assert "NOT executed" in res.visible_output
    finally:
        runner.close()


def test_claimguard_evaluated_when_capability_given(env):
    ws, cfg = env
    runner = AgentRunner.load(cfg)
    try:
        runner.rt.registry.register("cap_turn", "agent turn", "capt_solo", lifecycle="verified")
        runner.rt.proof.record("test_pass", "pytest", "h", "t", scope="cap_turn")
        runner.rt.proof.set_requirements("cap_turn", [ProofRequirement("test_pass", 1, "cap_turn")])
        br = runner.boot(AgentBootRequest(workspace_path=str(ws), mission_id="mission-x"))
        state = runner.run_state(br)
        req = AgentTurnRequest(
            intent=_intent(state), user_input="x",
            capability_id="cap_turn", claim_text="Turn complete and verified.",
        )
        res = runner.run_turn(state, req, provider=FakeProvider())
        assert res.claim_supported is True
    finally:
        runner.close()


# --- fresh-process resume ---------------------------------------------------

def test_fresh_process_resume_reconstructs_from_capt_state(env):
    ws, cfg = env
    # process 1: boot + one turn + checkpoint
    runner = AgentRunner.load(cfg)
    try:
        br = runner.boot(AgentBootRequest(workspace_path=str(ws), mission_id="mission-x"))
        state = runner.run_state(br)
        runner.run_turn(state, AgentTurnRequest(intent=_intent(state), user_input="x"), provider=FakeProvider())
    finally:
        runner.close()
    # process 2: only workspace + mission id (+ isolated cfg)
    report = resume_report(workspace_path=str(ws), mission_id="mission-x", configuration=cfg)
    assert report["mission_id"] == "mission-x"
    assert report["execution_mode"] == EXECUTION_MODE_GOVERNED
    assert report["gate_result"] == "PASS"
    assert report["next_justified_action"] == "add canonical boot path"
    assert "no transcript" in report["source"]
    # persisted independent report
    assert (Path(cfg.evidence_dir) / "agent-resume" / "mission-x.json").exists()


# --- CaveCAPT renderer ------------------------------------------------------

def test_cave_default_suppresses_narration_keeps_summary():
    p = OutputPolicy.for_mode("cave")
    out = output_mod.render(
        p, summary="Next: implement runner.\nCheckpoint written.",
        narration=["thinking about the plan", "considering options"],
        phase_completions=["Mission resumed.", "Memory gate passed."],
        provider_response="a very long provider response " * 50,
    )
    assert "thinking about the plan" not in out
    assert "Mission resumed." in out
    assert "Checkpoint written." in out
    # cave does not dump the raw provider response
    assert "a very long provider response a very long" not in out


def test_blockers_and_safety_bypass_cap():
    p = OutputPolicy(mode="cave", max_visible_chars=10)
    out = output_mod.render(
        p, summary="x" * 500, blockers=["critical blocker that is quite long and must not truncate"],
        safety=["do not delete owner files"],
    )
    assert "critical blocker that is quite long and must not truncate" in out
    assert "do not delete owner files" in out


def test_silent_emits_nothing_on_success_but_keeps_blockers():
    p = OutputPolicy.for_mode("silent")
    assert output_mod.render(p, summary="all good", phase_completions=["done"]) == ""
    out = output_mod.render(p, blockers=["boom"])
    assert "boom" in out


def test_verbose_includes_narration_and_response():
    p = OutputPolicy.for_mode("verbose")
    out = output_mod.render(p, summary="s", narration=["step reasoning"], provider_response="RESP")
    assert "step reasoning" in out
    assert "RESP" in out


# --- composition root -------------------------------------------------------

def test_runner_uses_single_composition_root(env):
    ws, cfg = env
    runner = AgentRunner.load(cfg)
    try:
        # runner borrows the runtime's owned subsystems; does not build its own
        assert runner.rt.gate._eng is runner.rt.engine
        assert runner.rt.lifecycle._ctp is runner.rt.ctp
        assert runner.rt.claimguard._reg is runner.rt.registry
    finally:
        runner.close()


def test_no_duplicate_composition_root_in_agent_pkg():
    import capt_solo.agent.boot as b
    import capt_solo.agent.runner as r
    # boot must never construct a runtime; runner constructs exactly via load()
    bsrc = Path(b.__file__).read_text()
    assert "CAPTRuntime(" not in bsrc and "CAPTRuntime.load(" not in bsrc
    rsrc = Path(r.__file__).read_text()
    # exactly one construction site: CAPTRuntime.load inside AgentRunner.load
    assert rsrc.count("CAPTRuntime.load(") == 1
    assert "CAPTRuntime(" not in rsrc.replace("CAPTRuntime.load(", "")
