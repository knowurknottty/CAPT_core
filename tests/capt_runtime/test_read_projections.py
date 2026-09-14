"""Read projections: approvals, missions, tasks, checkpoints.

These cover the gap where CAPT accepted ~26 command ops that create and
transition governed state but exposed almost no way to read it back — an
operator could command a mission or a checkpoint and then not inspect it, and
confirming a checkpoint persisted meant opening the ledger file directly.

Two properties are asserted throughout:

1. The stored ``state`` is reported VERBATIM. A projection may derive extra
   fields but may never rewrite or launder state.
2. Derived fields are named as derived. In particular a past-due approval still
   reads ``approved`` because CAPT never drives the ``expired`` transition
   (``HumanApprovalAggregate.mark_expired`` has no caller), so the projection
   reports the stored state and adds ``derivedStale`` beside it.
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

from capt_runtime import commands
from capt_runtime.checkpoint import create_checkpoint
from capt_runtime.errors import AuthorityViolation, ContractViolation
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from desktop.capt_runtime_service import RuntimeQueryService

import pytest

POLICY_DIGEST = "sha256:" + "c" * 64


def meta(command_id: str, actor_kind: str, key: str) -> dict:
    return commands.command(
        command_id=command_id,
        idempotency_key=key,
        operation_fingerprint="sha256:" + "b" * 64,
        correlation_id="corr",
        actor_id="operator",
        actor_kind=actor_kind,
        issued_at="2026-08-16T00:00:00Z",
    )


def approval_request(request_id: str, expires_at: str, task_id: str = "t-1") -> dict:
    return {
        "schemaVersion": "1.0.0",
        "requestId": request_id,
        "missionId": "m-1",
        "taskId": task_id,
        "requestedCapability": "cap.fs.read",
        "resource": "/tmp",
        "operation": "ModelOperatorInspection",
        "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": True},
        "riskClassification": "low",
        "policyReason": "Approve exact model-visible prompt.",
        "requestedBy": {"actorId": "exec-1", "kind": "execution_plane"},
        "expiresAt": expires_at,
        "correlationId": "corr",
        "createdAt": "2026-08-16T00:00:00Z",
        "promptAssemblyDigest": "sha256:" + "a" * 64,
    }


def approve(svc: RuntimeService, request_id: str) -> None:
    svc.submit_human_approval_decision(
        {
            "schemaVersion": "1.0.0",
            "requestId": request_id,
            "decision": "approve",
            "operatorId": "operator",
            "decidedAt": "2026-08-16T00:00:01Z",
            "note": None,
            "idempotencyKey": "approve-" + request_id,
            "correlationId": "corr",
            "sessionId": "sess",
        },
        meta("approve-" + request_id, "human", "approve-" + request_id),
    )


def mission_spec(mission_id: str) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "missionId": mission_id,
        "rawRequest": "test mission",
        "normalizedRequest": "test mission",
        "objectives": [{"objectiveId": "obj-1", "statement": "test", "priority": 10}],
        "constraints": [],
        "successCriteria": [
            {"criterionId": "sc-1", "statement": "done", "requiresVerification": False}
        ],
        "terminationCriteria": [],
        "unresolvedAmbiguities": [],
        "createdAt": "2026-08-16T10:00:00Z",
    }


def task_spec(task_id: str, mission_id: str, consequential: bool = False) -> dict:
    return {
        "taskId": task_id,
        "missionId": mission_id,
        "title": "inspect governed target",
        "state": "pending",
        "consequential": consequential,
        "capabilityRequirements": [
            {
                "requirementId": "req-" + task_id,
                "capabilityId": "cap.repository.read",
                "operations": ["repository.read"],
                "scope": {"kind": "repository", "repositoryId": "repo-1", "refPattern": "main"},
            }
        ],
        "attempt": 0,
        "maxAttempts": 3,
    }


# --------------------------------------------------------------------------
# capabilities advertisement
# --------------------------------------------------------------------------

def test_read_projections_are_advertised():
    """A client must be able to discover the read surface, not guess at it."""
    store = EventStore(":memory:")
    try:
        result = RuntimeQueryService(store).handle({"op": "capabilities"})
        assert result["ok"] is True
        ops = set(result["result"]["queryOperations"])
        for op in ("approvals", "missions", "tasks", "checkpoints"):
            assert op in ops, op
    finally:
        store.close()


# --------------------------------------------------------------------------
# missions + tasks
# --------------------------------------------------------------------------

def test_missions_projection_reports_state_and_derives_task_counts():
    store = EventStore(":memory:")
    try:
        svc = RuntimeService(store)
        svc.create_mission(mission_spec("m-proj-1"), meta("create-m-proj-1", "human", "m-proj-1"))
        svc.create_task(task_spec("t-1", "m-proj-1"), meta("create-t-1", "cognitive_plane", "t-1"))
        svc.create_task(task_spec("t-2", "m-proj-1"), meta("create-t-2", "cognitive_plane", "t-2"))
        svc.transition_task("t-2", "ready", "deps satisfied",
                            meta("t-2-ready", "execution_plane", "t-2-ready"))

        result = RuntimeQueryService(store).handle({"op": "missions"})
        assert result["ok"] is True
        body = result["result"]
        assert body["count"] == 1
        mission = body["missions"][0]
        # stored state is verbatim
        assert mission["missionId"] == "m-proj-1"
        assert mission["state"] == "draft"
        # derived, and labelled as such in the response note
        assert mission["taskCount"] == 2
        assert mission["taskStates"] == {"pending": 1, "ready": 1}
        assert "ordered by missionId" in body["note"]

        scoped = RuntimeQueryService(store).handle(
            {"op": "missions", "state": "completed"})
        assert scoped["result"]["count"] == 0
        # the summary still reports the true distribution
        assert scoped["result"]["countsByState"] == {"draft": 1}
    finally:
        store.close()


def test_tasks_projection_scopes_by_mission_and_state():
    store = EventStore(":memory:")
    try:
        svc = RuntimeService(store)
        svc.create_mission(mission_spec("m-proj-2"), meta("create-m-proj-2", "human", "m-proj-2"))
        svc.create_task(task_spec("t-a", "m-proj-2"), meta("create-t-a", "cognitive_plane", "t-a"))
        svc.create_task(task_spec("t-b", "m-proj-2", consequential=True),
                        meta("create-t-b", "cognitive_plane", "t-b"))
        svc.transition_task("t-b", "ready", "deps satisfied",
                            meta("t-b-ready", "execution_plane", "t-b-ready"))

        svc_ctl = RuntimeQueryService(store)
        all_tasks = svc_ctl.handle({"op": "tasks", "missionId": "m-proj-2"})["result"]
        assert all_tasks["count"] == 2
        assert all_tasks["countsByState"] == {"pending": 1, "ready": 1}

        ready = svc_ctl.handle({"op": "tasks", "state": "ready"})["result"]
        assert ready["count"] == 1
        entry = ready["tasks"][0]
        assert entry["taskId"] == "t-b"
        assert entry["state"] == "ready"
        assert entry["consequential"] is True
        assert entry["capabilityRequirementCount"] == 1
        assert entry["resultRefCount"] == 0
    finally:
        store.close()


# --------------------------------------------------------------------------
# approvals — the derived-expiry contract
# --------------------------------------------------------------------------

def test_approved_then_window_passed_reads_approved_but_is_derived_stale():
    """The live defect, pinned.

    CAPT never drives the `expired` transition, so an approval that was approved
    while its window was still open, and then never consumed, reads `approved`
    forever. The projection must report exactly that — stored state verbatim —
    and surface staleness only as a derived field.

    The window must be OPEN at decision time, because `decide()` refuses to
    approve a past-due request (see the lazy-expiry test below). Hence the
    expiry sits shortly AFTER decidedAt and long before today.
    """
    store = EventStore(":memory:")
    try:
        svc = RuntimeService(store)
        svc.request_human_approval(
            approval_request("r-past", "2026-08-16T00:00:30Z"),
            meta("request-r-past", "execution_plane", "r-past"),
        )
        approve(svc, "r-past")  # decidedAt 2026-08-16T00:00:01Z -> inside window

        body = RuntimeQueryService(store).handle({"op": "approvals"})["result"]
        assert body["count"] == 1
        entry = body["approvals"][0]
        # stored state: still approved, never transitioned to expired
        assert entry["state"] == "approved"
        assert entry["decision"] == "approve"
        assert entry["consumedAt"] is None
        # derived against the current clock
        assert entry["expired"] is True
        assert entry["derivedStale"] is True
        assert entry["awaitingConsumption"] is True
        assert body["derivedStale"] == 1
        assert "NOT state" in body["note"]
    finally:
        store.close()


def test_lazy_expiry_refuses_to_approve_a_past_due_request():
    """Expiry is enforced as a REFUSAL, not as a state transition.

    `HumanApprovalAggregate.mark_expired` has no caller and no
    `HumanApprovalExpired` event exists, so the `expired` state is never
    reached. What actually holds the boundary is this refusal inside
    `decide()` — which is precisely why the projection must derive staleness
    instead of reading a state the runtime never writes.
    """
    store = EventStore(":memory:")
    try:
        svc = RuntimeService(store)
        svc.request_human_approval(
            approval_request("r-late", "2020-01-01T00:00:00Z"),
            meta("request-r-late", "execution_plane", "r-late"),
        )
        with pytest.raises(AuthorityViolation):
            approve(svc, "r-late")

        body = RuntimeQueryService(store).handle({"op": "approvals"})["result"]
        entry = body["approvals"][0]
        # never `expired` — still `requested`, and past due
        assert entry["state"] == "requested"
        assert entry["expired"] is True
        assert entry["awaitingDecision"] is True
    finally:
        store.close()


def test_future_dated_approval_is_not_stale_and_filters_work():
    store = EventStore(":memory:")
    try:
        svc = RuntimeService(store)
        svc.request_human_approval(
            approval_request("r-future", "2030-01-01T00:00:00Z"),
            meta("request-r-future", "execution_plane", "r-future"),
        )
        svc.request_human_approval(
            approval_request("r-past2", "2020-01-01T00:00:00Z", task_id="t-2"),
            meta("request-r-past2", "execution_plane", "r-past2"),
        )
        approve(svc, "r-future")

        ctl = RuntimeQueryService(store)
        body = ctl.handle({"op": "approvals"})["result"]
        by_id = {e["requestId"]: e for e in body["approvals"]}

        future = by_id["r-future"]
        assert future["state"] == "approved"
        assert future["expired"] is False
        assert future["derivedStale"] is False
        assert future["expiresInSeconds"] > 0

        # r-past2 is still `requested` (never decided) and past due
        pending = by_id["r-past2"]
        assert pending["state"] == "requested"
        assert pending["awaitingDecision"] is True
        assert pending["expired"] is True

        # awaiting-decision and awaiting-consumption are distinguished
        assert body["awaitingDecision"] == 1
        assert body["awaitingConsumption"] == 1
        assert body["countsByStoredState"] == {"requested": 1, "approved": 1}

        # filters
        only_requested = ctl.handle({"op": "approvals", "state": "requested"})["result"]
        assert [e["requestId"] for e in only_requested["approvals"]] == ["r-past2"]
        by_task = ctl.handle({"op": "approvals", "missionId": "m-nope"})["result"]
        assert by_task["count"] == 0
    finally:
        store.close()


def test_malformed_expiry_cannot_be_stored_and_is_never_read_as_expired():
    """Two guards, both pinned.

    The contract's timestamp pattern means a malformed `expiresAt` cannot even
    be written, so the derivation's defensive branch is unreachable from real
    state. It is still tested directly: a legacy or hand-edited row must not be
    silently read as "expired".
    """
    store = EventStore(":memory:")
    try:
        svc = RuntimeService(store)
        with pytest.raises(ContractViolation):
            svc.request_human_approval(
                approval_request("r-bad", "not-a-timestamp"),
                meta("request-r-bad", "execution_plane", "r-bad"),
            )
    finally:
        store.close()

    derived = RuntimeQueryService._derive_expiry("not-a-timestamp")
    assert derived["expired"] is None
    assert derived["expiryUnparseable"] is True
    assert RuntimeQueryService._derive_expiry(None)["expired"] is None
    assert RuntimeQueryService._derive_expiry(None)["expiresInSeconds"] is None


# --------------------------------------------------------------------------
# checkpoints — the recovery surface that had no read op
# --------------------------------------------------------------------------

def test_checkpoints_projection_lists_and_reverifies_integrity():
    store = EventStore(":memory:")
    try:
        assert RuntimeQueryService(store).handle({"op": "checkpoints"})["result"]["count"] == 0

        create_checkpoint(
            store,
            checkpoint_id="cp-proj-1",
            created_at="2026-08-16T00:00:00Z",
            policy_bundle_digest=POLICY_DIGEST,
        )
        body = RuntimeQueryService(store).handle({"op": "checkpoints"})["result"]
        assert body["count"] == 1
        entry = body["checkpoints"][0]
        assert entry["checkpointId"] == "cp-proj-1"
        assert entry["createdAt"] == "2026-08-16T00:00:00Z"
        assert entry["integrityDigest"].startswith("sha256:")
        # integrity is recomputed, not read from the stored digest
        assert entry["integrityVerified"] is True
        # derived-from-open-reservations, never caller-supplied
        assert entry["recoveryState"] == "clean"
        assert entry["canDispatchConsequential"] is True
        assert "does NOT advance the head" in body["note"]
    finally:
        store.close()


def test_checkpoint_projection_reports_detail_false_without_unsealing():
    store = EventStore(":memory:")
    try:
        create_checkpoint(
            store,
            checkpoint_id="cp-proj-2",
            created_at="2026-08-16T00:00:00Z",
            policy_bundle_digest=POLICY_DIGEST,
        )
        body = RuntimeQueryService(store).handle(
            {"op": "checkpoints", "detail": False})["result"]
        entry = body["checkpoints"][0]
        assert entry["checkpointId"] == "cp-proj-2"
        assert "recoveryState" not in entry
        assert "integrityVerified" not in entry
    finally:
        store.close()


def test_store_list_checkpoints_orders_newest_first():
    store = EventStore(":memory:")
    try:
        for index, seq in enumerate(("cp-a", "cp-b")):
            create_checkpoint(
                store,
                checkpoint_id=seq,
                created_at="2026-08-16T00:0%d:00Z" % index,
                policy_bundle_digest=POLICY_DIGEST,
            )
        listed = store.list_checkpoints(limit=10)
        assert [row["checkpointId"] for row in listed] == ["cp-b", "cp-a"]
        assert store.list_checkpoints(limit=1)[0]["checkpointId"] == "cp-b"
        assert store.list_checkpoints(limit=0) == []
    finally:
        store.close()
