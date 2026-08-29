from __future__ import annotations

from pathlib import Path

import pytest

from capt_runtime import commands, contracts
from capt_runtime.composition import create_runtime
from capt_runtime.errors import CapabilityDenied
from capt_runtime.tool_broker import tool_request_fingerprint
from desktop.m1_command_service import RuntimeCommandService

NOW = "2026-08-19T14:15:00Z"


def _meta(step: str, actor_kind: str, actor_id: str) -> dict:
    return commands.command(
        command_id=f"cmd-{step}",
        idempotency_key=f"idem-{step}",
        operation_fingerprint=commands.fingerprint(step, {"step": step}),
        correlation_id="corr-tool-wiring",
        actor_id=actor_id,
        actor_kind=actor_kind,
        issued_at=NOW,
        replay_policy="never",
    )


def _seed_authority(runtime, root: Path, operation: str, *, suffix: str = "x", max_uses: int = 4):
    mission_id = f"m-tool-{suffix}"
    task_id = f"t-tool-{suffix}"
    policy_id = f"pd-tool-{suffix}"
    grant_id = f"g-tool-{suffix}"
    lease_id = f"l-tool-{suffix}"
    runtime.service.create_mission(
        {
            "schemaVersion": "1.0.0",
            "missionId": mission_id,
            "rawRequest": "governed tool integration test",
            "normalizedRequest": "governed tool integration test",
            "objectives": [{"objectiveId": "obj-1", "statement": "run governed tool", "priority": 1}],
            "constraints": [{
                "kind": "resource_boundary", "constraintId": "con-1", "origin": "explicit_user",
                "scope": {"kind": "filesystem", "rootPath": str(root), "recursive": True},
            }],
            "successCriteria": [{"criterionId": "sc-1", "statement": "tool result recorded", "requiresVerification": True}],
            "terminationCriteria": [{"criterionId": "tc-1", "statement": "invariant violation", "terminalState": "failed"}],
            "unresolvedAmbiguities": [],
            "taskGraphId": None,
            "createdAt": NOW,
        },
        _meta(f"mission-{suffix}", "human", "operator-test"),
    )
    runtime.service.evaluate_policy(
        {
            "schemaVersion": "1.0.0",
            "policyDecisionId": policy_id,
            "policyBundleDigest": contracts.digest({"policy": "tool-wiring", "suffix": suffix}),
            "effect": "allow",
            "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
            "missionId": mission_id,
            "taskId": task_id,
            "requestedOperations": [operation],
            "requestedScope": {"kind": "filesystem", "rootPath": str(root), "recursive": True},
            "conditions": [],
            "rationale": "bounded integration authority",
            "decidedBy": {"actorId": "gk-1", "kind": "governance_kernel"},
            "decidedAt": NOW,
        },
        _meta(f"policy-{suffix}", "governance_kernel", "gk-1"),
    )
    runtime.service.issue_grant(
        {
            "schemaVersion": "1.0.0",
            "grantId": grant_id,
            "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
            "capabilityId": f"cap.{operation}",
            "operations": [operation],
            "scope": {"kind": "filesystem", "rootPath": str(root), "recursive": True},
            "policyDecisionId": policy_id,
            "policyBundleDigest": contracts.digest({"policy": "tool-wiring", "suffix": suffix}),
            "conditions": [],
            "maxUses": max_uses,
            "validFrom": "2026-08-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "issuedBy": {"actorId": "gk-1", "kind": "governance_kernel"},
            "issuedAt": NOW,
        },
        _meta(f"grant-{suffix}", "governance_kernel", "gk-1"),
    )
    runtime.service.activate_lease(
        {
            "schemaVersion": "1.0.0",
            "leaseId": lease_id,
            "grantId": grant_id,
            "missionId": mission_id,
            "taskId": task_id,
            "executionContextId": f"ec-tool-{suffix}",
            "operations": [operation],
            "scope": {"kind": "filesystem", "rootPath": str(root), "recursive": True},
            "maxUses": max_uses,
            "validFrom": "2026-08-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "activatedAt": NOW,
        },
        _meta(f"lease-{suffix}", "governance_kernel", "gk-1"),
    )
    return grant_id, lease_id


def _tool_request(
    *, root: Path, tool_id: str, operation: str, arguments: list[dict],
    grant_id: str, lease_id: str, idem: str, consequential: bool,
    target_identity: str | None = None,
) -> dict:
    request = {
        "schemaVersion": "1.0.0",
        "toolRequestId": "req-" + idem,
        "toolId": tool_id,
        "operation": operation,
        "arguments": arguments,
        "consequential": consequential,
        "grantId": grant_id,
        "leaseId": lease_id,
        "reservationId": None,
        "backendId": "local",
        "targetIdentity": target_identity or str(root),
        "filesystemScope": str(root),
        "idempotencyKey": idem,
        "operationFingerprint": "sha256:" + "0" * 64,
        "replayPolicy": "never",
        "requestedAt": NOW,
    }
    request["operationFingerprint"] = tool_request_fingerprint(request)
    return request


def _envelope(request: dict, *, session: str = "sess-test", command_id: str = "cmd-run-tool", outer_idem: str | None = None) -> dict:
    return {
        "commandId": command_id,
        "operatorId": "operator-test",
        "sessionId": session,
        "schemaVersion": "1.0.0",
        "correlationId": "corr-run-tool",
        "idempotencyKey": outer_idem or request["idempotencyKey"],
        "timestamp": NOW,
        "op": "run_tool",
        "payload": request,
    }


def test_runtime_composition_owns_slice_a_registry_and_broker(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        assert [d["toolId"] for d in runtime.tool_registry.list_descriptors()] == [
            "code.execution", "file.operations", "terminal.docker", "terminal.local", "terminal.ssh"
        ]
        assert all(
            runtime.tool_registry.readiness(tool_id)["status"] == "available"
            for tool_id in ("terminal.local", "file.operations", "code.execution")
        )
        ssh_readiness = runtime.tool_registry.readiness("terminal.ssh")
        assert ssh_readiness["status"] == "unavailable"
        assert "no named SSH profiles" in ssh_readiness["reason"]
        docker_readiness = runtime.tool_registry.readiness("terminal.docker")
        assert docker_readiness["status"] == "unavailable"
        assert "no named Docker profiles" in docker_readiness["reason"]
        relay = runtime.command_service("operator-test", "sess-test")
        assert relay.tool_broker is runtime.tool_broker
    finally:
        runtime.close()


def test_authenticated_run_tool_executes_real_file_read(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        target = tmp_path / "hello.txt"
        target.write_text("CAPT_TOOL_OK")
        grant, lease = _seed_authority(runtime, tmp_path, "file.read", suffix="read")
        request = _tool_request(
            root=tmp_path, tool_id="file.operations", operation="file.read",
            arguments=[{"kind": "path", "name": "path", "value": str(target)}],
            grant_id=grant, lease_id=lease, idem="tool-read-1", consequential=False,
        )
        receipt = runtime.command_service("operator-test", "sess-test").execute(_envelope(request))
        assert receipt["status"] == "accepted"
        assert receipt["classification"] == "accepted"
        assert receipt["result"]["status"] == "succeeded"
        content = next(x["value"] for x in receipt["result"]["result"]["output"] if x["name"] == "content")
        assert content == "CAPT_TOOL_OK"
        execution = runtime.store.require_state("tool_execution-" + receipt["result"]["toolExecutionId"])
        assert execution["operatorId"] == "operator-test"
        assert execution["sessionId"] == "sess-test"
    finally:
        runtime.close()


def test_settled_replay_is_zero_redispatch_and_same_session_only(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        marker = tmp_path / "count.txt"
        grant, lease = _seed_authority(runtime, tmp_path, "code.execute_python", suffix="replay", max_uses=1)
        code = "from pathlib import Path; p=Path('count.txt'); p.write_text(p.read_text()+'x' if p.exists() else 'x')"
        request = _tool_request(
            root=tmp_path, tool_id="code.execution", operation="code.execute_python",
            arguments=[
                {"kind": "string", "name": "code", "value": code},
                {"kind": "path", "name": "cwd", "value": str(tmp_path)},
            ],
            grant_id=grant, lease_id=lease, idem="tool-code-replay", consequential=True,
        )
        relay = runtime.command_service("operator-test", "sess-test")
        first = relay.execute(_envelope(request, command_id="cmd-code-first"))
        second = relay.execute(_envelope(request, command_id="cmd-code-first"))
        assert first["status"] == "accepted"
        assert second["status"] == "idempotent"
        assert second["result"]["replayed"] is True
        assert marker.read_text() == "x"

        cross = runtime.command_service("operator-test", "sess-other").execute(
            _envelope(request, session="sess-other", command_id="cmd-code-cross")
        )
        assert cross["status"] == "rejected"
        assert cross["classification"] == "authority"
        assert marker.read_text() == "x"
    finally:
        runtime.close()


def test_run_tool_requires_outer_and_inner_idempotency_binding(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        target = tmp_path / "hello.txt"
        target.write_text("x")
        grant, lease = _seed_authority(runtime, tmp_path, "file.read", suffix="idem")
        request = _tool_request(
            root=tmp_path, tool_id="file.operations", operation="file.read",
            arguments=[{"kind": "path", "name": "path", "value": str(target)}],
            grant_id=grant, lease_id=lease, idem="inner-idem", consequential=False,
        )
        receipt = runtime.command_service("operator-test", "sess-test").execute(
            _envelope(request, outer_idem="different-outer-idem")
        )
        assert receipt["status"] == "rejected"
        assert receipt["classification"] == "authority"
        assert runtime.store.aggregate_version("tool_execution-" + runtime.tool_broker.execution_id("inner-idem")) == 0
    finally:
        runtime.close()


def test_run_tool_fails_closed_when_broker_is_not_wired(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        relay = RuntimeCommandService(
            runtime.store, "operator-test", "sess-test",
            runtime_service=runtime.service, tool_broker=None,
        )
        payload = {
            "schemaVersion": "1.0.0", "toolRequestId": "req-none", "toolId": "file.operations",
            "operation": "file.read", "arguments": [], "consequential": False,
            "grantId": "g-none", "leaseId": "l-none", "reservationId": None,
            "backendId": "local", "targetIdentity": str(tmp_path), "filesystemScope": str(tmp_path),
            "idempotencyKey": "tool-none", "operationFingerprint": "sha256:" + "0"*64,
            "replayPolicy": "never", "requestedAt": NOW,
        }
        receipt = relay.execute(_envelope(payload, outer_idem="tool-none"))
        assert receipt["status"] == "rejected"
        assert receipt["classification"] == "internal"
        assert receipt["error"]["code"] == "TOOL_BROKER_UNAVAILABLE"
    finally:
        runtime.close()


def test_world_receipt_crash_after_reservation_before_admission_is_reconciled(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        target = tmp_path / "state.txt"
        target.write_text("before", encoding="utf-8")
        grant, lease = _seed_authority(
            runtime, tmp_path, "file.write", suffix="wr-reserve-gap", max_uses=1
        )
        request = _tool_request(
            root=tmp_path,
            tool_id="file.operations",
            operation="file.write",
            arguments=[
                {"kind": "path", "name": "path", "value": str(target)},
                {"kind": "string", "name": "content", "value": "after"},
            ],
            grant_id=grant,
            lease_id=lease,
            idem="wr-reserve-gap",
            consequential=True,
            target_identity=str(target),
        )
        original_transition = runtime.service.transition_tool_execution

        def crash_before_admitted(execution_id, to_state, patch, metadata):
            if to_state == "admitted":
                raise SystemExit("simulated crash after reservation")
            return original_transition(execution_id, to_state, patch, metadata)

        runtime.service.transition_tool_execution = crash_before_admitted
        with pytest.raises(SystemExit, match="after reservation"):
            runtime.tool_broker.execute(
                request, operator_id="operator-test", session_id="sess-test"
            )
        runtime.service.transition_tool_execution = original_transition

        execution_id = runtime.tool_broker.execution_id(request["idempotencyKey"])
        stranded = runtime.store.require_state("tool_execution-" + execution_id)
        capability = runtime.store.require_state("capability-" + grant)
        assert stranded["state"] == "prepared"
        assert stranded["reservationId"] is None
        assert len([r for r in capability["reservations"] if r["state"] == "open"]) == 1
        assert target.read_text(encoding="utf-8") == "before"

        recovered = runtime.tool_broker.reconcile_stranded()
        recovered_state = next(x for x in recovered if x["toolExecutionId"] == execution_id)
        capability = runtime.store.require_state("capability-" + grant)
        assert recovered_state["state"] == "failed"
        assert recovered_state["reservationId"] is not None
        assert capability["usesConsumed"] == 0
        assert not [r for r in capability["reservations"] if r["state"] == "open"]
        assert target.read_text(encoding="utf-8") == "before"
    finally:
        runtime.close()


def test_authenticated_file_write_uses_lease_bound_staged_world_receipt(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        target = tmp_path / "world.txt"
        target.write_text("before", encoding="utf-8")
        grant, lease = _seed_authority(
            runtime, tmp_path, "file.write", suffix="world-write", max_uses=1
        )
        request = _tool_request(
            root=tmp_path,
            tool_id="file.operations",
            operation="file.write",
            arguments=[
                {"kind": "path", "name": "path", "value": str(target)},
                {"kind": "string", "name": "content", "value": "after"},
            ],
            grant_id=grant,
            lease_id=lease,
            idem="world-write",
            consequential=True,
            target_identity=str(target),
        )
        receipt = runtime.command_service("operator-test", "sess-test").execute(
            _envelope(request, command_id="cmd-world-write")
        )
        assert receipt["status"] == "accepted"
        execution = runtime.store.require_state(
            "tool_execution-" + receipt["result"]["toolExecutionId"]
        )
        assert execution["state"] == "completed"
        assert execution["effectIntent"]["expiresAt"] == "2030-01-01T00:00:00Z"
        assert execution["effectIntent"]["coordinationMode"] == "staged"
        assert execution["effectIntent"]["rollbackStrategy"] == "escrow"
        assert execution["worldReceipt"]["commitState"] == "committed"
        assert Path(execution["effectIntent"]["reversalHandle"]).read_text() == "before"
        assert target.read_text() == "after"
        capability = runtime.store.require_state("capability-" + grant)
        assert capability["usesConsumed"] == 1
    finally:
        runtime.close()


def test_expired_admitted_world_receipt_closes_reservation_without_dispatch(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        target = tmp_path / "expired-admitted.txt"
        target.write_text("before", encoding="utf-8")
        grant, lease = _seed_authority(
            runtime, tmp_path, "file.write", suffix="wr-expired-admitted", max_uses=1
        )
        request = _tool_request(
            root=tmp_path,
            tool_id="file.operations",
            operation="file.write",
            arguments=[
                {"kind": "path", "name": "path", "value": str(target)},
                {"kind": "string", "name": "content", "value": "after"},
            ],
            grant_id=grant,
            lease_id=lease,
            idem="wr-expired-admitted",
            consequential=True,
            target_identity=str(target),
        )
        broker = runtime.tool_broker
        execution = broker.build_execution(
            request, operator_id="operator-test", session_id="sess-test"
        )
        runtime.service.prepare_tool_execution(
            execution, broker.metadata(execution["toolExecutionId"], "prepared")
        )
        reservation = broker._reservation(request, execution["toolExecutionId"])
        runtime.service.reserve_use(
            grant, reservation,
            broker.metadata(execution["toolExecutionId"], "reserve-capability"),
        )
        runtime.service.transition_tool_execution(
            execution["toolExecutionId"], "admitted",
            {"reservationId": reservation["reservationId"]},
            broker.metadata(execution["toolExecutionId"], "admitted"),
        )

        original_now = broker._now
        broker._now = lambda: "2030-01-01T00:00:00Z"
        try:
            result = broker.execute(
                request, operator_id="operator-test", session_id="sess-test"
            )
        finally:
            broker._now = original_now

        assert result["status"] == "denied"
        state = runtime.store.require_state(
            "tool_execution-" + execution["toolExecutionId"]
        )
        capability = runtime.store.require_state("capability-" + grant)
        assert state["state"] == "failed"
        assert state["dispatchBoundary"] == "not_started"
        assert state["reservationId"] == reservation["reservationId"]
        assert capability["usesConsumed"] == 0
        stored_reservation = next(
            r for r in capability["reservations"]
            if r["reservationId"] == reservation["reservationId"]
        )
        assert stored_reservation["state"] == "finalized"
        assert target.read_text(encoding="utf-8") == "before"
    finally:
        runtime.close()


def test_predispatch_settlement_atomically_finalizes_reservation_and_execution(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        target = tmp_path / "atomic-settle.txt"
        target.write_text("before", encoding="utf-8")
        grant, lease = _seed_authority(runtime, tmp_path, "file.write", suffix="wr-atomic", max_uses=1)
        request = _tool_request(
            root=tmp_path, tool_id="file.operations", operation="file.write",
            arguments=[
                {"kind": "path", "name": "path", "value": str(target)},
                {"kind": "string", "name": "content", "value": "after"},
            ],
            grant_id=grant, lease_id=lease, idem="wr-atomic", consequential=True,
            target_identity=str(target),
        )
        broker = runtime.tool_broker
        execution = broker.build_execution(request, operator_id="operator-test", session_id="sess-test")
        runtime.service.prepare_tool_execution(execution, broker.metadata(execution["toolExecutionId"], "prepared"))
        reservation = broker._reservation(request, execution["toolExecutionId"])
        runtime.service.reserve_use(grant, reservation, broker.metadata(execution["toolExecutionId"], "reserve-capability"))
        runtime.service.transition_tool_execution(
            execution["toolExecutionId"], "admitted", {"reservationId": reservation["reservationId"]},
            broker.metadata(execution["toolExecutionId"], "admitted"),
        )
        denied = broker._denied_result(request, "WORLD_RECEIPT_EFFECT_INTENT_EXPIRED")
        consumption = broker._consumption(
            execution["toolExecutionId"], reservation["reservationId"], lease, "failed", None
        )
        settlement_meta = broker.metadata(execution["toolExecutionId"], "predispatch-settle")
        runtime.service.settle_predispatch_tool_execution(
            grant, consumption, execution["toolExecutionId"], denied, settlement_meta,
        )
        replayed = runtime.service.settle_predispatch_tool_execution(
            grant, consumption, execution["toolExecutionId"], denied, settlement_meta,
        )
        assert replayed["status"] == "idempotent"
        assert replayed["replayed"] is True

        state = runtime.store.require_state("tool_execution-" + execution["toolExecutionId"])
        capability = runtime.store.require_state("capability-" + grant)
        stored = next(r for r in capability["reservations"] if r["reservationId"] == reservation["reservationId"])
        assert state["state"] == "failed"
        assert state["settlementStatus"] == "settled"
        assert state["reservationId"] == reservation["reservationId"]
        assert state["result"]["status"] == "denied"
        assert stored["state"] == "finalized"
        assert capability["usesConsumed"] == 0
        assert target.read_text(encoding="utf-8") == "before"
        events = runtime.store.read_events()
        assert events[-2]["payload"]["eventType"] == "CapabilityUseFinalized"
        assert events[-1]["payload"]["eventType"] == "ToolExecutionTerminated"
        assert events[-1]["globalSequence"] == events[-2]["globalSequence"] + 1
    finally:
        runtime.close()


def test_predispatch_denial_survives_postcommit_dispatch_fault_without_later_effect(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        target = tmp_path / "dispatch-fault.txt"
        target.write_text("before", encoding="utf-8")
        grant, lease = _seed_authority(runtime, tmp_path, "file.write", suffix="wr-dispatch-fault", max_uses=1)
        request = _tool_request(
            root=tmp_path, tool_id="file.operations", operation="file.write",
            arguments=[
                {"kind": "path", "name": "path", "value": str(target)},
                {"kind": "string", "name": "content", "value": "after"},
            ],
            grant_id=grant, lease_id=lease, idem="wr-dispatch-fault", consequential=True,
            target_identity=str(target),
        )
        broker = runtime.tool_broker
        execution = broker.build_execution(request, operator_id="operator-test", session_id="sess-test")
        runtime.service.prepare_tool_execution(execution, broker.metadata(execution["toolExecutionId"], "prepared"))
        reservation = broker._reservation(request, execution["toolExecutionId"])
        runtime.service.reserve_use(grant, reservation, broker.metadata(execution["toolExecutionId"], "reserve-capability"))
        runtime.service.transition_tool_execution(
            execution["toolExecutionId"], "admitted", {"reservationId": reservation["reservationId"]},
            broker.metadata(execution["toolExecutionId"], "admitted"),
        )
        original_check = runtime.service.check_lease
        checks = {"count": 0}

        def deny_once(*args, **kwargs):
            checks["count"] += 1
            if checks["count"] == 1:
                raise CapabilityDenied("transient pre-dispatch denial", lease)
            return original_check(*args, **kwargs)

        runtime.service.check_lease = deny_once
        delivery = {"raised": False}

        def fail_first_delivery(_event):
            if not delivery["raised"]:
                delivery["raised"] = True
                raise RuntimeError("simulated crash after atomic commit")

        runtime.store.subscribe(fail_first_delivery)
        with pytest.raises(RuntimeError, match="after atomic commit"):
            broker.execute(request, operator_id="operator-test", session_id="sess-test")

        committed = runtime.store.require_state("tool_execution-" + execution["toolExecutionId"])
        capability = runtime.store.require_state("capability-" + grant)
        stored = next(r for r in capability["reservations"] if r["reservationId"] == reservation["reservationId"])
        assert committed["state"] == "failed"
        assert committed["reservationId"] == reservation["reservationId"]
        assert stored["state"] == "finalized"
        assert capability["usesConsumed"] == 0
        assert target.read_text(encoding="utf-8") == "before"

        replay = broker.execute(request, operator_id="operator-test", session_id="sess-test")
        assert replay["replayed"] is True
        assert replay["state"] == "failed"
        assert target.read_text(encoding="utf-8") == "before"
        assert checks["count"] == 1
    finally:
        runtime.close()


def test_recovery_predispatch_settlement_survives_postcommit_dispatch_fault(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        target = tmp_path / "recover-dispatch-fault.txt"
        target.write_text("before", encoding="utf-8")
        grant, lease = _seed_authority(runtime, tmp_path, "file.write", suffix="wr-recover-fault", max_uses=1)
        request = _tool_request(
            root=tmp_path, tool_id="file.operations", operation="file.write",
            arguments=[
                {"kind": "path", "name": "path", "value": str(target)},
                {"kind": "string", "name": "content", "value": "after"},
            ],
            grant_id=grant, lease_id=lease, idem="wr-recover-fault", consequential=True,
            target_identity=str(target),
        )
        broker = runtime.tool_broker
        execution = broker.build_execution(request, operator_id="operator-test", session_id="sess-test")
        runtime.service.prepare_tool_execution(execution, broker.metadata(execution["toolExecutionId"], "prepared"))
        reservation = broker._reservation(request, execution["toolExecutionId"])
        runtime.service.reserve_use(grant, reservation, broker.metadata(execution["toolExecutionId"], "reserve-capability"))

        delivery = {"raised": False}
        def fail_first_delivery(_event):
            if not delivery["raised"]:
                delivery["raised"] = True
                raise RuntimeError("simulated recovery crash after atomic commit")
        runtime.store.subscribe(fail_first_delivery)
        with pytest.raises(RuntimeError, match="recovery crash after atomic commit"):
            broker.reconcile_stranded()

        state = runtime.store.require_state("tool_execution-" + execution["toolExecutionId"])
        capability = runtime.store.require_state("capability-" + grant)
        stored = next(r for r in capability["reservations"] if r["reservationId"] == reservation["reservationId"])
        assert state["state"] == "failed"
        assert state["reservationId"] == reservation["reservationId"]
        assert stored["state"] == "finalized"
        assert capability["usesConsumed"] == 0
        assert target.read_text(encoding="utf-8") == "before"

        recovered = broker.reconcile_stranded()
        assert recovered == []
        assert target.read_text(encoding="utf-8") == "before"
    finally:
        runtime.close()


def test_predispatch_atomic_settlement_rolls_back_when_commit_never_starts(tmp_path: Path, monkeypatch) -> None:
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        target = tmp_path / "before-commit-fault.txt"
        target.write_text("before", encoding="utf-8")
        grant, lease = _seed_authority(runtime, tmp_path, "file.write", suffix="wr-before-commit", max_uses=1)
        request = _tool_request(
            root=tmp_path, tool_id="file.operations", operation="file.write",
            arguments=[
                {"kind": "path", "name": "path", "value": str(target)},
                {"kind": "string", "name": "content", "value": "after"},
            ],
            grant_id=grant, lease_id=lease, idem="wr-before-commit", consequential=True,
            target_identity=str(target),
        )
        broker = runtime.tool_broker
        execution = broker.build_execution(request, operator_id="operator-test", session_id="sess-test")
        runtime.service.prepare_tool_execution(execution, broker.metadata(execution["toolExecutionId"], "prepared"))
        reservation = broker._reservation(request, execution["toolExecutionId"])
        runtime.service.reserve_use(grant, reservation, broker.metadata(execution["toolExecutionId"], "reserve-capability"))
        runtime.service.transition_tool_execution(
            execution["toolExecutionId"], "admitted", {"reservationId": reservation["reservationId"]},
            broker.metadata(execution["toolExecutionId"], "admitted"),
        )
        denied = broker._denied_result(request, "synthetic pre-commit denial")
        consumption = broker._consumption(
            execution["toolExecutionId"], reservation["reservationId"], lease, "failed", None
        )
        head_before = runtime.store.head_sequence()

        def fail_commit(*_args, **_kwargs):
            raise RuntimeError("simulated failure before commit")

        monkeypatch.setattr(runtime.store, "commit_command", fail_commit)
        with pytest.raises(RuntimeError, match="before commit"):
            runtime.service.settle_predispatch_tool_execution(
                grant, consumption, execution["toolExecutionId"], denied,
                broker.metadata(execution["toolExecutionId"], "predispatch-before-commit"),
            )

        state = runtime.store.require_state("tool_execution-" + execution["toolExecutionId"])
        capability = runtime.store.require_state("capability-" + grant)
        stored = next(r for r in capability["reservations"] if r["reservationId"] == reservation["reservationId"])
        assert state["state"] == "admitted"
        assert stored["state"] == "open"
        assert capability["usesConsumed"] == 0
        assert runtime.store.head_sequence() == head_before
        assert target.read_text(encoding="utf-8") == "before"
    finally:
        runtime.close()


def test_predispatch_atomic_settlement_rolls_back_after_first_append_is_staged(tmp_path: Path, monkeypatch) -> None:
    import capt_runtime.store as store_module

    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        target = tmp_path / "mid-transaction-fault.txt"
        target.write_text("before", encoding="utf-8")
        grant, lease = _seed_authority(runtime, tmp_path, "file.write", suffix="wr-mid-transaction", max_uses=1)
        request = _tool_request(
            root=tmp_path, tool_id="file.operations", operation="file.write",
            arguments=[
                {"kind": "path", "name": "path", "value": str(target)},
                {"kind": "string", "name": "content", "value": "after"},
            ],
            grant_id=grant, lease_id=lease, idem="wr-mid-transaction", consequential=True,
            target_identity=str(target),
        )
        broker = runtime.tool_broker
        execution = broker.build_execution(request, operator_id="operator-test", session_id="sess-test")
        runtime.service.prepare_tool_execution(execution, broker.metadata(execution["toolExecutionId"], "prepared"))
        reservation = broker._reservation(request, execution["toolExecutionId"])
        runtime.service.reserve_use(grant, reservation, broker.metadata(execution["toolExecutionId"], "reserve-capability"))
        runtime.service.transition_tool_execution(
            execution["toolExecutionId"], "admitted", {"reservationId": reservation["reservationId"]},
            broker.metadata(execution["toolExecutionId"], "admitted"),
        )
        denied = broker._denied_result(request, "synthetic mid-transaction denial")
        consumption = broker._consumption(
            execution["toolExecutionId"], reservation["reservationId"], lease, "failed", None
        )
        head_before = runtime.store.head_sequence()
        real_require = store_module.require

        def fail_second_append(type_name, value):
            if type_name == "EventEnvelope" and value.get("eventType") == "ToolExecutionTerminated":
                raise RuntimeError("simulated failure after first append staged")
            return real_require(type_name, value)

        monkeypatch.setattr(store_module, "require", fail_second_append)
        with pytest.raises(RuntimeError, match="after first append staged"):
            runtime.service.settle_predispatch_tool_execution(
                grant, consumption, execution["toolExecutionId"], denied,
                broker.metadata(execution["toolExecutionId"], "predispatch-mid-transaction"),
            )

        state = runtime.store.require_state("tool_execution-" + execution["toolExecutionId"])
        capability = runtime.store.require_state("capability-" + grant)
        stored = next(r for r in capability["reservations"] if r["reservationId"] == reservation["reservationId"])
        assert state["state"] == "admitted"
        assert stored["state"] == "open"
        assert capability["usesConsumed"] == 0
        assert runtime.store.head_sequence() == head_before
        assert target.read_text(encoding="utf-8") == "before"
    finally:
        runtime.close()
