"""Actual CAPT EventStore, ToolBroker, FileToolAdapter and generated-schema tests.

There is deliberately no fake RuntimeService, adapter dispatch, provider,
permission minting, or externally claimed completion in these tests.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from capt_runtime import commands
from capt_runtime.authority import require_authority
from capt_runtime.contracts import require
from capt_runtime.errors import AuthorityViolation, CapabilityDenied, IntegrityViolation, IdempotencyConflict
from capt_runtime.governed_decision_offering import GovernedDecisionOfferingService
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from capt_runtime.tool_broker import ToolBroker, tool_request_fingerprint
from capt_runtime.tools.adapters.file import FileToolAdapter
from capt_runtime.tools.registry import ToolRegistry

FIXED_NOW = "2026-10-19T12:00:00Z"

class Clock:
    def __init__(self):
        self.now = FIXED_NOW
    def __call__(self):
        return self.now
    def advance(self, seconds: int):
        dt = datetime.fromisoformat(self.now.replace("Z","+00:00"))
        self.now = (dt+timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")

def descriptor(display_name: str="File Inspection") -> dict:
    return {
        "schemaVersion":"1.0.0","toolId":"file.operations","displayName":display_name,
        "family":"filesystem","operations":["file.read"],"requiredCapabilities":[],
        "operationEffects":[{"operation":"file.read","effectClass":"pure_read_only"}],
        "terminalBackends":["local"],"platforms":["macos","linux"],
        "supportsTimeout":True,"supportsCancellation":True,
        "idempotencySupport":"broker_settled_replay","artifactOutputs":[]
    }

def registry_for(clock: Clock, display_name: str="File Inspection") -> ToolRegistry:
    registry=ToolRegistry()
    registry.register(
        descriptor(display_name),FileToolAdapter(),
        lambda: {
            "schemaVersion":"1.0.0","toolId":"file.operations",
            "status":"available","reason":"local file adapter installed",
            "checkedAt":clock(),
        },
    )
    return registry

def sample(tmp_path):
    file=tmp_path/"observed.txt"
    file.write_text("source content\n")
    clock=Clock()
    store=EventStore(str(tmp_path/"governed.db"))
    runtime=RuntimeService(store)
    registry=registry_for(clock)
    broker=ToolBroker(runtime,registry,now=clock,governed_offerings_enabled=True)
    svc=GovernedDecisionOfferingService(broker)
    request={
        "schemaVersion":"1.0.0","toolRequestId":"ql-file-read-request",
        "toolId":"file.operations","operation":"file.read",
        "arguments":[{"kind":"path","name":"path","value":str(file)}],
        "consequential":False,"grantId":None,"leaseId":None,
        "backendId":"local","targetIdentity":str(file),
        "filesystemScope":str(tmp_path),
        "idempotencyKey":"ql-proposed-file-read",
        "operationFingerprint":"sha256:"+"0"*64,
        "replayPolicy":"never","requestedAt":clock(),
    }
    request["operationFingerprint"]=tool_request_fingerprint(request)
    require("ToolRequest",request)
    return store,clock,svc,request

def issue_meta(svc,request,*,key="ql-offering-command-1",actor_kind="governance_kernel",ttl=60):
    fp=svc.issue_fingerprint(
        request,svc.registry.descriptor_digest(request["toolId"]),ttl,
        "governance-1",
    )
    return commands.command(
        command_id="command-"+key,idempotency_key=key,operation_fingerprint=fp,
        correlation_id="corr-"+key,actor_id="governance-1",
        actor_kind=actor_kind,issued_at=svc.broker._now(),
    )

def revoke_meta(svc,oid,*,key="ql-revoke-command-1",actor_kind="human"):
    return commands.command(
        command_id="command-"+key,idempotency_key=key,
        operation_fingerprint=svc.revoke_fingerprint(oid),
        correlation_id="corr-"+key,actor_id="operator-1",
        actor_kind=actor_kind,issued_at=svc.broker._now(),
    )

def test_real_ledger_issue_and_inspect_do_not_authorize_execution(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        result=svc.issue(request,issue_meta(svc,request))
        r=result["receipt"]
        assert r["toolId"]=="file.operations" and r["operation"]=="file.read"
        assert len(r["nonce"])==64
        assert result["command"]["status"]=="applied"
        require("DecisionOfferingReceipt",r)
        inspect=svc.inspect(r,request)
        assert inspect["reason"]=="OFFERING_IDENTITY_CURRENT_NOT_DISPATCHABLE"
        assert inspect["identityCurrent"]
        assert not inspect["dispatchAllowed"] and not inspect["completionVerified"]
        assert not inspect["externalWorldVerified"]
        events=store.read_stream(svc.stream_id(r["offeringId"]))
        assert len(events)==1 and events[0]["eventType"]=="DecisionOfferingIssued"
        assert store.verify_chain()
        assert (tmp_path/"observed.txt").read_text()=="source content\n"
    finally: store.close()

def test_issue_is_exact_idempotent_replay(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        meta=issue_meta(svc,request)
        a=svc.issue(request,meta)
        b=svc.issue(request,meta)
        assert a["receipt"]==b["receipt"]
        assert b["command"]["status"]=="idempotent"
        assert len(store.read_stream(svc.stream_id(a["receipt"]["offeringId"])))==1
    finally:store.close()

def test_forged_governance_actor_kind_is_refused(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        with pytest.raises(AuthorityViolation):
            svc.issue(request,issue_meta(svc,request,actor_kind="cognitive_plane"))
        assert store.head_sequence()==0
    finally:store.close()

def test_tampered_issuance_command_fingerprint_refused(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        meta=issue_meta(svc,request)
        meta["operationFingerprint"]="sha256:"+"0"*64
        with pytest.raises(IntegrityViolation):
            svc.issue(request,meta)
        assert store.head_sequence()==0
    finally:store.close()

def test_invalid_ttl_refused(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        for ttl in (0,301,True,1.5,-1):
            with pytest.raises(AuthorityViolation):
                svc.issue(request,issue_meta(svc,request),ttl_seconds=ttl)
    finally:store.close()

def test_expiry_uses_issuer_clock_not_caller_timestamp(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        result=svc.issue(request,issue_meta(svc,request,ttl=2),ttl_seconds=2)
        clock.advance(3)
        assert svc.inspect(result["receipt"],request)["reason"]=="RECEIPT_EXPIRED_OR_NOT_YET_VALID"
    finally:store.close()

def test_revoke_by_human_persists_event_and_denies(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        r=svc.issue(request,issue_meta(svc,request))["receipt"]
        meta=revoke_meta(svc,r["offeringId"])
        outcome=svc.revoke(r["offeringId"],meta)
        assert outcome["status"]=="applied"
        assert svc.inspect(r,request)["reason"]=="RECEIPT_REVOKED"
        state=store.require_state(svc.stream_id(r["offeringId"]))
        assert state["revokedBy"]=="operator-1" and state["status"]=="revoked"
        assert [e["eventType"] for e in store.read_stream(svc.stream_id(r["offeringId"]))]==[
            "DecisionOfferingIssued","DecisionOfferingRevoked"]
        assert svc.revoke(r["offeringId"],meta)["status"]=="idempotent"
    finally:store.close()

def test_revoke_by_model_refused(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        r=svc.issue(request,issue_meta(svc,request))["receipt"]
        with pytest.raises(AuthorityViolation):
            svc.revoke(r["offeringId"],revoke_meta(svc,r["offeringId"],actor_kind="cognitive_plane"))
        assert svc.inspect(r,request)["identityCurrent"]
    finally:store.close()

def test_nonce_tampering_detected(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        r=svc.issue(request,issue_meta(svc,request))["receipt"]
        altered=deepcopy(r);altered["nonce"]="0"*64
        assert svc.inspect(altered,request)["reason"]=="RECEIPT_DIGEST_MISMATCH"
    finally:store.close()

def test_mutated_request_fingerprint_fails_closed(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        r=svc.issue(request,issue_meta(svc,request))["receipt"]
        changed=deepcopy(request);changed["arguments"][0]["value"]=str(tmp_path/"wrong")
        assert not svc.inspect(r,changed)["identityCurrent"]
    finally:store.close()

def test_intervening_event_invalidates_exact_ledger_basis(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        a=svc.issue(request,issue_meta(svc,request))["receipt"]
        svc.issue(request,issue_meta(svc,request,key="ql-offering-command-2"))
        assert svc.inspect(a,request)["reason"]=="AUTHORITATIVE_LEDGER_ADVANCED"
    finally:store.close()

def test_registry_descriptor_change_invalidates(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        r=svc.issue(request,issue_meta(svc,request))["receipt"]
        newer=ToolBroker(RuntimeService(store),registry_for(clock,"Altered descriptor"),now=clock,governed_offerings_enabled=True)
        assessment=GovernedDecisionOfferingService(newer).inspect(r,request)
        assert assessment["reason"]=="DESCRIPTOR_VERSION_CHANGED"
    finally:store.close()

def test_durable_receipt_survives_runtime_restart(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        receipt=svc.issue(request,issue_meta(svc,request))["receipt"]
    finally:
        store.close()
    another=EventStore(str(tmp_path/"governed.db"))
    try:
        broker=ToolBroker(RuntimeService(another),registry_for(clock),now=clock,governed_offerings_enabled=True)
        value=GovernedDecisionOfferingService(broker).inspect(receipt,request)
        assert value["identityCurrent"]
        assert not value["dispatchAllowed"]
    finally:another.close()

def test_declared_grant_without_lease_refused(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        changed=dict(request,grantId="not-a-grant")
        changed["operationFingerprint"]=tool_request_fingerprint(changed)
        with pytest.raises(CapabilityDenied):
            svc.issue(changed,issue_meta(svc,changed))
    finally:store.close()

def test_actual_file_adapter_available_but_not_dispatched_by_offering(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        actual=svc.registry.adapter("file.operations")
        assert isinstance(actual,FileToolAdapter)
        svc.issue(request,issue_meta(svc,request))
        assert (tmp_path/"observed.txt").read_text()=="source content\n"
        # Confirm the actual installed adapter can perform a real read, when
        # directly exercised by this test; this is NOT an authority test.
        output=actual.execute(request)
        assert output["status"]=="succeeded"
    finally:store.close()

def test_exact_request_id_not_interchangeable_with_same_semantic_fingerprint(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        receipt=svc.issue(request,issue_meta(svc,request))["receipt"]
        modified={**request,"toolRequestId":"another-request"}
        # CAPT semantic fingerprint deliberately omits this request identifier.
        assert tool_request_fingerprint(modified)==request["operationFingerprint"]
        assert svc.inspect(receipt,modified)["reason"]=="EXACT_REQUEST_DIGEST_MISMATCH"
    finally:store.close()

def test_idempotency_and_replay_policy_cannot_be_substituted(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        receipt=svc.issue(request,issue_meta(svc,request))["receipt"]
        for key,value in (("idempotencyKey","changed-idempotency"),
                          ("requestedAt","2026-10-19T12:00:01Z")):
            changed={**request,key:value}
            assert not svc.inspect(receipt,changed)["identityCurrent"]
    finally:store.close()

def test_same_issue_command_cannot_replay_changed_request_identity(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        metadata=issue_meta(svc,request)
        svc.issue(request,metadata)
        modified={**request,"toolRequestId":"another-request"}
        with pytest.raises(IntegrityViolation):
            svc.issue(modified,metadata)
    finally:store.close()

def test_external_file_change_is_not_misreported_as_verified_world(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        receipt=svc.issue(request,issue_meta(svc,request))["receipt"]
        changed=tmp_path/"observed.txt"
        changed.write_text("external modification after receipt\n")
        # Ledger-only observation cannot detect an independent target write.
        result=svc.inspect(receipt,request)
        assert result["identityCurrent"] is True
        assert result["externalWorldVerified"] is False
        assert result["dispatchAllowed"] is False
    finally:store.close()

def test_broker_owned_api_issues_inspects_and_revokes_in_authoritative_store(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        broker=svc.broker
        minted=broker.issue_decision_offering(request,issue_meta(svc,request))
        receipt=minted["receipt"]
        assert store.aggregate_version(svc.stream_id(receipt["offeringId"]))==1
        verdict=broker.inspect_decision_offering(receipt,request)
        assert verdict["identityCurrent"] is True
        assert verdict["dispatchAllowed"] is False
        revoked=broker.revoke_decision_offering(
            receipt["offeringId"],revoke_meta(svc,receipt["offeringId"]))
        assert revoked["status"]=="applied"
        assert broker.inspect_decision_offering(receipt,request)["reason"]=="RECEIPT_REVOKED"
    finally:store.close()


def test_production_default_disables_offering_issuance_and_replay(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        default_broker=ToolBroker(RuntimeService(store),registry_for(clock),now=clock)
        default_service=GovernedDecisionOfferingService(default_broker)
        with pytest.raises(AuthorityViolation,match="DECISION_OFFERINGS_DISABLED"):
            default_broker.issue_decision_offering(request,issue_meta(svc,request))
        with pytest.raises(AuthorityViolation,match="DECISION_OFFERINGS_DISABLED"):
            default_service.issue(request,issue_meta(svc,request))
        assert store.head_sequence()==0
    finally:store.close()


def test_cross_connection_atomic_chain_basis_rejects_intervening_issue(tmp_path):
    """Two real SQLite EventStore connections: a read-before-write cannot win."""
    store,clock,svc,request=sample(tmp_path)
    second=EventStore(str(tmp_path/"governed.db"))
    try:
        before=store.head_chain()
        second_broker=ToolBroker(
            RuntimeService(second),registry_for(clock),now=clock,
            governed_offerings_enabled=True,
        )
        second_service=GovernedDecisionOfferingService(second_broker)
        another=second_service.issue(
            request,issue_meta(second_service,request,key="other-receipt-claim")
        )
        assert another["command"]["status"]=="applied"
        assert store.head_chain()!=before
        with pytest.raises(IntegrityViolation,match="LEDGER_BASIS_STALE_AT_COMMIT"):
            store.commit_command(
                [],"stale-commit-command",
                "sha256:"+"a"*64,"stale-commit-command",
                expected_chain_digest=before,
            )
        assert store.find_idempotent("stale-commit-command") is None
        assert store.verify_chain()
    finally:
        second.close()
        store.close()


def test_exact_predecessor_digest_is_committed_and_replay_does_not_write(tmp_path):
    store,clock,svc,request=sample(tmp_path)
    try:
        chain_before=store.head_chain()
        metadata=issue_meta(svc,request)
        first=svc.issue(request,metadata)
        assert first["receipt"]["ledgerBasisDigest"]==chain_before
        chain_after=store.head_chain()
        assert chain_after!=chain_before
        assert svc.issue(request,metadata)["command"]["status"]=="idempotent"
        assert store.head_chain()==chain_after
        assert store.verify_chain()
    finally:
        store.close()
