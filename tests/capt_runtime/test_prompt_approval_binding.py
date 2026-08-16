from __future__ import annotations

import pytest

from capt_runtime import commands
from capt_runtime.errors import AuthorityViolation
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore

DIGEST = "sha256:" + "a" * 64


def meta(command_id: str, actor_kind: str, key: str):
    return commands.command(command_id=command_id, idempotency_key=key,
        operation_fingerprint="sha256:" + "b" * 64, correlation_id="corr",
        actor_id="operator", actor_kind=actor_kind,
        issued_at="2026-08-16T00:00:00Z")


def request(request_id: str, digest: str = DIGEST):
    return {"schemaVersion": "1.0.0", "requestId": request_id,
        "missionId": "m-1", "taskId": "t-1", "requestedCapability": "cap.fs.read",
        "resource": "/tmp", "operation": "ModelOperatorInspection",
        "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": True},
        "riskClassification": "low", "policyReason": "Approve exact model-visible prompt.",
        "requestedBy": {"actorId": "exec-1", "kind": "execution_plane"},
        "expiresAt": "2030-01-01T00:00:00Z", "correlationId": "corr",
        "createdAt": "2026-08-16T00:00:00Z", "promptAssemblyDigest": digest}


def approve(svc: RuntimeService, request_id: str):
    svc.submit_human_approval_decision({"schemaVersion": "1.0.0", "requestId": request_id,
        "decision": "approve", "operatorId": "operator", "decidedAt": "2026-08-16T00:00:01Z",
        "note": None, "idempotencyKey": "approve-" + request_id,
        "correlationId": "corr", "sessionId": "sess"}, meta("approve-" + request_id, "human", "approve-" + request_id))


def test_durable_approved_prompt_digest_is_required_and_survives_restart(tmp_path):
    db = str(tmp_path / "ledger.db")
    store = EventStore(db); svc = RuntimeService(store)
    svc.request_human_approval(request("r-1"), meta("request-1", "execution_plane", "request-1"))
    approve(svc, "r-1")
    assert svc.require_approved_prompt_assembly("r-1", DIGEST, "ModelOperatorInspection")["state"] == "approved"
    store.close()
    store = EventStore(db); svc = RuntimeService(store)
    assert svc.require_approved_prompt_assembly("r-1", DIGEST, "ModelOperatorInspection")["promptAssemblyDigest"] == DIGEST
    store.close()


def test_unapproved_and_stale_or_wrong_digest_receipts_fail_closed(tmp_path):
    store = EventStore(str(tmp_path / "ledger.db")); svc = RuntimeService(store)
    svc.request_human_approval(request("r-2"), meta("request-2", "execution_plane", "request-2"))
    with pytest.raises(AuthorityViolation, match="NOT_APPROVED"):
        svc.require_approved_prompt_assembly("r-2", DIGEST, "ModelOperatorInspection")
    approve(svc, "r-2")
    with pytest.raises(AuthorityViolation, match="DIGEST_MISMATCH"):
        svc.require_approved_prompt_assembly("r-2", "sha256:" + "c" * 64, "ModelOperatorInspection")
    with pytest.raises(AuthorityViolation, match="OPERATION_MISMATCH"):
        svc.require_approved_prompt_assembly("r-2", DIGEST, "OtherOperation")
    store.close()
