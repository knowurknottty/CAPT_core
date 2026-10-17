"""Reviewed, atomic, append-only mission disposition tests."""
from __future__ import annotations
import pytest
from capt_runtime import commands
from capt_runtime.errors import AuthorityViolation, ConcurrencyError
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from capt_runtime.replay import full_replay
from desktop.m1_command_service import RuntimeCommandService
from desktop.capt_runtime_service import RuntimeQueryService

WHEN = "2026-10-17T15:00:00Z"

def meta(k, actor="human"):
    return commands.command(
        command_id="cmd-"+k, idempotency_key="idem-"+k,
        operation_fingerprint=commands.fingerprint(k, {"key":k}),
        correlation_id="corr-reviewed-mission", actor_id="operator",
        actor_kind=actor, issued_at=WHEN,
    )

def mission_spec(mid):
    return {"schemaVersion":"1.0.0", "missionId":mid,
            "rawRequest":"test", "normalizedRequest":"test",
            "objectives":[{"objectiveId":"obj-1","statement":"test","priority":10}],
            "constraints":[], "successCriteria":[{"criterionId":"s-1","statement":"done","requiresVerification":True}],
            "terminationCriteria":[], "unresolvedAmbiguities":[], "createdAt":WHEN}

def task_spec(tid,mid):
    return {"taskId":tid,"missionId":mid,"title":"inspect","state":"pending","consequential":False,
            "capabilityRequirements":[],"attempt":0,"maxAttempts":1}

def approval_spec(mid,tid,rid):
    return {"schemaVersion":"1.0.0","requestId":rid,"missionId":mid,
            "taskId":tid,"requestedCapability":"cap.fs.read","resource":"/tmp",
            "operation":"RepositoryRead","scope":{"kind":"filesystem","rootPath":"/tmp","recursive":False},
            "riskClassification":"low","policyReason":"bounded","requestedBy":{"actorId":"exec","kind":"execution_plane"},
            "expiresAt":"2026-11-17T15:00:00Z","correlationId":"corr-reviewed-mission",
            "createdAt":WHEN}

def make():
    store=EventStore(":memory:")
    svc=RuntimeService(store)
    mid="m-review-test"
    svc.create_mission(mission_spec(mid),meta("mission"))
    return store,svc,mid

def apply(svc,mid,target,tag="apply"):
    preview=svc.mission_disposition_preview(mid,target)
    return svc.dispose_mission(mid,target,preview["expectedVersion"],
                               preview["previewDigest"],"Operator reviewed mission",meta(tag))

def test_draft_authorization_is_reviewed_and_idempotent():
    store,svc,mid=make()
    try:
        preview=RuntimeQueryService(store).handle(
            {"op":"mission_disposition_preview","missionId":mid,"target":"authorize"})["result"]
        assert not preview["blocked"]
        result=svc.dispose_mission(mid,"authorize",preview["expectedVersion"],
                                   preview["previewDigest"],"Human reviewed",meta("auth"))
        assert result["missionState"]=="authorized"
        assert store.require_state("mission-"+mid)["state"]=="authorized"
        replay=svc.dispose_mission(mid,"authorize",preview["expectedVersion"],
                                   preview["previewDigest"],"Human reviewed",meta("auth"))
        assert replay["status"]=="idempotent"
        assert full_replay(store).aggregates["mission-"+mid]==store.require_state("mission-"+mid)
    finally:store.close()

def test_cancel_atomic_with_task_and_requested_approval():
    store,svc,mid=make()
    try:
        tid="t-review-test";rid="approval-review-test"
        svc.create_task(task_spec(tid,mid),meta("task","cognitive_plane"))
        svc.request_human_approval(approval_spec(mid,tid,rid),meta("approval","execution_plane"))
        p=svc.mission_disposition_preview(mid,"cancel")
        assert not p["blocked"]
        result=apply(svc,mid,"cancel")
        assert result["settledEvents"]==3
        assert store.require_state("task-"+tid)["state"]=="cancelled"
        assert store.require_state("human_approval-"+rid)["state"]=="denied"
        assert store.require_state("mission-"+mid)["state"]=="cancelled"
        replay=full_replay(store)
        for prefix,name in [("mission-",mid),("task-",tid),("human_approval-",rid)]:
            assert replay.aggregates[prefix+name]==store.require_state(prefix+name)
    finally:store.close()

def test_stale_preview_never_mutates():
    store,svc,mid=make()
    try:
        p=svc.mission_disposition_preview(mid,"cancel")
        apply(svc,mid,"authorize","auth2")
        with pytest.raises(ConcurrencyError):
            svc.dispose_mission(mid,"cancel",p["expectedVersion"],p["previewDigest"],
                                "stale approval",meta("stale"))
        assert store.require_state("mission-"+mid)["state"]=="authorized"
    finally:store.close()

def test_completion_cannot_be_fabricated_without_claim():
    store,svc,mid=make()
    try:
        apply(svc,mid,"authorize","auth3")
        svc.transition_mission(mid,"executing","started",meta("exec"))
        p=svc.mission_disposition_preview(mid,"complete")
        assert "CLAIMGUARD_ACCEPTED_SUCCESSOR_REQUIRED" in p["blocked"]
        with pytest.raises(AuthorityViolation):
            svc.dispose_mission(mid,"complete",p["expectedVersion"],p["previewDigest"],
                                "no evidence",meta("false-complete"))
        assert store.require_state("mission-"+mid)["state"]=="executing"
    finally:store.close()

def test_approved_unconsumed_authority_blocks_cancellation():
    store,svc,mid=make()
    try:
        tid="t-review-test";rid="approval-review-test"
        svc.create_task(task_spec(tid,mid),meta("task4","cognitive_plane"))
        svc.request_human_approval(approval_spec(mid,tid,rid),meta("approval4","execution_plane"))
        svc.submit_human_approval_decision({
            "schemaVersion":"1.0.0","requestId":rid,"decision":"approve",
            "operatorId":"operator","decidedAt":WHEN,"idempotencyKey":"decision4",
            "correlationId":"corr-reviewed-mission"},meta("approved4"))
        p=svc.mission_disposition_preview(mid,"cancel")
        assert "APPROVED_AUTHORITY_REQUIRES_REVOCATION" in p["blocked"]
        with pytest.raises(AuthorityViolation):
            apply(svc,mid,"cancel","blocked4")
        assert store.require_state("task-"+tid)["state"]=="pending"
    finally:store.close()

def test_operator_command_requires_typed_confirmation():
    store,svc,mid=make()
    try:
        relay=RuntimeCommandService(store,"operator","session-test",runtime_service=svc)
        payload=svc.mission_disposition_preview(mid,"authorize")
        common={"missionId":mid,"target":"authorize","expectedVersion":payload["expectedVersion"],
                "previewDigest":payload["previewDigest"],"reason":"review","confirmedMissionId":"wrong"}
        def command(k,body):
            return {"commandId":k,"operatorId":"operator","sessionId":"session-test",
                    "schemaVersion":"1.0.0","correlationId":"corr",
                    "idempotencyKey":k,"timestamp":WHEN,
                    "op":"mission_disposition","payload":body}
        denied=relay.execute(command("cmd-wrong",common))
        assert denied["status"]=="rejected"
        common["confirmedMissionId"]=mid
        ok=relay.execute(command("cmd-right",common))
        assert ok["status"]=="accepted",ok
        assert store.require_state("mission-"+mid)["state"]=="authorized"
    finally:store.close()

def test_verified_historical_closure_is_atomic_and_replayable(tmp_path):
    """Reconcile a real ClaimGuard-accepted provider result without a new run."""
    from capt_runtime.composition import create_runtime
    from tests.capt_runtime.test_model_operator import (
        _seed_provider_result_awaiting_review, _envelope,
    )
    runtime = create_runtime(str(tmp_path / "verified-reconcile.db"))
    svc = runtime.service
    mid = "m-provider-reconcile"
    try:
        svc.create_mission(mission_spec(mid), meta("reconcile-mission"))
        apply(svc, mid, "authorize", "reconcile-authorize")
        ids = _seed_provider_result_awaiting_review(runtime, "reconcile")
        relay = RuntimeCommandService(runtime.store, "operator-x", "sess-1", runtime_service=svc)
        receipt = relay.execute(_envelope(
            "submit_provider_result_review",
            {"driverRunId": ids["driverRunId"], "disposition": "accept",
             "note": "Result meets criteria."}, key="reconcile-result-review",
        ))
        assert receipt["status"] == "accepted", receipt
        assert runtime.store.require_state("task-"+ids["taskId"])["state"] == "succeeded"
        preview = svc.mission_disposition_preview(mid, "reconcile_complete")
        assert preview["blocked"] == [], preview
        before_head=runtime.store.head_sequence()
        committed=svc.dispose_mission(mid, "reconcile_complete",
                                       preview["expectedVersion"], preview["previewDigest"],
                                       "Accept earlier verified completion", meta("reconcile-complete"))
        assert committed["missionState"] == "completed"
        assert committed["settledEvents"] == 2
        assert runtime.store.head_sequence() == before_head + 2
        events=runtime.store.read_stream("mission-"+mid)
        assert [(e["payload"]["fromState"],e["payload"]["toState"]) for e in events[-2:]] == [
            ("authorized","executing"),("executing","completed")]
        assert full_replay(runtime.store).aggregates["mission-"+mid] == runtime.store.require_state("mission-"+mid)
    finally:
        runtime.close()

def test_reviewed_cancel_revokes_prior_approved_authority_atomically():
    from capt_runtime.aggregates.human_approval import HumanApprovalAggregate
    from capt_runtime.errors import IllegalTransition
    store, svc, mid = make()
    try:
        tid, rid = "t-approved-review", "approval-approved-review"
        svc.create_task(task_spec(tid, mid), meta("revocation-task", "cognitive_plane"))
        request = approval_spec(mid, tid, rid)
        request["expiresAt"] = "2030-01-01T00:00:00Z"
        svc.request_human_approval(request, meta("revocation-request", "execution_plane"))
        svc.submit_human_approval_decision({
            "schemaVersion": "1.0.0", "requestId": rid, "decision": "approve",
            "operatorId": "operator", "decidedAt": WHEN,
            "idempotencyKey": "reviewed-prior-approval",
            "correlationId": "corr-reviewed-mission"
        }, meta("revocation-approve"))
        ordinary = svc.mission_disposition_preview(mid, "cancel")
        assert "APPROVED_AUTHORITY_REQUIRES_REVOCATION" in ordinary["blocked"]
        plan = svc.mission_disposition_preview(mid, "cancel_revoke")
        assert plan["blocked"] == []
        assert plan["approvedRevocationCount"] == 1
        before = store.head_sequence()
        receipt = svc.dispose_mission(mid, "cancel_revoke", plan["expectedVersion"],
                                      plan["previewDigest"], "Human cancelled this mission",
                                      meta("revocation-confirmed"))
        assert receipt["missionState"] == "cancelled"
        assert receipt["settledEvents"] == 3
        assert store.head_sequence() == before + 3
        assert store.require_state("mission-"+mid)["state"] == "cancelled"
        assert store.require_state("task-"+tid)["state"] == "cancelled"
        approval = store.require_state("human_approval-"+rid)
        assert approval["state"] == "revoked"
        assert approval["decision"] == "approve"  # immutable original decision provenance
        assert approval["revocation"]["operatorId"] == "operator"
        assert approval["revocation"]["reason"] == "Human cancelled this mission"
        with pytest.raises(IllegalTransition):
            HumanApprovalAggregate.consume(approval, "use-after-revocation", WHEN)
        replay = full_replay(store)
        for sid in ("mission-"+mid,"task-"+tid,"human_approval-"+rid):
            assert replay.aggregates[sid] == store.require_state(sid)
    finally: store.close()


def test_reviewed_revocation_rejects_external_commitments():
    store, svc, mid = make()
    try:
        tid, rid = "t-with-external", "approval-with-external"
        svc.create_task(task_spec(tid,mid),meta("external-task","cognitive_plane"))
        request = approval_spec(mid,tid,rid)
        request["externalCommitments"] = [{"kind": "external_agreement", "digest": "sha256:" + "a" * 64}]
        svc.request_human_approval(request,meta("external-request","execution_plane"))
        svc.submit_human_approval_decision({
            "schemaVersion":"1.0.0","requestId":rid,"decision":"approve",
            "operatorId":"operator","decidedAt":WHEN,
            "idempotencyKey":"external-approved","correlationId":"corr-reviewed-mission"
        },meta("external-approval"))
        preview=svc.mission_disposition_preview(mid,"cancel_revoke")
        assert "EXTERNAL_COMMITMENTS_RECONCILIATION_REQUIRED" in preview["blocked"]
        with pytest.raises(AuthorityViolation):
            svc.dispose_mission(mid,"cancel_revoke",preview["expectedVersion"],
                                preview["previewDigest"],"not safe",meta("external-refused"))
        assert store.require_state("human_approval-"+rid)["state"]=="approved"
    finally:store.close()
