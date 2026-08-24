from __future__ import annotations

import json
from pathlib import Path

from capt_runtime import commands, contracts
from capt_runtime.composition import create_runtime
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
        "targetIdentity": str(root),
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
