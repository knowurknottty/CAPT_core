"""Focused tests for the packaged governed model operator.

Covers: composition hermes_host factory wiring, the governed
run_approved_hermes_inspection routing in RuntimeCommandService, and
authoritative objective derivation into the Hermes prompt.
"""
from __future__ import annotations

from pathlib import Path

from capt_runtime.composition import create_runtime
from capt_runtime.drivers.hermes import DESCRIPTOR as HERMES_DESCRIPTOR
from capt_runtime.drivers.hermes import HermesDriver, build_prompt
from capt_runtime.task_resolver import TaskResolver
from desktop.m1_command_service import RuntimeCommandService


def _envelope(op: str, payload: dict, *, operator: str = "operator-x", session: str = "sess-1") -> dict:
    return {
        "commandId": "cmd-model-1",
        "operatorId": operator,
        "sessionId": session,
        "schemaVersion": "1.0.0",
        "correlationId": "corr-model",
        "idempotencyKey": "idem-model-1",
        "timestamp": "2026-08-05T00:00:00Z",
        "op": op,
        "payload": payload,
    }


def test_composition_hermes_host_registers_and_wires_resolver(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "README.md").write_text("# target\n")
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        host = runtime.hermes_host(
            target_repo=str(target), staging_root=str(tmp_path / "staging"),
            executable="/bin/echo", enforce_memory=False,
        )
        assert runtime.registry.is_registered(HERMES_DESCRIPTOR["driverId"])
        assert runtime.registry.list_drivers() == ["hermes"]
        assert host.registry is runtime.registry
        driver = host._driver
        assert isinstance(driver, HermesDriver)
        assert isinstance(driver._task_resolver, TaskResolver)
    finally:
        runtime.close()


def test_governed_hermes_op_routes_to_runner_and_is_idempotent(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        svc = RuntimeCommandService(runtime.store, "operator-x", "sess-1",
                                    runtime_service=runtime.service)
        seen = {"calls": 0, "prior": None}

        def stub_runner(command):
            seen["calls"] += 1
            if seen["prior"] is not None:
                return {**seen["prior"], "_idempotent": True}
            seen["prior"] = {"missionId": "m-model-1", "taskId": "t-model-1",
                             "driverRunId": "dr-model-1"}
            return seen["prior"]

        svc.approved_hermes_runner = stub_runner
        cmd = _envelope("run_approved_hermes_inspection",
                        {"objective": "x", "targetRoot": "/tmp"})
        first = svc.execute(cmd)
        assert first["status"] == "accepted"
        assert first["result"]["missionId"] == "m-model-1"
        assert seen["calls"] == 1
        # Same idempotency key -> receipt is idempotent and the runner
        # re-emits the prior receipt (no new work, no reinference).
        second = svc.execute(cmd)
        assert second["status"] == "idempotent"
        assert seen["calls"] == 2
        assert second["result"]["missionId"] == "m-model-1"
    finally:
        runtime.close()



def test_governed_hermes_in_progress_is_not_presented_as_accepted(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        svc = RuntimeCommandService(runtime.store, "operator-x", "sess-1", runtime_service=runtime.service)
        svc.approved_hermes_runner = lambda _cmd: {"status": "in_progress", "commandId": "cmd-model-1"}
        receipt = svc.execute(_envelope("run_approved_hermes_inspection", {"objective": "x", "targetRoot": "/tmp"}))
        assert receipt["status"] == "in_progress"
        assert receipt["classification"] == "in_progress"
    finally:
        runtime.close()


def test_governed_hermes_op_rejected_when_runner_unset(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        svc = RuntimeCommandService(runtime.store, "operator-x", "sess-1",
                                    runtime_service=runtime.service)
        cmd = _envelope("run_approved_hermes_inspection",
                        {"objective": "x", "targetRoot": "/tmp"})
        receipt = svc.execute(cmd)
        assert receipt["status"] == "rejected"
        assert receipt["classification"] == "internal_failure"
        assert receipt["error"]["code"] == "HERMES_DRIVER_UNAVAILABLE"
    finally:
        runtime.close()


def test_hermes_prompt_uses_resolved_objective_when_resolver_present(tmp_path: Path) -> None:
    from capt_runtime import commands
    from capt_runtime.services import RuntimeService
    from capt_runtime.store import EventStore

    store = EventStore(str(tmp_path / "ledger.db"))
    svc = RuntimeService(store)
    meta = commands.command(command_id="cmd", idempotency_key="idem",
                            operation_fingerprint="sha256:" + "0" * 64,
                            correlation_id="corr", actor_id="captain",
                            actor_kind="human", issued_at="2026-08-05T00:00:00Z")
    svc.create_mission(
        {"schemaVersion": "1.0.0", "missionId": "m-1", "rawRequest": "x",
         "normalizedRequest": "x", "objectives": [{"objectiveId": "o", "statement": "x", "priority": 1}],
         "constraints": [], "successCriteria": [{"criterionId": "s", "statement": "x", "requiresVerification": True}],
         "terminationCriteria": [{"criterionId": "t", "statement": "x", "terminalState": "failed"}],
         "unresolvedAmbiguities": [], "taskGraphId": None, "createdAt": "2026-08-05T00:00:00Z"},
        meta)
    svc.create_task(
        {"taskId": "t-1", "missionId": "m-1", "title": "Inspect version declarations.",
         "state": "pending", "consequential": False,
         "capabilityRequirements": [{"requirementId": "r", "capabilityId": "cap.fs.read",
                                     "operations": ["repository.read"],
                                     "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": True}}],
         "assignedDriverId": None, "attempt": 0, "maxAttempts": 1, "recoveryState": "none"},
        commands.command(command_id="cmd-t", idempotency_key="idem-t",
                         operation_fingerprint="sha256:" + "1" * 64,
                         correlation_id="corr", actor_id="cog", actor_kind="cognitive_plane",
                         issued_at="2026-08-05T00:00:00Z"))
    resolver = TaskResolver(store)
    prompt = build_prompt(
        {"target": "/tmp", "filesystemPolicy": {"rootPath": "/tmp", "writesAllowed": False,
                                                "allowedPaths": ["/tmp"]},
         "budgets": {"maxSeconds": 60, "maxTokens": 1000}, "tools": [],
         "egress": {"egressAllowed": False}, "contextPackRef": None,
         "networkPolicy": {"egressAllowed": False}},
        ["RepositoryRead", "FilesystemRead", "AnalysisOnly"],
        objective=resolver.resolve_for_execution(mission_id="m-1", task_id="t-1").objective,
    )
    assert "Inspect version declarations." in prompt
    assert "OBSERVATION:" not in prompt
    store.close()


def test_hermes_prompt_retains_fixed_mode_without_resolver() -> None:
    prompt = build_prompt(
        {"target": "/tmp", "filesystemPolicy": {"rootPath": "/tmp", "writesAllowed": False,
                                                "allowedPaths": ["/tmp"]},
         "budgets": {"maxSeconds": 60, "maxTokens": 1000}, "tools": [],
         "egress": {"egressAllowed": False}, "contextPackRef": None,
         "networkPolicy": {"egressAllowed": False}},
        ["RepositoryRead", "FilesystemRead", "AnalysisOnly"],
    )
    assert "OBSERVATION:" in prompt
    assert "inspect the target directory and describe its runtime architecture" in prompt
