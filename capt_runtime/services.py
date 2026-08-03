"""Application services: the only cross-aggregate mutation path (ADR-0103).

Each method performs the eight-step transaction rule:
    validate -> load with expected version -> check invariant -> transition
    -> persist state+event in ONE transaction -> commit -> dispatch via outbox.

Aggregates never call each other. Any change touching two aggregates is an
explicit service method here, so cross-aggregate coupling is enumerable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import commands
from .aggregates import (
    CapabilityAggregate,
    ClaimAggregate,
    DriverRunAggregate,
    HumanApprovalAggregate,
    MissionAggregate,
    TaskAggregate,
)
from .authority import require_authority
from .contracts import require
from .errors import AuthorityViolation, ConcurrencyError
from .store import AppendRequest, EventStore


class RuntimeService(object):
    """Command surface for the M0-A runtime."""

    def __init__(self, store: EventStore) -> None:
        self.store = store

    # -- helpers -----------------------------------------------------------

    def _commit(
        self,
        appends: List[AppendRequest],
        metadata: Dict[str, Any],
        dispatch: bool = True,
    ) -> Dict[str, Any]:
        result = self.store.commit_command(
            appends,
            metadata["idempotencyKey"],
            metadata["operationFingerprint"],
            metadata["commandId"],
        )
        if dispatch:
            # Strictly AFTER commit returns (spec invariant 10).
            self.store.dispatch()
        return result

    # -- mission -----------------------------------------------------------

    def create_mission(
        self, spec: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("MissionSpec", spec)
        require("CommandMetadata", metadata)
        require_authority("create_mission", metadata["actor"]["kind"])

        stream = MissionAggregate.stream_id(spec["missionId"])
        expected = self.store.aggregate_version(stream)
        state = MissionAggregate.create(spec)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="MissionCreated",
            payload={"eventType": "MissionCreated", "missionSpec": spec},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=spec["missionId"],
        )
        return self._commit(
            [AppendRequest(stream, MissionAggregate.KIND, expected, event, state)],
            metadata,
        )

    def evaluate_policy(
        self, decision: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("PolicyDecision", decision)
        require("CommandMetadata", metadata)
        require_authority("evaluate_policy", metadata["actor"]["kind"])

        # A PolicyDecision must be authored by the governance kernel itself,
        # not merely submitted by one.
        if decision["decidedBy"]["kind"] != "governance_kernel":
            raise AuthorityViolation(
                "PolicyDecision.decidedBy must be a governance_kernel actor, got %r"
                % decision["decidedBy"]["kind"]
            )

        mission_id = decision["missionId"]
        stream = MissionAggregate.stream_id(mission_id)
        expected = self.store.aggregate_version(stream)
        state = MissionAggregate.record_policy_decision(
            self.store.require_state(stream), decision["policyDecisionId"]
        )
        if state["state"] == "draft" and decision["effect"] in (
            "allow",
            "allow_with_conditions",
        ):
            state = MissionAggregate.transition(state, "authorized")

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="PolicyEvaluated",
            payload={"eventType": "PolicyEvaluated", "policyDecision": decision},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=mission_id,
        )
        return self._commit(
            [AppendRequest(stream, MissionAggregate.KIND, expected, event, state)],
            metadata,
        )

    def transition_mission(
        self, mission_id: str, to_state: str, reason: str, metadata: Dict[str, Any],
        expected_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        require("CommandMetadata", metadata)
        stream = MissionAggregate.stream_id(mission_id)
        actual = self.store.aggregate_version(stream)
        expected = actual if expected_version is None else expected_version
        if expected != actual:
            raise ConcurrencyError(
                "mission %s expected version %d but actual is %d"
                % (mission_id, expected, actual)
            )
        current = self.store.require_state(stream)
        state = MissionAggregate.transition(current, to_state)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="MissionStateChanged",
            payload={
                "eventType": "MissionStateChanged",
                "fromState": current["state"],
                "toState": to_state,
                "reason": reason,
            },
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=mission_id,
        )
        return self._commit(
            [AppendRequest(stream, MissionAggregate.KIND, expected, event, state)],
            metadata,
        )

    # -- task --------------------------------------------------------------

    def create_task(
        self, node: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("TaskNode", node)
        require("CommandMetadata", metadata)
        require_authority("plan_tasks", metadata["actor"]["kind"])

        stream = TaskAggregate.stream_id(node["taskId"])
        expected = self.store.aggregate_version(stream)
        state = TaskAggregate.create(node)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="TaskCreated",
            payload={"eventType": "TaskCreated", "task": node},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=node["missionId"],
            task_id=node["taskId"],
        )
        return self._commit(
            [AppendRequest(stream, TaskAggregate.KIND, expected, event, state)], metadata
        )

    def transition_task(
        self,
        task_id: str,
        to_state: str,
        reason: str,
        metadata: Dict[str, Any],
        driver_id: Optional[str] = None,
        expected_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        require("CommandMetadata", metadata)
        require_authority("transition_task", metadata["actor"]["kind"])

        stream = TaskAggregate.stream_id(task_id)
        actual = self.store.aggregate_version(stream)
        expected = actual if expected_version is None else expected_version
        current = self.store.require_state(stream)
        state = TaskAggregate.transition(current, to_state, driver_id)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="TaskTransitioned",
            payload={
                "eventType": "TaskTransitioned",
                "taskId": task_id,
                "fromState": current["state"],
                "toState": to_state,
                "reason": reason,
            },
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=current["missionId"],
            task_id=task_id,
        )
        return self._commit(
            [AppendRequest(stream, TaskAggregate.KIND, expected, event, state)], metadata
        )

    # -- capability --------------------------------------------------------

    def issue_grant(
        self, grant: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Only the governance kernel may create authority (invariant 1/2)."""
        require("CapabilityGrant", grant)
        require("CommandMetadata", metadata)
        require_authority("issue_grant", metadata["actor"]["kind"])

        if grant["issuedBy"]["kind"] != "governance_kernel":
            raise AuthorityViolation(
                "CapabilityGrant.issuedBy must be a governance_kernel actor, got %r"
                % grant["issuedBy"]["kind"]
            )

        # The grant must cite a PolicyDecision this runtime actually recorded.
        # A grant citing an unknown decision is unauthorized even if its own
        # fields validate (ledger Finding I).
        if not self._policy_decision_exists(grant["policyDecisionId"]):
            raise AuthorityViolation(
                "grant %s cites unknown policy decision %s"
                % (grant["grantId"], grant["policyDecisionId"])
            )

        stream = CapabilityAggregate.stream_id(grant["grantId"])
        expected = self.store.aggregate_version(stream)
        state = CapabilityAggregate.grant(grant)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="CapabilityGranted",
            payload={"eventType": "CapabilityGranted", "grant": grant},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
        )
        return self._commit(
            [AppendRequest(stream, CapabilityAggregate.KIND, expected, event, state)],
            metadata,
        )

    def _policy_decision_exists(self, policy_decision_id: str) -> bool:
        for env in self.store.read_events():
            payload = env["payload"]
            if payload["eventType"] == "PolicyEvaluated":
                if payload["policyDecision"]["policyDecisionId"] == policy_decision_id:
                    return True
        return False

    def activate_lease(
        self, lease: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("CapabilityLease", lease)
        require("CommandMetadata", metadata)
        require_authority("activate_lease", metadata["actor"]["kind"])

        stream = CapabilityAggregate.stream_id(lease["grantId"])
        expected = self.store.aggregate_version(stream)
        state = CapabilityAggregate.activate_lease(
            self.store.require_state(stream), lease
        )

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="CapabilityLeaseActivated",
            payload={"eventType": "CapabilityLeaseActivated", "lease": lease},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=lease["missionId"],
            task_id=lease["taskId"],
        )
        return self._commit(
            [AppendRequest(stream, CapabilityAggregate.KIND, expected, event, state)],
            metadata,
        )

    def reserve_use(
        self, grant_id: str, reservation: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reserve one consequential use. Revalidates the lease first."""
        require("CapabilityReservation", reservation)
        require("CommandMetadata", metadata)
        require_authority("reserve_use", metadata["actor"]["kind"])

        stream = CapabilityAggregate.stream_id(grant_id)
        expected = self.store.aggregate_version(stream)
        state = CapabilityAggregate.reserve(
            self.store.require_state(stream), reservation, metadata["issuedAt"]
        )

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="CapabilityUseReserved",
            payload={"eventType": "CapabilityUseReserved", "reservation": reservation},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
        )
        return self._commit(
            [AppendRequest(stream, CapabilityAggregate.KIND, expected, event, state)],
            metadata,
        )

    def finalize_use(
        self, grant_id: str, consumption: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("CapabilityConsumptionRecord", consumption)
        require("CommandMetadata", metadata)
        require_authority("finalize_use", metadata["actor"]["kind"])

        stream = CapabilityAggregate.stream_id(grant_id)
        expected = self.store.aggregate_version(stream)
        state = CapabilityAggregate.finalize(self.store.require_state(stream), consumption)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="CapabilityUseFinalized",
            payload={"eventType": "CapabilityUseFinalized", "consumption": consumption},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
        )
        return self._commit(
            [AppendRequest(stream, CapabilityAggregate.KIND, expected, event, state)],
            metadata,
        )

    def revoke(
        self, grant_id: str, revocation: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("CapabilityRevocation", revocation)
        require("CommandMetadata", metadata)
        require_authority("revoke", metadata["actor"]["kind"])

        stream = CapabilityAggregate.stream_id(grant_id)
        expected = self.store.aggregate_version(stream)
        state = CapabilityAggregate.revoke(self.store.require_state(stream), revocation)

        event_type = (
            "CapabilityGrantRevoked"
            if revocation["targetKind"] == "grant"
            else "CapabilityLeaseRevoked"
        )
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type=event_type,
            payload={"eventType": event_type, "revocation": revocation},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
        )
        return self._commit(
            [AppendRequest(stream, CapabilityAggregate.KIND, expected, event, state)],
            metadata,
        )

    def check_lease(
        self, grant_id: str, lease_id: str, operation: str, scope: Dict[str, Any], now: str
    ) -> None:
        """Revalidate immediately before a consequential side effect.

        Reads live state, never a cached copy. Raises CapabilityDenied.
        """
        CapabilityAggregate.check_lease(
            self.store.require_state(CapabilityAggregate.stream_id(grant_id)),
            lease_id,
            operation,
            scope,
            now,
        )

    # -- driver run (state model only; no driver is contacted) -------------

    def create_driver_run(
        self, run: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("DriverRun", run)
        require("CommandMetadata", metadata)

        stream = DriverRunAggregate.stream_id(run["driverRunId"])
        expected = self.store.aggregate_version(stream)
        state = DriverRunAggregate.create(run)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="DriverRunCreated",
            payload={"eventType": "DriverRunCreated", "driverRun": run},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=run["missionId"],
            task_id=run["taskId"],
        )
        return self._commit(
            [AppendRequest(stream, DriverRunAggregate.KIND, expected, event, state)],
            metadata,
        )

    def transition_driver_run(
        self, driver_run_id: str, to_state: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("CommandMetadata", metadata)
        stream = DriverRunAggregate.stream_id(driver_run_id)
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)
        state = DriverRunAggregate.transition(current, to_state)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="DriverRunStateChanged",
            payload={
                "eventType": "DriverRunStateChanged",
                "driverRunId": driver_run_id,
                "fromState": current["state"],
                "toState": to_state,
            },
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
        )
        return self._commit(
            [AppendRequest(stream, DriverRunAggregate.KIND, expected, event, state)],
            metadata,
        )

    # -- human approval (M1 governed operator actions) --------------------

    def request_human_approval(
        self, request: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("HumanApprovalRequest", request)
        require("CommandMetadata", metadata)
        require_authority("request_human_approval", metadata["actor"]["kind"])

        stream = HumanApprovalAggregate.stream_id(request["requestId"])
        expected = self.store.aggregate_version(stream)
        state = HumanApprovalAggregate.create(request)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="HumanApprovalRequested",
            payload={"eventType": "HumanApprovalRequested", "request": request},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=request["missionId"],
            task_id=request["taskId"],
        )
        return self._commit(
            [AppendRequest(stream, HumanApprovalAggregate.KIND, expected, event, state)],
            metadata,
        )

    def submit_human_approval_decision(
        self,
        decision: Dict[str, Any],
        metadata: Dict[str, Any],
        now: Optional[str] = None,
    ) -> Dict[str, Any]:
        require("HumanApprovalDecision", decision)
        require("CommandMetadata", metadata)
        require_authority("submit_human_approval_decision", metadata["actor"]["kind"])

        stream = HumanApprovalAggregate.stream_id(decision["requestId"])
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)
        decided_at = decision.get("decidedAt") or metadata["issuedAt"]
        state = HumanApprovalAggregate.decide(current, decision, now or decided_at)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="HumanApprovalDecided",
            payload={"eventType": "HumanApprovalDecided", "decision": decision},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=current["missionId"],
            task_id=current["taskId"],
        )
        return self._commit(
            [AppendRequest(stream, HumanApprovalAggregate.KIND, expected, event, state)],
            metadata,
        )

    # -- cancellation (M1) ------------------------------------------------

    def cancel_task(
        self, task_id: str, reason: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("CommandMetadata", metadata)
        require_authority("cancel_task", metadata["actor"]["kind"])
        return self.transition_task(task_id, "cancelled", reason, metadata)

    def cancel_driver_run(
        self, driver_run_id: str, reason: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("CommandMetadata", metadata)
        require_authority("cancel_driver_run", metadata["actor"]["kind"])
        return self.transition_driver_run(driver_run_id, "cancelled", metadata)

    def propose_claim(
        self, claim: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("ClaimRecord", claim)
        require("CommandMetadata", metadata)
        require_authority("propose_claim", metadata["actor"]["kind"])

        if claim["promotionState"] != "proposed":
            raise AuthorityViolation(
                "a new claim must enter as 'proposed', got %r" % claim["promotionState"]
            )

        stream = ClaimAggregate.stream_id(claim["claimId"])
        expected = self.store.aggregate_version(stream)
        state = ClaimAggregate.propose(claim)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="ClaimCreated",
            payload={"eventType": "ClaimCreated", "claim": claim},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=claim["missionId"],
            claim_id=claim["claimId"],
        )
        return self._commit(
            [AppendRequest(stream, ClaimAggregate.KIND, expected, event, state)], metadata
        )

    def record_evidence(
        self, claim_id: str, evidence: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("EvidenceRecord", evidence)
        require("CommandMetadata", metadata)
        require_authority("record_evidence", metadata["actor"]["kind"])

        stream = ClaimAggregate.stream_id(claim_id)
        expected = self.store.aggregate_version(stream)
        state = ClaimAggregate.attach_evidence(
            self.store.require_state(stream), evidence["evidenceId"]
        )

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="EvidenceRecorded",
            payload={"eventType": "EvidenceRecorded", "evidence": evidence},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=evidence["missionId"],
            claim_id=claim_id,
        )
        return self._commit(
            [AppendRequest(stream, ClaimAggregate.KIND, expected, event, state)], metadata
        )

    def record_verification(
        self, verification: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Attach an independently produced VerificationResult."""
        require("VerificationResult", verification)
        require("CommandMetadata", metadata)
        require_authority("produce_verification", metadata["actor"]["kind"])

        if verification["verifiedBy"]["kind"] != "verification_plane":
            raise AuthorityViolation(
                "VerificationResult.verifiedBy must be a verification_plane actor, "
                "got %r" % verification["verifiedBy"]["kind"]
            )

        stream = ClaimAggregate.stream_id(verification["claimId"])
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)

        # A 'verified' status must cite evidence this runtime already holds.
        # Otherwise verification could name evidence ids that do not exist.
        status = verification["status"]
        if status["kind"] == "verified":
            known = set(current["evidenceIds"])
            missing = [e for e in status["supportingEvidenceIds"] if e not in known]
            if missing:
                raise AuthorityViolation(
                    "verification cites evidence not recorded on claim %s: %s"
                    % (verification["claimId"], ", ".join(sorted(missing)))
                )

        state = ClaimAggregate.record_verification(current, verification)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="ClaimVerified",
            payload={"eventType": "ClaimVerified", "verification": verification},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            claim_id=verification["claimId"],
        )
        return self._commit(
            [AppendRequest(stream, ClaimAggregate.KIND, expected, event, state)], metadata
        )

    def decide_claim(
        self, decision: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("ClaimGuardDecision", decision)
        require("CommandMetadata", metadata)
        require_authority("decide_claim", metadata["actor"]["kind"])

        if decision["decidedBy"]["kind"] != "claim_authority":
            raise AuthorityViolation(
                "ClaimGuardDecision.decidedBy must be a claim_authority actor, got %r"
                % decision["decidedBy"]["kind"]
            )

        stream = ClaimAggregate.stream_id(decision["claimId"])
        expected = self.store.aggregate_version(stream)
        state = ClaimAggregate.decide(self.store.require_state(stream), decision)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="ClaimGuardDecided",
            payload={"eventType": "ClaimGuardDecided", "decision": decision},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            claim_id=decision["claimId"],
        )
        return self._commit(
            [AppendRequest(stream, ClaimAggregate.KIND, expected, event, state)], metadata
        )
