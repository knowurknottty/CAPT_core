from pathlib import Path

import pytest

from capt_lab.contracts import LabEngineRequest, LabEngineResult
from capt_lab.registry import LabEngineDescriptor, LabEngineRegistry, LabOperationDescriptor, build_default_registry
from capt_lab.runtime import run_lab_advisory
from capt_runtime import commands
from capt_runtime.errors import IdempotencyConflict, IntegrityViolation
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore

NOW = "2026-08-18T16:00:00Z"


def meta(step, actor_kind="human", actor_id="operator-test"):
    return commands.command(
        command_id="cmd-" + step,
        idempotency_key="idem-" + step,
        operation_fingerprint=commands.fingerprint(step, {"step": step}),
        correlation_id="corr-lab",
        actor_id=actor_id,
        actor_kind=actor_kind,
        issued_at=NOW,
        replay_policy="never",
    )


def mission(mid="m-lab"):
    return {
        "schemaVersion": "1.0.0", "missionId": mid, "rawRequest": "lab test",
        "normalizedRequest": "lab test",
        "objectives": [{"objectiveId": "o-1", "statement": "Use a Lab advisory.", "priority": 1}],
        "constraints": [],
        "successCriteria": [{"criterionId": "s-1", "statement": "Evidence recorded.", "requiresVerification": True}],
        "terminationCriteria": [{"criterionId": "t-1", "statement": "Invariant failure.", "terminalState": "failed"}],
        "unresolvedAmbiguities": [], "taskGraphId": None, "createdAt": NOW,
    }


def task(tid="t-lab", mid="m-lab", state="pending"):
    return {
        "taskId": tid, "missionId": mid, "title": "Obtain specialist advisory",
        "state": state, "consequential": False, "capabilityRequirements": [],
        "assignedDriverId": None, "attempt": 0, "maxAttempts": 1, "recoveryState": "none",
    }


def command(payload=None, key="idem-lab-run", command_id="cmd-lab-run"):
    return {
        "commandId": command_id, "operatorId": "operator-test", "sessionId": "sess-test",
        "schemaVersion": "1.0.0", "correlationId": "corr-lab", "idempotencyKey": key,
        "timestamp": NOW, "op": "run_lab_engine_advisory",
        "payload": payload or {
            "engineId": "lab.math", "operation": "cyclotomic_summary",
            "input": {"conductor": 5}, "missionId": "m-lab", "taskId": "t-lab",
        },
    }


@pytest.fixture
def runtime(tmp_path):
    store = EventStore(str(tmp_path / "runtime.db"))
    svc = RuntimeService(store)
    svc.create_mission(mission(), meta("mission"))
    svc.create_task(task(), meta("task", "cognitive_plane", "cog-test"))
    yield store, svc, tmp_path / "lab-staging"
    store.close()


def test_success_records_unverified_observation_without_task_promotion(runtime):
    store, svc, staging = runtime
    before_task = store.require_state("task-t-lab")["state"]
    receipt = run_lab_advisory(store, svc, build_default_registry(), staging, command())
    assert receipt["verificationId"] is None
    assert receipt["promotionState"] == "proposed"
    assert receipt["epistemicClass"] == "calculation"
    assert store.require_state("driverrun-" + receipt["driverRunId"])["state"] == "completed"
    claim = store.require_state("claim-" + receipt["claimId"])
    assert claim["kind"] == "observation"
    assert claim["promotionState"] == "proposed"
    assert claim["verificationId"] is None
    assert receipt["evidenceId"] in claim["evidenceIds"]
    assert store.require_state("task-t-lab")["state"] == before_task
    assert Path(receipt["artifactPath"]).is_file()
    assert Path(receipt["artifactPath"]).read_bytes()

    event_types = [e["eventType"] for e in store.read_events(0)]
    assert "ClaimVerified" not in event_types
    assert "ClaimGuardDecided" not in event_types
    assert not any(e.get("payload", {}).get("toState") == "succeeded" for e in store.read_events(0))


def test_replay_same_key_same_payload_does_not_rerun_engine(runtime):
    store, svc, staging = runtime
    calls = {"count": 0}
    registry = LabEngineRegistry()
    descriptor = LabEngineDescriptor(
        engine_id="lab.test", engine_version="0.1.0", display_name="Test",
        description="counting test engine",
        operations=(LabOperationDescriptor("inspect", "advisory", "inspect"),),
        provenance={"donorRepository": "test/repo", "donorCommit": "abc123", "sourceFiles": []},
    )
    def engine(req, context):
        calls["count"] += 1
        return LabEngineResult("lab.test", "0.1.0", "inspect", "advisory", {"call": calls["count"]})
    registry.register(descriptor, engine)
    payload = {"engineId":"lab.test","operation":"inspect","input":{},"missionId":"m-lab","taskId":"t-lab"}
    first = run_lab_advisory(store, svc, registry, staging, command(payload))
    second = run_lab_advisory(store, svc, registry, staging, command(payload))
    assert calls["count"] == 1
    assert second["_idempotent"] is True
    assert second["artifactDigest"] == first["artifactDigest"]


def test_same_key_different_payload_is_idempotency_collision(runtime):
    store, svc, staging = runtime
    run_lab_advisory(store, svc, build_default_registry(), staging, command())
    changed = command({
        "engineId":"lab.math","operation":"cyclotomic_summary","input":{"conductor":7},
        "missionId":"m-lab","taskId":"t-lab",
    })
    with pytest.raises(IdempotencyConflict):
        run_lab_advisory(store, svc, build_default_registry(), staging, changed)


def test_mission_task_spoof_rejected_before_driver_run(runtime):
    store, svc, staging = runtime
    svc.create_mission(mission("m-other"), meta("mission-other"))
    bad = command({
        "engineId":"lab.math","operation":"cyclotomic_summary","input":{"conductor":5},
        "missionId":"m-other","taskId":"t-lab",
    }, key="idem-spoof", command_id="cmd-spoof")
    with pytest.raises(Exception, match="mission|task"):
        run_lab_advisory(store, svc, build_default_registry(), staging, bad)
    assert not [s for s in store.all_aggregates() if s[1] == "driverrun"]


def test_terminal_task_rejected_before_driver_run(tmp_path):
    store = EventStore(str(tmp_path / "runtime.db")); svc = RuntimeService(store)
    svc.create_mission(mission(), meta("mission-terminal"))
    svc.create_task(task(state="pending"), meta("task-terminal", "cognitive_plane", "cog-test"))
    svc.transition_task("t-lab", "cancelled", "test", meta("cancel-terminal", "execution_plane", "exec-test"))
    try:
        with pytest.raises(Exception, match="terminal"):
            run_lab_advisory(store, svc, build_default_registry(), tmp_path / "staging", command(key="idem-terminal"))
        assert not [s for s in store.all_aggregates() if s[1] == "driverrun"]
    finally:
        store.close()


def test_engine_failure_marks_driver_failed_and_fabricates_no_claim_or_evidence(runtime):
    store, svc, staging = runtime
    registry = LabEngineRegistry()
    descriptor = LabEngineDescriptor(
        engine_id="lab.fail", engine_version="0.1.0", display_name="Fail",
        description="failing engine",
        operations=(LabOperationDescriptor("explode", "advisory", "explode"),),
        provenance={"donorRepository":"test/repo","donorCommit":"abc","sourceFiles":[]},
    )
    def explode(req, context):
        raise RuntimeError("boom")
    registry.register(descriptor, explode)
    payload={"engineId":"lab.fail","operation":"explode","input":{},"missionId":"m-lab","taskId":"t-lab"}
    with pytest.raises(RuntimeError, match="boom"):
        run_lab_advisory(store, svc, registry, staging, command(payload, key="idem-fail", command_id="cmd-fail"))
    runs=[store.require_state(s[0]) for s in store.all_aggregates() if s[1]=="driverrun"]
    assert len(runs) == 1 and runs[0]["state"] == "failed"
    assert not [s for s in store.all_aggregates() if s[1] == "claim"]


def test_artifact_tamper_fails_closed_before_evidence(runtime):
    store, svc, staging = runtime
    def tamper(path: Path):
        path.write_text("tampered", encoding="utf-8")
    with pytest.raises(IntegrityViolation, match="artifact"):
        run_lab_advisory(store, svc, build_default_registry(), staging, command(key="idem-tamper", command_id="cmd-tamper"), post_write_hook=tamper)
    runs=[store.require_state(s[0]) for s in store.all_aggregates() if s[1]=="driverrun"]
    assert len(runs) == 1 and runs[0]["state"] == "failed"
    assert not [s for s in store.all_aggregates() if s[1] == "claim"]


def test_query_service_exposes_live_lab_registry_and_capability(tmp_path):
    from desktop.capt_runtime_service import RuntimeQueryService
    store = EventStore(str(tmp_path / "runtime.db"))
    try:
        query = RuntimeQueryService(store, lab_registry=build_default_registry())
        response = query.handle({"op": "lab_engines"})
        assert response["ok"] is True
        assert {item["engineId"] for item in response["result"]} == {
            "lab.math", "lab.analogy", "lab.consensus", "lab.forge"
        }
        caps = query.handle({"op": "capabilities"})["result"]
        assert "lab_engines" in caps["queryOperations"]
        assert "run_lab_engine_advisory" in caps["commandOperations"]
        assert caps["runtimeComponents"]["labEngines"] is True
    finally:
        store.close()


def test_command_service_routes_lab_advisory_and_preserves_duplicate_status(runtime):
    from desktop.m1_command_service import RuntimeCommandService
    store, svc, staging = runtime
    service = RuntimeCommandService(store, "operator-test", "sess-test", runtime_service=svc)
    registry = build_default_registry()
    service.lab_runner = lambda cmd: run_lab_advisory(store, svc, registry, staging, cmd)
    first = service.execute(command())
    second = service.execute(command())
    assert first["status"] == "accepted"
    assert first["classification"] == "accepted"
    assert first["result"]["promotionState"] == "proposed"
    assert second["status"] == "idempotent"
    assert second["classification"] == "duplicate"
    assert second["result"]["artifactDigest"] == first["result"]["artifactDigest"]
