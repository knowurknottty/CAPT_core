from __future__ import annotations

from pathlib import Path

import pytest

from capt_runtime import commands, contracts
from capt_runtime.composition import create_runtime
from capt_runtime.errors import AuthorityViolation
from capt_runtime.model_authority import normalize_model_authority
from capt_runtime.model_tool_bridge import ModelToolBridge

NOW = "2026-09-07T06:00:00Z"


def _meta(step: str, *, actor: str = "gk-1", kind: str = "governance_kernel"):
    return commands.command(
        command_id="cmd-" + step,
        idempotency_key="idem-" + step,
        operation_fingerprint=commands.fingerprint(step, {"step": step}),
        correlation_id="corr-model-tools",
        actor_id=actor,
        actor_kind=kind,
        issued_at=NOW,
        replay_policy="never",
    )


def _authority(runtime, root: Path, operations: list[str]):
    mission_id, task_id = "m-model-tools", "t-model-tools"
    policy_id, grant_id, lease_id = "pd-model-tools", "g-model-tools", "l-model-tools"
    runtime.service.create_mission(
        {
            "schemaVersion": "1.0.0",
            "missionId": mission_id,
            "rawRequest": "model tool bridge test",
            "normalizedRequest": "model tool bridge test",
            "objectives": [{"objectiveId": "obj-1", "statement": "exercise bridge", "priority": 1}],
            "constraints": [{
                "kind": "resource_boundary", "constraintId": "con-1",
                "origin": "explicit_user",
                "scope": {"kind": "filesystem", "rootPath": str(root), "recursive": True},
            }],
            "successCriteria": [{
                "criterionId": "sc-1", "statement": "tool result recorded",
                "requiresVerification": True,
            }],
            "terminationCriteria": [{
                "criterionId": "tc-1", "statement": "stop", "terminalState": "failed",
            }],
            "unresolvedAmbiguities": [],
            "taskGraphId": None,
            "createdAt": NOW,
        },
        _meta("mission", actor="operator-test", kind="human"),
    )
    runtime.service.evaluate_policy(
        {
            "schemaVersion": "1.0.0",
            "policyDecisionId": policy_id,
            "policyBundleDigest": contracts.digest({"policy": "model-tools"}),
            "effect": "allow",
            "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
            "missionId": mission_id,
            "taskId": task_id,
            "requestedOperations": operations,
            "requestedScope": {"kind": "filesystem", "rootPath": str(root), "recursive": True},
            "conditions": [],
            "rationale": "test bounded model tool authority",
            "decidedBy": {"actorId": "gk-1", "kind": "governance_kernel"},
            "decidedAt": NOW,
        },
        _meta("policy"),
    )
    runtime.service.issue_grant(
        {
            "schemaVersion": "1.0.0",
            "grantId": grant_id,
            "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
            "capabilityId": "cap.model.tools",
            "operations": operations,
            "scope": {"kind": "filesystem", "rootPath": str(root), "recursive": True},
            "policyDecisionId": policy_id,
            "policyBundleDigest": contracts.digest({"policy": "model-tools"}),
            "conditions": [],
            "maxUses": 16,
            "validFrom": "2026-09-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "issuedBy": {"actorId": "gk-1", "kind": "governance_kernel"},
            "issuedAt": NOW,
        },
        _meta("grant"),
    )
    runtime.service.activate_lease(
        {
            "schemaVersion": "1.0.0",
            "leaseId": lease_id,
            "grantId": grant_id,
            "missionId": mission_id,
            "taskId": task_id,
            "executionContextId": "ec-model-tools",
            "operations": operations,
            "scope": {"kind": "filesystem", "rootPath": str(root), "recursive": True},
            "maxUses": 16,
            "validFrom": "2026-09-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "activatedAt": NOW,
        },
        _meta("lease"),
    )
    return grant_id, lease_id


def _bridge(runtime, root: Path, profile: dict, operations: list[str]):
    grant, lease = _authority(runtime, root, operations)
    return ModelToolBridge(
        broker=runtime.tool_broker,
        authority_profile=profile,
        grant_id=grant,
        lease_id=lease,
        operator_id="operator-test",
        session_id="session-test",
        driver_run_id="dr-model-tools",
        now=lambda: NOW,
    )


def test_safe_profile_advertises_only_read_and_search(tmp_path: Path):
    profile = normalize_model_authority(None, target_root=str(tmp_path))
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        bridge = _bridge(runtime, tmp_path, profile, profile["toolOperations"])
        names = [item["function"]["name"] for item in bridge.openai_tools()]
        assert names == ["capt_file_read", "capt_file_search"]
    finally:
        runtime.close()


def test_file_read_executes_through_toolbroker_and_records_execution(tmp_path: Path):
    target = tmp_path / "hello.txt"
    target.write_text("CAPT_BRIDGE_OK")
    profile = normalize_model_authority(None, target_root=str(tmp_path))
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        bridge = _bridge(runtime, tmp_path, profile, profile["toolOperations"])
        result = bridge.execute_call(
            "capt_file_read", {"path": str(target)}, call_id="call-read"
        )
        assert result["status"] == "succeeded"
        assert result["values"]["content"] == "CAPT_BRIDGE_OK"
        assert any(kind == "tool_execution" for _, kind, _ in runtime.store.all_aggregates())
    finally:
        runtime.close()


def test_unapproved_write_and_shell_are_rejected_before_toolbroker(tmp_path: Path):
    profile = normalize_model_authority(None, target_root=str(tmp_path))
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        bridge = _bridge(runtime, tmp_path, profile, profile["toolOperations"])
        with pytest.raises(AuthorityViolation, match="MODEL_TOOL_NOT_AUTHORIZED"):
            bridge.execute_call(
                "capt_file_write", {"path": str(tmp_path / "x.txt"), "content": "x"},
                call_id="call-write",
            )
        with pytest.raises(AuthorityViolation, match="MODEL_TOOL_NOT_AUTHORIZED"):
            bridge.execute_call(
                "capt_shell_exec", {"argv": ["/bin/pwd"], "cwd": str(tmp_path)},
                call_id="call-shell",
            )
        assert all(kind != "tool_execution" for _, kind, _ in runtime.store.all_aggregates())
    finally:
        runtime.close()


def test_write_and_shell_execute_when_explicitly_authorized(tmp_path: Path):
    profile = normalize_model_authority(
        {
            "filesystemScope": "project",
            "filesystemRoot": str(tmp_path),
            "fileMutationAllowed": True,
            "shellAccessAllowed": True,
            "providerNetworkPolicy": "local_only",
        },
        target_root=str(tmp_path),
    )
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        bridge = _bridge(runtime, tmp_path, profile, profile["toolOperations"])
        target = tmp_path / "written.txt"
        write = bridge.execute_call(
            "capt_file_write", {"path": str(target), "content": "written-by-capt"},
            call_id="call-write",
        )
        assert write["status"] == "succeeded"
        assert target.read_text() == "written-by-capt"
        shell = bridge.execute_call(
            "capt_shell_exec", {"argv": ["/bin/pwd"], "cwd": str(tmp_path)},
            call_id="call-shell",
        )
        assert shell["status"] == "succeeded"
        assert str(tmp_path) in shell["values"]["stdout"]
    finally:
        runtime.close()


def test_scope_escape_never_reads_outside_approved_root(tmp_path: Path):
    root = tmp_path / "root"; root.mkdir()
    outside = tmp_path / "outside.txt"; outside.write_text("SECRET")
    profile = normalize_model_authority(None, target_root=str(root))
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        bridge = _bridge(runtime, root, profile, profile["toolOperations"])
        result = bridge.execute_call(
            "capt_file_read", {"path": str(outside)}, call_id="call-escape"
        )
        assert result["status"] != "succeeded"
        assert "SECRET" not in str(result)
    finally:
        runtime.close()


def test_runtime_issues_exact_model_tool_authority_and_revokes_it(tmp_path: Path):
    from capt_runtime.model_tool_authority import issue_model_tool_authority, revoke_model_tool_authority

    root = tmp_path / "authority-root"
    root.mkdir()
    (root / "hello.txt").write_text("BOUND")
    runtime = create_runtime(str(tmp_path / "authority-runtime.db"))
    profile = normalize_model_authority(None, target_root=str(root))
    try:
        runtime.service.create_mission(
            {
                "schemaVersion": "1.0.0", "missionId": "m-issued-tools",
                "rawRequest": "issue model tool authority", "normalizedRequest": "issue model tool authority",
                "objectives": [{"objectiveId": "obj-1", "statement": "use tools", "priority": 1}],
                "constraints": [],
                "successCriteria": [{"criterionId": "sc-1", "statement": "bounded", "requiresVerification": True}],
                "terminationCriteria": [{"criterionId": "tc-1", "statement": "stop", "terminalState": "failed"}],
                "unresolvedAmbiguities": [], "taskGraphId": None, "createdAt": NOW,
            },
            _meta("issued-mission", actor="operator-test", kind="human"),
        )
        authority = issue_model_tool_authority(
            service=runtime.service,
            broker=runtime.tool_broker,
            authority_profile=profile,
            target_root=str(root),
            mission_id="m-issued-tools",
            task_id="t-issued-tools",
            driver_run_id="dr-issued-tools",
            operator_id="operator-test",
            session_id="session-test",
            issued_at=NOW,
            valid_until="2030-01-01T00:00:00Z",
            metadata_factory=lambda step: _meta("issued-" + step),
            now=lambda: NOW,
        )
        state = runtime.store.require_state("capability-" + authority.grant_id)
        assert state["operations"] == ["file.read", "file.search"]
        assert state["scope"]["rootPath"] == str(root.resolve())
        assert state["validUntil"] == "2030-01-01T00:00:00Z"
        assert authority.bridge.openai_tools()[0]["function"]["name"] == "capt_file_read"
        result = authority.bridge.execute_call(
            "capt_file_read", {"path": "hello.txt"}, call_id="read-before-revoke"
        )
        assert result["status"] == "succeeded"

        revoke_model_tool_authority(
            service=runtime.service,
            grant_id=authority.grant_id,
            issued_at=NOW,
            reason="provider tool phase closed",
            metadata=_meta("issued-revoke"),
        )
        denied = authority.bridge.execute_call(
            "capt_file_read", {"path": "hello.txt"}, call_id="read-after-revoke"
        )
        assert denied["status"] == "denied"
    finally:
        runtime.close()


def test_checkpoint_accounts_for_durable_tool_execution_stream(tmp_path: Path):
    from capt_runtime.checkpoint import create_checkpoint

    root = tmp_path / "checkpoint-tools-root"
    root.mkdir()
    (root / "hello.txt").write_text("CHECKPOINT_TOOL")
    runtime = create_runtime(str(tmp_path / "checkpoint-tools.db"))
    profile = normalize_model_authority(None, target_root=str(root))
    try:
        bridge = _bridge(runtime, root, profile, profile["toolOperations"])
        result = bridge.execute_call(
            "capt_file_read", {"path": "hello.txt"}, call_id="checkpoint-read"
        )
        assert result["status"] == "succeeded"
        manifest = create_checkpoint(
            runtime.store,
            "cp-tool-execution",
            NOW,
            contracts.digest({"policy": "checkpoint-tools"}),
        )
        assert manifest["toolExecutionVersions"] == [{
            "streamId": "tool_execution-" + result["toolExecutionId"],
            "version": runtime.store.aggregate_version(
                "tool_execution-" + result["toolExecutionId"]
            ),
        }]
    finally:
        runtime.close()


def test_model_visible_tool_result_is_bounded_but_eventstore_keeps_full_result(tmp_path: Path):
    payload = "BEGIN-" + ("x" * 30000) + "-END"
    target = tmp_path / "large.txt"
    target.write_text(payload, encoding="utf-8")
    profile = normalize_model_authority(None, target_root=str(tmp_path))
    runtime = create_runtime(str(tmp_path / "rt-bounded.db"))
    try:
        bridge = _bridge(runtime, tmp_path, profile, profile["toolOperations"])
        visible = bridge.execute_call(
            "capt_file_read", {"path": str(target), "limit_bytes": 65536},
            call_id="call-large-read",
        )
        shown = visible["values"]["content"]
        assert shown.startswith("BEGIN-")
        assert shown.endswith("-END")
        assert "bytes omitted here" in shown
        assert len(str(visible).encode("utf-8")) < len(payload.encode("utf-8"))

        state = runtime.store.require_state(
            "tool_execution-" + visible["toolExecutionId"]
        )
        raw_values = {
            item["name"]: item.get("value")
            for item in state["result"]["output"]
        }
        assert raw_values["content"] == payload
        assert "bytes omitted here" not in raw_values["content"]
    finally:
        runtime.close()
