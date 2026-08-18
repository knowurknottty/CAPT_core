"""CAPT-UPG-015 discriminating tests for the authenticated lease kill-key path."""
from __future__ import annotations

import pytest

from capt_runtime import commands
from capt_runtime.aggregates.capability import CapabilityAggregate
from capt_runtime.composition import create_runtime
from capt_runtime.errors import AuthorityViolation, CapabilityDenied
from capt_runtime.services import RuntimeService
from capt_runtime.store import AppendRequest, EventStore

TS = "2026-08-18T06:00:00Z"
SCOPE = {"kind": "filesystem", "rootPath": "/tmp/capt-upg-015", "recursive": False}


def _metadata(command_id: str, idem: str, operation: str, subject, actor_kind="governance_kernel"):
    return commands.command(
        command_id=command_id,
        idempotency_key=idem,
        operation_fingerprint=commands.fingerprint(operation, subject),
        correlation_id="corr-" + command_id,
        actor_id="seed-governance",
        actor_kind=actor_kind,
        issued_at=TS,
    )


def _seed_leased_capability(store: EventStore) -> None:
    grant = {
        "schemaVersion": "1.0.0",
        "grantId": "g-kill",
        "subject": {"actorId": "exec-1", "kind": "execution_plane"},
        "capabilityId": "cap.fs.write",
        "operations": ["fs.write"],
        "scope": {"kind": "filesystem", "rootPath": "/tmp/capt-upg-015", "recursive": True},
        "policyDecisionId": "pd-seed",
        "policyBundleDigest": "sha256:" + "1" * 64,
        "conditions": [],
        "maxUses": 3,
        "validFrom": "2026-08-18T00:00:00Z",
        "validUntil": "2026-08-19T00:00:00Z",
        "issuedBy": {"actorId": "seed-governance", "kind": "governance_kernel"},
        "issuedAt": TS,
    }
    state = CapabilityAggregate.grant(grant)
    meta = _metadata("seed-grant", "idem-seed-grant", "seed_grant", grant)
    event = commands.envelope(
        event_id="ev-seed-grant",
        stream_id="capability-g-kill",
        event_type="CapabilityGranted",
        payload={"eventType": "CapabilityGranted", "grant": grant},
        metadata=meta,
        occurred_at=TS,
    )
    store.commit_command(
        [AppendRequest("capability-g-kill", CapabilityAggregate.KIND, 0, event, state)],
        meta["idempotencyKey"], meta["operationFingerprint"], meta["commandId"],
    )

    lease = {
        "schemaVersion": "1.0.0",
        "leaseId": "l-kill",
        "grantId": "g-kill",
        "missionId": "m-kill",
        "taskId": "t-kill",
        "executionContextId": "ec-kill",
        "operations": ["fs.write"],
        "scope": SCOPE,
        "maxUses": 2,
        "validFrom": "2026-08-18T00:01:00Z",
        "validUntil": "2026-08-18T23:00:00Z",
        "activatedAt": TS,
    }
    leased = CapabilityAggregate.activate_lease(state, lease)
    meta2 = _metadata("seed-lease", "idem-seed-lease", "seed_lease", lease)
    event2 = commands.envelope(
        event_id="ev-seed-lease",
        stream_id="capability-g-kill",
        event_type="CapabilityLeaseActivated",
        payload={"eventType": "CapabilityLeaseActivated", "lease": lease},
        metadata=meta2,
        occurred_at=TS,
        mission_id="m-kill",
        task_id="t-kill",
    )
    store.commit_command(
        [AppendRequest("capability-g-kill", CapabilityAggregate.KIND, 1, event2, leased)],
        meta2["idempotencyKey"], meta2["operationFingerprint"], meta2["commandId"],
    )


def _command(*, command_id="kill-1", idem="idem-kill-1", operator="captain", session="s-1", reason="operator emergency stop", target_id="l-kill"):
    return {
        "commandId": command_id,
        "operatorId": operator,
        "sessionId": session,
        "schemaVersion": "1.0.0",
        "correlationId": "corr-" + command_id,
        "idempotencyKey": idem,
        "timestamp": TS,
        "op": "revoke_capability",
        "payload": {
            "grantId": "g-kill",
            "targetKind": "lease",
            "targetId": target_id,
            "reason": reason,
        },
    }


def test_authenticated_operator_kill_key_revokes_lease_and_blocks_future_use(tmp_path):
    comp = create_runtime(str(tmp_path / "runtime.db"))
    _seed_leased_capability(comp.store)
    comp.service.check_lease("g-kill", "l-kill", "fs.write", SCOPE, TS)

    relay = comp.command_service("captain", "s-1")
    receipt = relay.execute(_command())

    assert receipt["status"] == "accepted"
    assert receipt["classification"] == "accepted"
    state = comp.store.require_state("capability-g-kill")
    assert state["grantState"] == "revoked"
    assert state["lease"]["state"] == "revoked"
    assert state["revocation"]["targetKind"] == "lease"
    assert state["revocation"]["targetId"] == "l-kill"
    assert state["revocation"]["revokedBy"] == "captain"
    assert comp.store.read_stream("capability-g-kill")[-1]["payload"]["eventType"] == "CapabilityLeaseRevoked"

    with pytest.raises(CapabilityDenied, match="revoked"):
        comp.service.check_lease("g-kill", "l-kill", "fs.write", SCOPE, TS)
    comp.close()


def test_kill_key_exact_retry_is_idempotent_and_conflicting_replay_is_rejected(tmp_path):
    comp = create_runtime(str(tmp_path / "runtime.db"))
    _seed_leased_capability(comp.store)
    relay = comp.command_service("captain", "s-1")
    command = _command()

    first = relay.execute(command)
    head = comp.store.head_sequence()
    second = relay.execute(command)
    assert first["status"] == "accepted"
    assert second["status"] == "idempotent"
    assert second["classification"] == "duplicate"
    assert comp.store.head_sequence() == head

    conflict = _command(reason="different semantic operation")
    rejected = relay.execute(conflict)
    assert rejected["status"] == "rejected"
    assert rejected["classification"] == "conflict"
    assert rejected["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert comp.store.head_sequence() == head
    comp.close()


def test_kill_key_rejects_wrong_authenticated_identity_without_mutation(tmp_path):
    comp = create_runtime(str(tmp_path / "runtime.db"))
    _seed_leased_capability(comp.store)
    relay = comp.command_service("captain", "s-1")
    before = comp.store.head_sequence()

    receipt = relay.execute(_command(operator="intruder"))
    assert receipt["status"] == "rejected"
    assert receipt["classification"] == "unauthorized"
    assert comp.store.head_sequence() == before
    assert comp.store.require_state("capability-g-kill")["revocation"] is None
    comp.close()


def test_kill_key_rejects_semantically_mismatched_target_at_runtime_authority_boundary(tmp_path):
    comp = create_runtime(str(tmp_path / "runtime.db"))
    _seed_leased_capability(comp.store)
    relay = comp.command_service("captain", "s-1")
    before = comp.store.head_sequence()

    receipt = relay.execute(_command(target_id="l-not-active"))
    assert receipt["status"] == "rejected"
    assert receipt["classification"] == "authority"
    assert "does not match active lease" in receipt["detail"]
    assert comp.store.head_sequence() == before
    assert comp.store.require_state("capability-g-kill")["revocation"] is None
    comp.close()


def test_revocation_survives_close_reopen_and_remains_terminal(tmp_path):
    ledger = str(tmp_path / "runtime.db")
    comp = create_runtime(ledger)
    _seed_leased_capability(comp.store)
    receipt = comp.command_service("captain", "s-1").execute(_command())
    assert receipt["status"] == "accepted"
    comp.close()

    reopened = create_runtime(ledger)
    state = reopened.store.require_state("capability-g-kill")
    assert state["grantState"] == "revoked"
    assert state["lease"]["state"] == "revoked"
    assert state["revocation"]["reason"] == "operator emergency stop"
    with pytest.raises(CapabilityDenied, match="revoked"):
        reopened.service.check_lease("g-kill", "l-kill", "fs.write", SCOPE, TS)
    reopened.close()


def test_base_runtime_service_itself_rejects_mismatched_revocation_target(tmp_path):
    store = EventStore(str(tmp_path / "runtime.db"))
    _seed_leased_capability(store)
    svc = RuntimeService(store)
    revocation = {
        "schemaVersion": "1.0.0",
        "revocationId": "rev-direct",
        "targetKind": "lease",
        "targetId": "l-wrong",
        "reason": "must fail at canonical service boundary",
        "revokedBy": {"actorId": "captain", "kind": "human"},
        "revokedAt": TS,
    }
    meta = commands.command(
        command_id="direct-revoke",
        idempotency_key="idem-direct-revoke",
        operation_fingerprint=commands.fingerprint("revoke", revocation),
        correlation_id="corr-direct-revoke",
        actor_id="captain",
        actor_kind="human",
        issued_at=TS,
    )
    before = store.head_sequence()
    with pytest.raises(AuthorityViolation, match="does not match active lease"):
        svc.revoke("g-kill", revocation, meta)
    assert store.head_sequence() == before
    assert store.require_state("capability-g-kill")["revocation"] is None
    store.close()
