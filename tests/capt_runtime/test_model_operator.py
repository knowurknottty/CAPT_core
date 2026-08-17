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
from capt_runtime.prepared_execution import PreparedApprovedModelExecution, freeze
from capt_runtime.task_resolver import TaskResolver
from desktop.m1_command_service import RuntimeCommandService


def _envelope(
    op: str,
    payload: dict,
    *,
    operator: str = "operator-x",
    session: str = "sess-1",
    key: str | None = None,
) -> dict:
    token = key or op
    return {
        "commandId": "cmd-" + token,
        "operatorId": operator,
        "sessionId": session,
        "schemaVersion": "1.0.0",
        "correlationId": "corr-" + token,
        "idempotencyKey": "idem-" + token,
        "timestamp": "2026-08-17T10:00:00Z",
        "op": op,
        "payload": payload,
    }


def _approved_run_payload(
    svc: RuntimeCommandService, payload: dict, key: str
) -> dict:
    request_payload = {**payload, "expiresAt": "2030-01-01T00:00:00Z"}
    request = svc.execute(
        _envelope(
            "request_model_prompt_approval",
            request_payload,
            key=key + "-request",
        )
    )
    assert request["status"] == "accepted"
    planned = request["result"]
    decision = svc.execute(
        _envelope(
            "submit_approval_decision",
            {"requestId": planned["requestId"], "decision": "approve"},
            key=key + "-decision",
        )
    )
    assert decision["status"] == "accepted"
    authoritative = svc.store.require_state(
        "human_approval-" + planned["requestId"]
    )
    assert authoritative["state"] == "approved"
    return {
        **payload,
        "approvalRequestId": planned["requestId"],
        "missionId": planned["missionId"],
        "taskId": planned["taskId"],
        "driverRunId": planned["driverRunId"],
    }


class _PreparedRunner:
    def __init__(self, svc, *, prepare_error=None, execute_error=None, result=None):
        self.svc, self.prepare_error, self.execute_error = svc, prepare_error, execute_error
        self.result = result or {"missionId": "m-model-1", "taskId": "t-model-1", "driverRunId": "dr-model-1"}
        self.prepared = self.executed = None
        self.execute_calls = 0

    def prepare(self, command):
        if self.prepare_error:
            raise self.prepare_error
        payload = command["payload"]
        approval = self.svc.store.require_state("human_approval-" + payload["approvalRequestId"])
        self.prepared = PreparedApprovedModelExecution(
            command_id=command["commandId"], idempotency_key=command["idempotencyKey"],
            correlation_id=command["correlationId"], issued_at=command["timestamp"],
            approval_request_id=payload["approvalRequestId"],
            prompt_assembly_digest=approval["promptAssemblyDigest"],
            dispatch_prompt_digest="sha256:" + "a" * 64,
            mission_id=payload["missionId"], task_id=payload["taskId"],
            driver_run_id=payload["driverRunId"], resource=payload["targetRoot"],
            objective=payload["objective"], provider_id=None, provider_model=None,
            executable=None, data=freeze({}),
        )
        return self.prepared

    def execute(self, prepared):
        self.execute_calls += 1
        self.executed = prepared
        if self.execute_error:
            raise self.execute_error
        return dict(self.result)


def test_prepared_execution_digest_is_deterministic_and_frozen(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        svc = RuntimeCommandService(runtime.store, "operator-x", "sess-1", runtime_service=runtime.service)
        payload = _approved_run_payload(svc, {"objective": "x", "targetRoot": "/tmp"}, "digest")
        runner = _PreparedRunner(svc)
        prepared = runner.prepare(_envelope("run_approved_hermes_inspection", payload, key="digest-run"))
        first = prepared.prepared_execution_digest
        assert first == prepared.prepared_execution_digest
        assert not hasattr(prepared, "command")
        assert "providerKey" not in repr(prepared)
        try:
            prepared.data["objective"] = "tampered"
        except TypeError:
            pass
        else:
            raise AssertionError("prepared data was mutable")
        assert first == prepared.prepared_execution_digest
    finally:
        runtime.close()


def test_atomic_admission_creates_driver_intent_before_dispatch(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        svc = RuntimeCommandService(runtime.store, "operator-x", "sess-1", runtime_service=runtime.service)
        payload = _approved_run_payload(svc, {"objective": "x", "targetRoot": "/tmp"}, "atomic")
        runner = _PreparedRunner(svc)
        svc.approved_hermes_runner = runner
        receipt = svc.execute(_envelope("run_approved_hermes_inspection", payload, key="atomic-run"))
        assert receipt["status"] == "accepted"
        approval = svc.store.require_state("human_approval-" + payload["approvalRequestId"])
        run = svc.store.require_state("driverrun-" + payload["driverRunId"])
        assert approval["state"] == "consumed"
        assert run["state"] == "created"
        assert runner.executed is runner.prepared  # same prepared object, no raw reconstruction
    finally:
        runtime.close()


def test_crash_after_admission_never_redispatches(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        svc = RuntimeCommandService(runtime.store, "operator-x", "sess-1", runtime_service=runtime.service)
        payload = _approved_run_payload(svc, {"objective": "x", "targetRoot": "/tmp"}, "crash")
        runner = _PreparedRunner(svc, execute_error=RuntimeError("simulated crash after admission"))
        svc.approved_hermes_runner = runner
        command = _envelope("run_approved_hermes_inspection", payload, key="crash-run")
        assert svc.execute(command)["status"] == "rejected"
        assert runner.execute_calls == 1
        replay = svc.execute(command)
        assert replay["status"] == "idempotent"
        assert runner.execute_calls == 1
        assert svc.store.require_state("human_approval-" + payload["approvalRequestId"])["state"] == "consumed"
        assert svc.store.require_state("driverrun-" + payload["driverRunId"])["state"] == "created"
    finally:
        runtime.close()


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
        runner = _PreparedRunner(svc)
        svc.approved_hermes_runner = runner
        payload = _approved_run_payload(
            svc, {"objective": "x", "targetRoot": "/tmp"}, "route"
        )
        cmd = _envelope(
            "run_approved_hermes_inspection", payload, key="route-run"
        )
        first = svc.execute(cmd)
        assert first["status"] == "accepted"
        assert first["result"]["missionId"] == "m-model-1"
        assert runner.executed is runner.prepared
        # Same idempotency key is idempotent at the one-use admission boundary.
        second = svc.execute(cmd)
        assert second["status"] == "idempotent"
        assert second["result"]["missionId"] == "m-model-1"
    finally:
        runtime.close()



def test_governed_hermes_in_progress_is_not_presented_as_accepted(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        svc = RuntimeCommandService(runtime.store, "operator-x", "sess-1", runtime_service=runtime.service)
        svc.approved_hermes_runner = _PreparedRunner(
            svc, result={"status": "in_progress", "commandId": "cmd-model-1"})
        payload = _approved_run_payload(
            svc, {"objective": "x", "targetRoot": "/tmp"}, "progress"
        )
        receipt = svc.execute(
            _envelope(
                "run_approved_hermes_inspection", payload, key="progress-run"
            )
        )
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


def test_invalid_context_preparation_does_not_consume_approval(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        svc = RuntimeCommandService(runtime.store, "operator-x", "sess-1", runtime_service=runtime.service)
        payload = _approved_run_payload(svc, {"objective": "x", "targetRoot": "/tmp"}, "invalid-context")
        svc.approved_hermes_runner = _PreparedRunner(svc, prepare_error=ValueError("MODEL_TASK_OBJECTIVE_OR_TARGET_MISSING"))
        receipt = svc.execute(_envelope("run_approved_hermes_inspection", payload, key="invalid-context-run"))
        assert receipt["status"] == "rejected"
        assert svc.store.require_state("human_approval-" + payload["approvalRequestId"])["state"] == "approved"
    finally:
        runtime.close()


def test_title_preparation_failure_does_not_consume_approval(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        svc = RuntimeCommandService(runtime.store, "operator-x", "sess-1", runtime_service=runtime.service)
        payload = _approved_run_payload(svc, {"objective": "x", "targetRoot": "/tmp"}, "title")
        svc.approved_hermes_runner = _PreparedRunner(svc, prepare_error=ValueError("MODEL_VISIBLE_PROMPT_TITLE_TOO_LONG"))
        receipt = svc.execute(_envelope("run_approved_hermes_inspection", payload, key="title-run"))
        assert receipt["status"] == "rejected"
        assert svc.store.require_state("human_approval-" + payload["approvalRequestId"])["state"] == "approved"
    finally:
        runtime.close()


def test_prepared_identity_is_admitted_then_same_object_is_dispatched(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        svc = RuntimeCommandService(runtime.store, "operator-x", "sess-1", runtime_service=runtime.service)
        payload = _approved_run_payload(svc, {"objective": "x", "targetRoot": "/tmp"}, "identity")
        runner = _PreparedRunner(svc)
        svc.approved_hermes_runner = runner
        receipt = svc.execute(_envelope("run_approved_hermes_inspection", payload, key="identity-run"))
        assert receipt["status"] == "accepted"
        assert runner.executed is runner.prepared
        assert runner.executed.approval_identity["driverRunId"] == payload["driverRunId"]
        assert svc.store.require_state("human_approval-" + payload["approvalRequestId"])["state"] == "consumed"
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
