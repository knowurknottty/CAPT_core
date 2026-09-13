"""Audit trail for envelope-identity refusals.

A command whose envelope carries a foreign ``operatorId``/``sessionId`` is
refused as ``unauthorized``. That refusal previously left NO durable trace: only
two producers of ``security_rejections`` existed
(``unauthenticated_ipc_attempt`` and ``provider_spend_threshold_alert``), so a
*missing* session token was recorded while an identity-*spoofing* attempt — the
more security-relevant class — was invisible.

Two properties matter as much as the recording itself:

1. Only DIGESTS of the identifiers are written. The audit trail must prove a
   mismatch happened without becoming a store of the identifiers it protects.
2. A failure to write the audit row must never change the outcome. The command
   is already refused; an audit write must not turn that into a crash or, worse,
   an accept.
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

import pytest

from capt_runtime.store import EventStore
from desktop.capt_runtime_service import RuntimeQueryService
from desktop.m1_command_service import RuntimeCommandService

BOUND_OPERATOR = "operator-knowurknot"
BOUND_SESSION = "sess-bound-1"


def envelope(operator_id: str, session_id: str, op: str = "create_mission", payload: dict | None = None) -> dict:
    return {
        "commandId": "cmd-id-audit",
        "operatorId": operator_id,
        "sessionId": session_id,
        "schemaVersion": "1.0.0",
        "correlationId": "corr-audit",
        "idempotencyKey": "idem-audit",
        "timestamp": "2026-08-16T00:00:00Z",
        "op": op,
        "payload": payload if payload is not None else {},
    }


def mission_payload(mission_id: str) -> dict:
    """The desktop `create_mission` op takes an OperatorMissionIntent."""
    return {
        "schemaVersion": "1.0.0",
        "missionId": mission_id,
        "objective": "Read-only repository analysis of the local worktree.",
        "rawRequest": "analyze repo",
        "normalizedRequest": "analyze repo",
        "constraints": [
            {"kind": "resource_boundary", "constraintId": "con-1", "origin": "explicit_user",
             "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False}}
        ],
        "successCriteria": [
            {"criterionId": "sc-1", "statement": "Analysis produced.", "requiresVerification": True}
        ],
        "terminationCriteria": [
            {"criterionId": "tc-1", "statement": "Invariant violation.", "terminalState": "failed"}
        ],
        "unresolvedAmbiguities": [],
        "requiresApproval": False,
        "requestedCapability": "cap.fs.read",
        "operation": "RepositoryRead",
        "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False},
        "riskClassification": "low",
        "policyReason": "Operator-initiated read-only analysis of a bounded root.",
    }


def service(store: EventStore) -> RuntimeCommandService:
    return RuntimeCommandService(store, BOUND_OPERATOR, BOUND_SESSION)


def identity_rows(store: EventStore) -> list:
    return [r for r in store.list_security_rejections()
            if r["rejectionKind"] == "unauthorized_envelope_identity"]


# --------------------------------------------------------------------------

def test_foreign_operator_id_is_refused_and_audited():
    store = EventStore(":memory:")
    try:
        result = service(store).execute(
            envelope("operator-someone-else", BOUND_SESSION, payload=mission_payload("m-audit-1"))
        )
        assert result["classification"] == "unauthorized"

        rows = identity_rows(store)
        assert len(rows) == 1
        details = rows[0]["details"]
        assert details["mismatchedFields"] == ["operatorId"]
        assert details["op"] == "create_mission"
        assert details["presentedOperatorDigest"].startswith("sha256:")
        assert details["boundOperatorDigest"].startswith("sha256:")
        # the presented and bound identities must be distinguishable
        assert details["presentedOperatorDigest"] != details["boundOperatorDigest"]
        # a session that DID match is still recorded as matching
        assert details["presentedSessionDigest"] == details["boundSessionDigest"]
    finally:
        store.close()


def test_foreign_session_id_is_refused_and_audited():
    store = EventStore(":memory:")
    try:
        result = service(store).execute(
            envelope(BOUND_OPERATOR, "sess-someone-else", payload=mission_payload("m-audit-2"))
        )
        assert result["classification"] == "unauthorized"
        rows = identity_rows(store)
        assert len(rows) == 1
        assert rows[0]["details"]["mismatchedFields"] == ["sessionId"]
    finally:
        store.close()


def test_both_fields_foreign_are_both_recorded():
    store = EventStore(":memory:")
    try:
        service(store).execute(
            envelope("operator-x", "sess-x", payload=mission_payload("m-audit-3"))
        )
        rows = identity_rows(store)
        assert len(rows) == 1
        assert rows[0]["details"]["mismatchedFields"] == ["operatorId", "sessionId"]
    finally:
        store.close()


def test_the_raw_identifiers_are_never_written():
    """The audit trail must not become a store of the identifiers."""
    store = EventStore(":memory:")
    try:
        service(store).execute(
            envelope("operator-THIS-MUST-NOT-APPEAR", "sess-ALSO-MUST-NOT", payload=mission_payload("m-audit-4"))
        )
        rows = identity_rows(store)
        assert len(rows) == 1
        blob = json.dumps(rows[0])
        assert "operator-THIS-MUST-NOT-APPEAR" not in blob
        assert "sess-ALSO-MUST-NOT" not in blob
        # the bound identity is not leaked either
        assert BOUND_OPERATOR not in blob
        assert BOUND_SESSION not in blob
    finally:
        store.close()


def test_a_correctly_bound_command_records_nothing():
    """Refusals are audited; accepted work must not spam the trail."""
    store = EventStore(":memory:")
    try:
        result = service(store).execute(
            envelope(BOUND_OPERATOR, BOUND_SESSION, payload=mission_payload("m-audit-5"))
        )
        assert result["classification"] == "accepted"
        assert identity_rows(store) == []
        assert store.list_security_rejections() == []
    finally:
        store.close()


def test_a_malformed_envelope_is_not_recorded_as_an_identity_rejection():
    """Malformed and unauthorized are different classes; only the latter is here."""
    store = EventStore(":memory:")
    try:
        bad = envelope(BOUND_OPERATOR, BOUND_SESSION)
        del bad["correlationId"]                 # now malformed
        result = service(store).execute(bad)
        assert result["classification"] == "malformed"
        assert identity_rows(store) == []
    finally:
        store.close()


def test_audit_failure_does_not_change_the_refusal(monkeypatch):
    """The refusal must survive an audit write that blows up."""
    store = EventStore(":memory:")
    try:
        def explode(*args, **kwargs):
            raise RuntimeError("audit store unavailable")

        monkeypatch.setattr(store, "record_security_rejection", explode)

        result = service(store).execute(
            envelope("operator-someone-else", BOUND_SESSION, payload=mission_payload("m-audit-6"))
        )
        # still refused, not raised, not accepted
        assert result["classification"] == "unauthorized"
        assert result["status"] == "rejected"
    finally:
        store.close()


def test_rejection_kind_is_distinct_from_the_existing_producers():
    """The new class must not be confused with a missing-token refusal."""
    store = EventStore(":memory:")
    try:
        store.record_security_rejection(
            rejection_id="rej-existing", rejection_kind="unauthenticated_ipc_attempt",
            details={"reason": "invalid_or_missing_session_token"},
        )
        service(store).execute(
            envelope("operator-someone-else", BOUND_SESSION, payload=mission_payload("m-audit-7"))
        )
        kinds = sorted(r["rejectionKind"] for r in store.list_security_rejections())
        assert kinds == ["unauthenticated_ipc_attempt", "unauthorized_envelope_identity"]
        # and the new row is exactly the identity refusal
        assert len(identity_rows(store)) == 1
    finally:
        store.close()


# --------------------------------------------------------------------------
# the audit trail is readable, not write-only
# --------------------------------------------------------------------------

def test_audit_surface_is_advertised():
    store = EventStore(":memory:")
    try:
        caps = RuntimeQueryService(store).handle({"op": "capabilities"})["result"]
        assert "security_rejections" in caps["queryOperations"]
    finally:
        store.close()


def test_read_projection_exposes_the_recorded_refusal_without_raw_identifiers():
    store = EventStore(":memory:")
    try:
        service(store).execute(
            envelope("operator-ATTACKER", "sess-ATTACKER", payload=mission_payload("m-audit-8"))
        )
        body = RuntimeQueryService(store).handle({"op": "security_rejections"})["result"]
        assert body["count"] == 1
        assert body["countsByKind"] == {"unauthorized_envelope_identity": 1}
        entry = body["rejections"][0]
        assert entry["rejectionKind"] == "unauthorized_envelope_identity"
        assert entry["details"]["mismatchedFields"] == ["operatorId", "sessionId"]
        # the read surface must not become the leak the write path avoided
        blob = json.dumps(body)
        assert "operator-ATTACKER" not in blob
        assert "sess-ATTACKER" not in blob
        assert BOUND_OPERATOR not in blob
        assert BOUND_SESSION not in blob
    finally:
        store.close()


def test_read_projection_filters_by_kind_and_can_omit_details():
    store = EventStore(":memory:")
    try:
        store.record_security_rejection(
            rejection_id="rej-other", rejection_kind="unauthenticated_ipc_attempt",
            details={"reason": "invalid_or_missing_session_token"},
        )
        service(store).execute(
            envelope("operator-x", BOUND_SESSION, payload=mission_payload("m-audit-9"))
        )
        ctl = RuntimeQueryService(store)

        filtered = ctl.handle(
            {"op": "security_rejections", "kind": "unauthorized_envelope_identity"})["result"]
        assert filtered["count"] == 1
        # the summary reports the whole observed distribution, not just the filter
        assert filtered["countsByKind"] == {
            "unauthenticated_ipc_attempt": 1, "unauthorized_envelope_identity": 1}

        lean = ctl.handle({"op": "security_rejections", "detail": False})["result"]
        assert lean["count"] == 2
        assert all("details" not in e for e in lean["rejections"])
        # the unconstrained column is called out rather than presented as an enum
        assert "unconstrained TEXT" in lean["note"]
    finally:
        store.close()
