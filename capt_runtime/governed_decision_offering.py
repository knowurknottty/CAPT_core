"""Durable, governed decision-offering receipts for CAPT's ToolBroker.

This is an issuance and inspection boundary, NOT an execution grant.
Only runtime-validated command metadata from governance may issue. EventStore
owns durable state/versions and replay. No receipt authorizes dispatch.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, TYPE_CHECKING

from . import commands
from .authority import require_authority
from .contracts import digest, require
from .errors import AuthorityViolation, CapabilityDenied, IntegrityViolation
from .store import AppendRequest

if TYPE_CHECKING:
    from .tool_broker import ToolBroker

_MAX_TTL_SECONDS = 300

def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("naive time")
        return parsed.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError) as exc:
        raise AuthorityViolation("DECISION_OFFERING_CLOCK_INVALID") from exc

def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

def _offering_id(idempotency_key: str) -> str:
    # Not a bearer secret; the independently minted nonce is opaque.
    return "ql-" + hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:32]

class GovernedDecisionOfferingService:
    """RuntimeService/EventStore-backed receipt issuer; no adapter dispatch."""

    def __init__(self, broker: "ToolBroker"):
        self.broker = broker
        self.runtime = broker.runtime
        self.registry = broker.registry
        self.store = broker.store

    @staticmethod
    def stream_id(offering_id: str) -> str:
        return "decision_offering-" + offering_id

    @staticmethod
    def issue_fingerprint(request: dict, descriptor_digest: str, ttl_seconds: int, actor_id: str) -> str:
        return commands.fingerprint("issue_decision_offering", {
            "toolRequestFingerprint": request["operationFingerprint"],
            "toolRequestDigest": digest(request),
            "descriptorDigest": descriptor_digest,
            "ttlSeconds": ttl_seconds,
            "issuerActorId": actor_id,
        })

    @staticmethod
    def revoke_fingerprint(offering_id: str) -> str:
        return commands.fingerprint("revoke_decision_offering", {"offeringId": offering_id})

    def issue(self, request: dict, metadata: dict, *, ttl_seconds: int = 60) -> dict:
        """Create a governed *proposal* receipt, never a capability grant."""
        require("CommandMetadata", metadata)
        require_authority("issue_decision_offering", metadata["actor"]["kind"])
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= _MAX_TTL_SECONDS:
            raise AuthorityViolation("DECISION_OFFERING_TTL_OUT_OF_RANGE")
        # Live descriptor and request checked by the same broker that will later
        # own admission; a model cannot author its own tool descriptor.
        registration = self.broker._validate_request(request)
        desc_digest = registration["descriptorDigest"]
        expected_fp = self.issue_fingerprint(
            request, desc_digest, ttl_seconds, metadata["actor"]["actorId"]
        )
        if metadata["operationFingerprint"] != expected_fp:
            raise IntegrityViolation("DECISION_OFFERING_ISSUE_COMMAND_FINGERPRINT_MISMATCH")
        oid = _offering_id(metadata["idempotencyKey"])
        stream = self.stream_id(oid)
        if self.store.find_idempotent(metadata["idempotencyKey"]) is not None:
            result = self.runtime._commit([], metadata)
            state = self.store.require_state(stream)
            require("DecisionOfferingState", state)
            return {"receipt": state["receipt"], "command": result, "dispatchAllowed": False}

        now = _utc(self.broker._now())
        issued_at = _timestamp(now)
        expires_at = _timestamp(now + timedelta(seconds=ttl_seconds))
        # Check a bound lease at issue time, and again at inspection. A pure
        # read-only request without lease is not elevated into a grant.
        if request.get("grantId") or request.get("leaseId"):
            if not request.get("grantId") or not request.get("leaseId"):
                raise CapabilityDenied("DECISION_OFFERING_GRANT_LEASE_PAIR_REQUIRED",request.get("leaseId"))
            self.runtime.check_lease(
                request["grantId"], request["leaseId"],
                request["operation"], self.broker._scope_for(request), issued_at,
            )
        material = {
            "schemaVersion": "1.0.0",
            "offeringId": oid,
            "issuedBy": metadata["actor"]["actorId"],
            "issuedAt": issued_at,
            "expiresAt": expires_at,
            "nonce": secrets.token_hex(32),
            "ledgerBasisDigest": self.store.head_chain(),
            "toolId": request["toolId"],
            "operation": request["operation"],
            "operationFingerprint": request["operationFingerprint"],
            "toolRequestDigest": digest(request),
            "descriptorDigest": desc_digest,
            "grantId": request.get("grantId"),
            "leaseId": request.get("leaseId"),
        }
        receipt = {**material, "receiptDigest": digest(material)}
        require("DecisionOfferingReceipt", receipt)
        state = {"receipt": receipt, "status":"active","revokedAt":None,"revokedBy":None}
        require("DecisionOfferingState",state)
        if self.store.aggregate_version(stream):
            raise AuthorityViolation("DECISION_OFFERING_ID_COLLISION")
        envelope = commands.envelope(
            event_id=metadata["commandId"]+"-ev1", stream_id=stream,
            event_type="DecisionOfferingIssued",
            payload={"eventType":"DecisionOfferingIssued","receipt":receipt},
            metadata=metadata,occurred_at=issued_at
        )
        result = self.runtime._commit(
            [AppendRequest(stream,"decision_offering",0,envelope,state)],metadata
        )
        return {"receipt":receipt,"command":result,"dispatchAllowed":False}

    def revoke(self, offering_id: str, metadata:dict) -> dict:
        require("CommandMetadata",metadata)
        require_authority("revoke_decision_offering", metadata["actor"]["kind"])
        if metadata["operationFingerprint"]!=self.revoke_fingerprint(offering_id):
            raise IntegrityViolation("DECISION_OFFERING_REVOKE_COMMAND_FINGERPRINT_MISMATCH")
        if self.store.find_idempotent(metadata["idempotencyKey"]) is not None:
            return self.runtime._commit([],metadata)
        stream=self.stream_id(offering_id)
        version=self.store.aggregate_version(stream)
        state=self.store.require_state(stream)
        require("DecisionOfferingState",state)
        if state["status"] != "active":
            raise AuthorityViolation("DECISION_OFFERING_ALREADY_TERMINAL")
        revoked_at=_timestamp(_utc(self.broker._now()))
        nxt={**state,"status":"revoked","revokedAt":revoked_at,
             "revokedBy":metadata["actor"]["actorId"]}
        require("DecisionOfferingState",nxt)
        envelope=commands.envelope(
            event_id=metadata["commandId"]+"-ev1",stream_id=stream,
            event_type="DecisionOfferingRevoked",
            payload={"eventType":"DecisionOfferingRevoked",
                     "offeringId":offering_id,"revokedAt":revoked_at},
            metadata=metadata,occurred_at=revoked_at,
        )
        return self.runtime._commit(
            [AppendRequest(stream,"decision_offering",version,envelope,nxt)],metadata
        )

    def inspect(self, receipt:dict, request:dict) -> dict:
        """Fail closed against durable state; never conclude external effect."""
        def outcome(code: str, *, matched: bool=False, lease_checked: bool=False):
            return {
                "reason":code,"identityCurrent":matched,"liveLeaseChecked":lease_checked,
                "externalWorldVerified":False,"humanPresenceVerified":False,
                "dispatchAllowed":False,"completionVerified":False,
            }
        try:
            require("DecisionOfferingReceipt",receipt)
            require("ToolRequest",request)
            if digest({k:v for k,v in receipt.items() if k!="receiptDigest"})!=receipt["receiptDigest"]:
                return outcome("RECEIPT_DIGEST_MISMATCH")
            stream=self.stream_id(receipt["offeringId"])
            state=self.store.load_state(stream)
            if state is None or state["receipt"]!=receipt:
                return outcome("RECEIPT_NOT_IN_AUTHORITATIVE_LEDGER")
            if state["status"]!="active":
                return outcome("RECEIPT_REVOKED")
            now=_utc(self.broker._now())
            if now>=_utc(receipt["expiresAt"]) or now<_utc(receipt["issuedAt"]):
                return outcome("RECEIPT_EXPIRED_OR_NOT_YET_VALID")
            if (request["toolId"]!=receipt["toolId"]
                or request["operation"]!=receipt["operation"]
                or request["operationFingerprint"]!=receipt["operationFingerprint"]):
                return outcome("PROPOSAL_REQUEST_IDENTITY_MISMATCH")
            if digest(request)!=receipt["toolRequestDigest"]:
                return outcome("EXACT_REQUEST_DIGEST_MISMATCH")
            registration=self.broker._validate_request(request)
            if registration["descriptorDigest"]!=receipt["descriptorDigest"]:
                return outcome("DESCRIPTOR_VERSION_CHANGED")
            if (request.get("grantId")!=receipt.get("grantId")
                or request.get("leaseId")!=receipt.get("leaseId")):
                return outcome("CAPABILITY_IDENTITY_MISMATCH")
            # conservative fail-closed rule: the persisted issue event must
            # still be ledger head. This is *not* an external world readback.
            events=self.store.read_stream(stream)
            if len(events)!=1 or self.store.head_sequence()!=events[0]["globalSequence"]:
                return outcome("AUTHORITATIVE_LEDGER_ADVANCED")
            if request.get("grantId") or request.get("leaseId"):
                if not request.get("grantId") or not request.get("leaseId"):
                    return outcome("CAPABILITY_PAIR_MISSING")
                self.runtime.check_lease(
                    request["grantId"],request["leaseId"],
                    request["operation"],self.broker._scope_for(request),_timestamp(now)
                )
                return outcome("IDENTITY_AND_LEASE_CURRENT_NOT_DISPATCHABLE",
                               matched=True,lease_checked=True)
            return outcome("OFFERING_IDENTITY_CURRENT_NOT_DISPATCHABLE",matched=True)
        except (AuthorityViolation,CapabilityDenied,IntegrityViolation,KeyError,ValueError,
                TypeError,RuntimeError) as exc:
            return outcome("GOVERNED_OFFERING_VALIDATION_REFUSED")
