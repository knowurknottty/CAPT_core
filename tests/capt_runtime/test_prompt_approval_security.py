from __future__ import annotations

from copy import deepcopy

import pytest

from capt_runtime import commands
from capt_runtime.checkpoint import create_checkpoint
from capt_runtime.errors import AuthorityViolation
from capt_runtime.prompt_approval import request_model_prompt_approval
from capt_runtime.replay import checkpoint_replay, full_replay, replay_equivalent
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from desktop.capt_runtime_service import RuntimeQueryService, _provider_credential_required


DIGEST = "sha256:" + "a" * 64


def meta(
    command_id: str,
    actor_kind: str,
    key: str,
    *,
    correlation: str = "corr-security",
    issued_at: str = "2026-08-16T00:00:00Z",
):
    return commands.command(
        command_id=command_id,
        idempotency_key=key,
        operation_fingerprint="sha256:" + "b" * 64,
        correlation_id=correlation,
        actor_id="operator" if actor_kind == "human" else "exec-1",
        actor_kind=actor_kind,
        issued_at=issued_at,
        replay_policy="never",
    )


def approval_intent(**overrides):
    intent = {
        "missionId": "m-security-1",
        "taskId": "t-security-1",
        "driverRunId": "dr-security-1",
        "objective": "Inspect the repository and report bounded findings.",
        "targetRoot": "/tmp/security-project",
        "provider": "",
        "model": "hermes",
        "responseMode": "SPOCK",
        "promptEnhancement": "OFF",
        "requestedContextBudget": 64_000,
        "humanVerificationRequired": True,
        "executable": "/opt/hermes/bin/hermes",
        "expiresAt": "2030-01-01T00:00:00Z",
    }
    intent.update(overrides)
    return intent


def raw_request(request_id: str, *, expires_at: str = "2030-01-01T00:00:00Z"):
    return {
        "schemaVersion": "1.0.0",
        "requestId": request_id,
        "missionId": "m-security-raw",
        "taskId": "t-security-raw",
        "requestedCapability": "cap.fs.read",
        "resource": "/tmp/security-project",
        "operation": "ModelOperatorInspection",
        "scope": {"kind": "filesystem", "rootPath": "/tmp/security-project", "recursive": True},
        "riskClassification": "low",
        "policyReason": "Bounded approval security regression.",
        "requestedBy": {"actorId": "exec-1", "kind": "execution_plane"},
        "expiresAt": expires_at,
        "remainingUses": 1,
        "correlationId": "corr-security-raw",
        "createdAt": "2026-08-15T00:00:00Z",
        "promptAssemblyDigest": DIGEST,
    }


def approve(svc: RuntimeService, request_id: str, *, decided_at: str = "2026-08-15T00:00:01Z"):
    svc.submit_human_approval_decision(
        {
            "schemaVersion": "1.0.0",
            "requestId": request_id,
            "decision": "approve",
            "operatorId": "operator",
            "decidedAt": decided_at,
            "note": None,
            "idempotencyKey": "approve-" + request_id,
            "correlationId": "corr-security-decision",
            "sessionId": "sess-security",
        },
        meta(
            "approve-" + request_id,
            "human",
            "approve-" + request_id,
            correlation="corr-security-decision",
            issued_at=decided_at,
        ),
        now=decided_at,
    )


def planner_result(tmp_path, label: str, intent: dict):
    store = EventStore(str(tmp_path / (label + ".db")))
    try:
        svc = RuntimeService(store)
        return request_model_prompt_approval(
            svc,
            intent,
            meta(
                "cmd-" + label,
                "human",
                "idem-" + label,
                correlation="corr-" + label,
            ),
        )
    finally:
        store.close()


def test_approval_digest_binds_every_execution_relevant_operator_input(tmp_path):
    base = approval_intent()
    base_digest = planner_result(tmp_path, "base", base)["promptAssemblyDigest"]
    mutations = {
        "provider": "ollama",
        "model": "qwen3.5:9b",
        "requestedContextBudget": 96_000,
        "humanVerificationRequired": False,
        "targetRoot": "/tmp/other-project",
        "missionId": "m-security-2",
        "taskId": "t-security-2",
        "driverRunId": "dr-security-2",
        "executable": "/tmp/alternate-hermes",
    }
    for field, value in mutations.items():
        changed = deepcopy(base)
        changed[field] = value
        changed_digest = planner_result(tmp_path, "mut-" + field, changed)["promptAssemblyDigest"]
        assert changed_digest != base_digest, field


def test_local_no_auth_provider_does_not_require_synthetic_credential():
    from capt_ui.operator.providers import ProviderKind

    class P:
        kind = ProviderKind.LOCAL
        key_ref = ""

    assert _provider_credential_required(P()) is False
    P.key_ref = "env:LOCAL_PROVIDER_KEY"
    assert _provider_credential_required(P()) is True
    P.kind = ProviderKind.CLOUD
    P.key_ref = ""
    assert _provider_credential_required(P()) is True


def test_model_operator_objective_can_exceed_task_title_limit_without_overflow(tmp_path):
    from capt_runtime.contracts import require
    long_objective = "evidence-grounded review " * 40
    assert 512 < len(long_objective) < 4096
    intent = {
        "schemaVersion": "1.0.0",
        "missionId": "m-long-objective",
        "objective": long_objective,
        "taskTitle": "Bounded model review",
        "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": True},
        "requiresApproval": False,
    }
    require("OperatorMissionIntent", intent)


def test_transport_whitespace_is_canonicalized_before_approval_binding(tmp_path):
    base = approval_intent(
        provider="mtplx", model="qwen3.8-27b-mtplx", executable=""
    )
    canonical = planner_result(tmp_path, "canonical-whitespace", base)
    transported = deepcopy(base)
    transported.update(
        objective="  " + base["objective"] + "\n",
        targetRoot=" " + base["targetRoot"] + " ",
        provider=" mtplx ",
        model=" qwen3.8-27b-mtplx\n",
        executable=" ",
    )
    normalized = planner_result(tmp_path, "transport-whitespace", transported)

    assert normalized["promptAssemblyDigest"] == canonical["promptAssemblyDigest"]
    assert normalized["dispatchPromptDigest"] == canonical["dispatchPromptDigest"]
    assert normalized["modelVisiblePromptDigest"] == canonical["modelVisiblePromptDigest"]

    changed = deepcopy(base)
    changed["objective"] = base["objective"].replace("bounded", "different")
    distinct = planner_result(tmp_path, "semantic-change", changed)
    assert distinct["promptAssemblyDigest"] != canonical["promptAssemblyDigest"]


def test_planner_persists_one_use_execution_binding_and_exact_dispatch_digest(tmp_path):
    store = EventStore(str(tmp_path / "binding.db"))
    try:
        svc = RuntimeService(store)
        result = request_model_prompt_approval(
            svc,
            approval_intent(requestId="approval-security-binding"),
            meta("cmd-binding", "human", "idem-binding"),
        )
        state = store.require_state("human_approval-approval-security-binding")
        binding = state["scope"].get("approvalBinding")
        assert state["remainingUses"] == 1
        assert isinstance(binding, dict)
        assert binding["missionId"] == "m-security-1"
        assert binding["taskId"] == "t-security-1"
        assert binding["driverRunId"] == "dr-security-1"
        assert binding["targetRoot"] == "/tmp/security-project"
        assert binding["executable"] == "/opt/hermes/bin/hermes"
        assert binding["dispatchPromptDigest"] == result["dispatchPromptDigest"]
        assert result["dispatchPromptDigest"].startswith("sha256:")
    finally:
        store.close()


def test_checkpoint_accounts_for_durable_human_approval_stream(tmp_path):
    store = EventStore(str(tmp_path / "checkpoint-approval.db"))
    try:
        svc = RuntimeService(store)
        result = request_model_prompt_approval(
            svc,
            approval_intent(requestId="approval-checkpoint"),
            meta("cmd-checkpoint-request", "human", "idem-checkpoint-request"),
        )
        manifest = create_checkpoint(
            store,
            "cp-approval-security",
            "2026-08-17T00:00:00Z",
            "sha256:" + "c" * 64,
        )
        assert manifest["humanApprovalVersions"] == [
            {"streamId": "human_approval-" + result["requestId"], "version": 1}
        ]
        full = full_replay(store)
        partial = checkpoint_replay(store, manifest)
        assert replay_equivalent(full, partial)
        assert full.aggregates["human_approval-" + result["requestId"]]["state"] == "requested"
    finally:
        store.close()


def test_approved_request_is_rejected_after_expiry_at_use_time(tmp_path):
    store = EventStore(str(tmp_path / "expired.db"))
    try:
        svc = RuntimeService(store)
        result = request_model_prompt_approval(
            svc,
            approval_intent(
                requestId="approval-expired",
                expiresAt="2026-08-16T00:00:00Z",
            ),
            meta(
                "cmd-expired-request",
                "human",
                "idem-expired-request",
                issued_at="2026-08-15T00:00:00Z",
            ),
        )
        approve(svc, "approval-expired", decided_at="2026-08-15T00:00:01Z")
        with pytest.raises(AuthorityViolation, match="EXPIRED"):
            svc.admit_approved_model_execution(
                "approval-expired",
                result["promptAssemblyDigest"],
                "ModelOperatorInspection",
                mission_id="m-security-1",
                task_id="t-security-1",
                driver_run_id="dr-security-1",
                resource="/tmp/security-project",
                use_id="run-expired",
                now="2026-08-17T00:00:00Z",
                metadata=meta(
                    "cmd-expired-use",
                    "execution_plane",
                    "idem-expired-use",
                    issued_at="2026-08-17T00:00:00Z",
                ),
            )
    finally:
        store.close()


def test_existing_request_id_cannot_be_recreated_under_new_command(tmp_path):
    store = EventStore(str(tmp_path / "duplicate-request.db"))
    try:
        svc = RuntimeService(store)
        request = raw_request("approval-duplicate")
        svc.request_human_approval(
            request,
            meta("cmd-duplicate-1", "execution_plane", "idem-duplicate-1"),
        )
        with pytest.raises(AuthorityViolation, match="ALREADY_EXISTS"):
            svc.request_human_approval(
                request,
                meta(
                    "cmd-duplicate-2",
                    "execution_plane",
                    "idem-duplicate-2",
                    correlation="corr-duplicate-2",
                ),
            )
    finally:
        store.close()


def test_exact_approval_retry_uses_outer_idempotency_not_fresh_correlation(tmp_path):
    store = EventStore(str(tmp_path / "retry.db"))
    try:
        svc = RuntimeService(store)
        intent = approval_intent()
        first = request_model_prompt_approval(
            svc,
            intent,
            meta("cmd-retry", "human", "idem-retry", correlation="corr-retry-a"),
        )
        second = request_model_prompt_approval(
            svc,
            intent,
            meta("cmd-retry", "human", "idem-retry", correlation="corr-retry-b"),
        )
        assert second["status"] == "idempotent"
        assert second["requestId"] == first["requestId"]
        assert second["promptAssemblyDigest"] == first["promptAssemblyDigest"]
        approvals = [
            stream_id
            for stream_id, kind, _version in store.all_aggregates()
            if kind == "human_approval"
        ]
        assert len(approvals) == 1
    finally:
        store.close()


def test_capability_self_description_advertises_every_prompt_approval_command(tmp_path):
    store = EventStore(str(tmp_path / "capabilities.db"))
    try:
        result = RuntimeQueryService(store).handle({"op": "capabilities"})
        assert result["ok"] is True
        assert "request_model_prompt_approval" in result["result"]["commandOperations"]
    finally:
        store.close()


def test_authoritative_admission_binds_ids_and_consumes_once(tmp_path):
    store = EventStore(str(tmp_path / "consume.db"))
    try:
        svc = RuntimeService(store)
        result = request_model_prompt_approval(
            svc,
            approval_intent(requestId="approval-consume"),
            meta("cmd-consume-request", "human", "idem-consume-request"),
        )
        approve(svc, "approval-consume", decided_at="2026-08-16T00:00:01Z")
        admit = getattr(svc, "admit_approved_model_execution", None)
        assert callable(admit), "RuntimeService lacks authoritative one-use model approval admission"

        with pytest.raises(AuthorityViolation, match="MISSION_MISMATCH"):
            admit(
                "approval-consume",
                result["promptAssemblyDigest"],
                "ModelOperatorInspection",
                mission_id="m-wrong",
                task_id="t-security-1",
                driver_run_id="dr-security-1",
                resource="/tmp/security-project",
                use_id="run-use-wrong",
                now="2026-08-16T00:00:02Z",
                metadata=meta(
                    "cmd-consume-wrong",
                    "execution_plane",
                    "idem-consume-wrong",
                    issued_at="2026-08-16T00:00:02Z",
                ),
            )

        admitted = admit(
            "approval-consume",
            result["promptAssemblyDigest"],
            "ModelOperatorInspection",
            mission_id="m-security-1",
            task_id="t-security-1",
            driver_run_id="dr-security-1",
            resource="/tmp/security-project",
            use_id="run-use-1",
            now="2026-08-16T00:00:02Z",
            metadata=meta(
                "cmd-consume-exact",
                "execution_plane",
                "idem-consume-exact",
                issued_at="2026-08-16T00:00:02Z",
            ),
        )
        assert admitted["state"] == "consumed"
        assert admitted["remainingUses"] == 0
        assert admitted["consumedBy"] == "run-use-1"

        replay = admit(
            "approval-consume",
            result["promptAssemblyDigest"],
            "ModelOperatorInspection",
            mission_id="m-security-1",
            task_id="t-security-1",
            driver_run_id="dr-security-1",
            resource="/tmp/security-project",
            use_id="run-use-1",
            now="2026-08-16T00:00:03Z",
            metadata=meta(
                "cmd-consume-replay",
                "execution_plane",
                "idem-consume-replay",
                issued_at="2026-08-16T00:00:03Z",
            ),
        )
        assert replay["state"] == "consumed"
        assert replay["consumedBy"] == "run-use-1"

        with pytest.raises(AuthorityViolation, match="CONSUMED"):
            admit(
                "approval-consume",
                result["promptAssemblyDigest"],
                "ModelOperatorInspection",
                mission_id="m-security-1",
                task_id="t-security-1",
                driver_run_id="dr-security-1",
                resource="/tmp/security-project",
                use_id="run-use-2",
                now="2026-08-16T00:00:04Z",
                metadata=meta(
                    "cmd-consume-second",
                    "execution_plane",
                    "idem-consume-second",
                    issued_at="2026-08-16T00:00:04Z",
                ),
            )
    finally:
        store.close()
