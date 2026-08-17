"""Application services: the only cross-aggregate mutation path (ADR-0103).

Each method performs the eight-step transaction rule:
    validate -> load with expected version -> check invariant -> transition
    -> persist state+event in ONE transaction -> commit -> dispatch via outbox.

Aggregates never call each other. Any change touching two aggregates is an
explicit service method here, so cross-aggregate coupling is enumerable.
"""

from __future__ import annotations

import time
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
from .errors import AuthorityViolation, ConcurrencyError, IdempotencyConflict
from .store import AppendRequest, EventStore


def _now_rfc3339() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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
        return self._commit(
            [self._append_create_mission(spec, metadata)], metadata
        )

    def _append_create_mission(
        self, spec: Dict[str, Any], metadata: Dict[str, Any]
    ) -> "AppendRequest":
        require("MissionSpec", spec)
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
        return AppendRequest(stream, MissionAggregate.KIND, expected, event, state)

    # -- operator mission intent (M1 governed operator actions) -----------
    #
    # The desktop submits a high-level OperatorMissionIntent. ALL planning
    # (MissionSpec / TaskNode / HumanApprovalRequest construction) and the
    # cross-aggregate orchestration live here, in the runtime. The desktop
    # never builds aggregates. The whole intent is committed in ONE
    # transaction under the operator command's idempotency key, with the
    # correct actor kind per aggregate (human mission, cognitive_plane task,
    # execution_plane approval).

    def _inner_metadata(
        self,
        outer: Dict[str, Any],
        operation: str,
        subject: Dict[str, Any],
        actor_kind: str,
        actor_id: str,
        idem_suffix: str,
    ) -> Dict[str, Any]:
        idek = outer["idempotencyKey"] + (":" + idem_suffix if idem_suffix else "")
        return commands.command(
            command_id=outer["commandId"] + (":" + idem_suffix if idem_suffix else ""),
            idempotency_key=idek,
            operation_fingerprint=commands.fingerprint(operation, subject),
            correlation_id=outer.get("correlationId", "corr-m1"),
            actor_id=actor_id,
            actor_kind=actor_kind,
            issued_at=outer.get("issuedAt") or outer.get("timestamp") or _now_rfc3339(),
            replay_policy="never",
        )

    def _build_mission_spec_from_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        objectives = intent.get("objectives") or [
            {"objectiveId": "obj-1", "statement": intent.get("objective", "Operator mission"),
             "priority": 1}
        ]
        constraints = intent.get("constraints", [])
        success = intent.get("successCriteria") or [
            {"criterionId": "sc-1", "statement": "Mission objective achieved",
             "requiresVerification": True}
        ]
        termination = intent.get("terminationCriteria") or [
            {"criterionId": "tc-1", "statement": "Invariant violation terminates mission",
             "terminalState": "failed"}
        ]
        return {
            "schemaVersion": "1.0.0",
            "missionId": intent["missionId"],
            "rawRequest": intent.get("rawRequest", intent.get("objective", "")),
            "normalizedRequest": intent.get("normalizedRequest", intent.get("objective", "")),
            "objectives": objectives,
            "constraints": constraints,
            "successCriteria": success,
            "terminationCriteria": termination,
            "unresolvedAmbiguities": intent.get("unresolvedAmbiguities", []),
            "taskGraphId": None,
            "createdAt": _now_rfc3339(),
        }

    def _build_task_from_intent(self, intent: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        scope = intent.get("scope") or {"kind": "filesystem", "rootPath": "/tmp", "recursive": False}
        if "recursive" not in scope:
            scope = {**scope, "recursive": False}
        return {
            "taskId": task_id,
            "missionId": intent["missionId"],
            "title": intent.get("objective", "Operator task"),
            "state": "pending",
            "consequential": bool(intent.get("consequential", True)),
            "capabilityRequirements": [
                {
                    "requirementId": "req-1",
                    "capabilityId": intent.get("requestedCapability", "cap.fs.read"),
                    "operations": intent.get("operations", ["repository.read"]),
                    "scope": scope,
                }
            ],
            "assignedDriverId": None,
            "attempt": 0,
            "maxAttempts": 1,
            "recoveryState": "none",
        }

    def _build_approval_request_from_intent(
        self, intent: Dict[str, Any], task_id: str, request_id: str
    ) -> Dict[str, Any]:
        scope = intent.get("scope") or {"kind": "filesystem", "rootPath": "/tmp", "recursive": False}
        if "recursive" not in scope:
            scope = {**scope, "recursive": False}
        return {
            "schemaVersion": "1.0.0",
            "requestId": request_id,
            "missionId": intent["missionId"],
            "taskId": task_id,
            "requestedCapability": intent.get("requestedCapability", "cap.fs.read"),
            "resource": intent.get("resource", intent.get("target", "/tmp")),
            "operation": intent.get("operation", "RepositoryRead"),
            "scope": scope,
            "riskClassification": intent.get("riskClassification", "low"),
            "policyReason": intent.get(
                "policyReason",
                "Operator-initiated consequential action requires approval.",
            ),
            "requestedBy": {"actorId": "exec-1", "kind": "execution_plane"},
            "expiresAt": intent.get("expiresAt", "2030-01-01T00:00:00Z"),
            "remainingUses": intent.get("remainingUses"),
            "correlationId": intent.get("correlationId", "corr-m1"),
            "createdAt": _now_rfc3339(),
        }

    def create_mission_with_approval(
        self, intent: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a bounded mission from an operator intent (runtime-owned planning).

        The operator command's CommandMetadata (human actor, bound operatorId)
        is the authority source. This method owns ALL planning: it builds the
        MissionSpec, TaskNode, and (when requiresApproval) HumanApprovalRequest,
        then commits them in ONE transaction under the operator command's
        idempotency key. Actor kinds are correct per aggregate: the mission is
        human-authored, the task is planned by the cognitive plane, the
        approval is requested by the execution plane.

        A replay of the same operator command (same idempotencyKey) returns
        idempotent without creating duplicates.
        """
        require("OperatorMissionIntent", intent)
        require("CommandMetadata", metadata)
        require_authority("create_mission", metadata["actor"]["kind"])
        if metadata["actor"]["kind"] != "human":
            raise AuthorityViolation(
                "operator mission commands must be human-authored, got %r"
                % metadata["actor"]["kind"]
            )

        mission_id = intent["missionId"]
        stream = MissionAggregate.stream_id(mission_id)
        # Idempotency replay of the same operator command. A reused key MUST
        # carry the SAME operation fingerprint; a conflicting payload is an
        # authority violation, not a replay (ADR-0108).
        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            offered = metadata.get("operationFingerprint")
            if offered and prior["operation_fingerprint"] != offered:
                raise IdempotencyConflict(
                    "idempotency key %r reused with a different operation "
                    "fingerprint (stored %s, offered %s)"
                    % (metadata["idempotencyKey"], prior["operation_fingerprint"], offered)
                )
            return self._reconstruct_mission_result(mission_id, metadata)

        spec = self._build_mission_spec_from_intent(intent)
        task_id = intent.get("taskId") or (mission_id + "-task-1")
        task = self._build_task_from_intent(intent, task_id)
        appends = [self._append_create_mission(spec, metadata)]
        appends.append(
            self._append_create_task(
                task,
                self._inner_metadata(
                    metadata, "create_task", {"taskId": task_id},
                    "cognitive_plane", "cog-1", "task",
                ),
            )
        )
        request_id = None
        if intent.get("requiresApproval"):
            request_id = intent.get("requestId") or (mission_id + "-approval-1")
            request = self._build_approval_request_from_intent(intent, task_id, request_id)
            appends.append(
                self._append_request_human_approval(
                    request,
                    self._inner_metadata(
                        metadata, "request_human_approval", {"requestId": request_id},
                        "execution_plane", "exec-1", "approval",
                    ),
                )
            )
        result = self._commit(appends, metadata)
        result = dict(result)
        result["missionId"] = mission_id
        result["taskId"] = task_id
        result["requestId"] = request_id
        return result

    def _reconstruct_mission_result(
        self, mission_id: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "status": "idempotent",
            "missionId": mission_id,
            "taskId": None,
            "requestId": None,
        }
        for (sid, _kind, _ver) in self.store.all_aggregates():
            if sid.startswith("task-") or sid.startswith("human_approval-"):
                st = self.store.load_state(sid)
                if st and st.get("missionId") == mission_id:
                    if sid.startswith("task-"):
                        result["taskId"] = st.get("taskId")
                    elif sid.startswith("human_approval-"):
                        result["requestId"] = st.get("requestId")
        return result


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
        return self._commit([self._append_create_task(node, metadata)], metadata)

    def _append_create_task(
        self, node: Dict[str, Any], metadata: Dict[str, Any]
    ) -> "AppendRequest":
        require("TaskNode", node)
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
        return AppendRequest(stream, TaskAggregate.KIND, expected, event, state)

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
        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            return self._commit([], metadata)
        stream = HumanApprovalAggregate.stream_id(request["requestId"])
        if self.store.aggregate_version(stream) != 0:
            raise AuthorityViolation("HUMAN_APPROVAL_REQUEST_ALREADY_EXISTS")
        return self._commit(
            [self._append_request_human_approval(request, metadata)], metadata
        )

    def _append_request_human_approval(
        self, request: Dict[str, Any], metadata: Dict[str, Any]
    ) -> "AppendRequest":
        require("HumanApprovalRequest", request)
        require_authority("request_human_approval", metadata["actor"]["kind"])
        stream = HumanApprovalAggregate.stream_id(request["requestId"])
        expected = 0
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
        return AppendRequest(stream, HumanApprovalAggregate.KIND, expected, event, state)

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
        # Idempotency replay of the same operator command: return the prior
        # result without a new event. Checked here (before the aggregate
        # transition, which would otherwise raise IllegalTransition on an
        # already-terminal request) so a retried command is a clean no-op.
        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            current = self.store.load_state(stream)
            return {
                "status": "idempotent",
                "requestId": decision["requestId"],
                "state": current["state"] if current else None,
            }
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

    def require_approved_prompt_assembly(
        self, request_id: str, prompt_assembly_digest: str, operation: str
    ) -> Dict[str, Any]:
        """Compatibility read-check for the prompt portion of a governed approval.

        Consequential model execution MUST use ``admit_approved_model_execution``
        first.  This check remains for the existing runner's later prompt-only
        assertion and therefore accepts the persisted full binding digest or its
        explicitly persisted base prompt-assembly digest.
        """
        state = self.store.require_state(HumanApprovalAggregate.stream_id(request_id))
        if state.get("state") not in ("approved", "consumed"):
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_NOT_APPROVED")
        if state.get("operation") != operation:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_OPERATION_MISMATCH")
        binding = (state.get("scope") or {}).get("approvalBinding") or {}
        accepted_digests = {
            state.get("promptAssemblyDigest"),
            binding.get("basePromptAssemblyDigest"),
        }
        if prompt_assembly_digest not in accepted_digests:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_DIGEST_MISMATCH")
        return state

    def admit_approved_model_execution(
        self,
        request_id: str,
        prompt_assembly_digest: str,
        operation: str,
        *,
        mission_id: str,
        task_id: str,
        driver_run_id: str,
        resource: str,
        use_id: str,
        now: str,
        metadata: Dict[str, Any],
        driver_id: str = "hermes",
        prepared_execution_digest: str = "sha256:" + "0" * 64,
    ) -> Dict[str, Any]:
        """Atomically consume approval and persist a DriverRun dispatch intent.

        This is the irreversible admission boundary. The approval consumption,
        durable DriverRunCreated intent, and caller command idempotency record
        are one ``EventStore.commit_command`` transaction. A crash after return
        is never permission to reconstruct or redispatch work.
        """
        require("CommandMetadata", metadata)
        require_authority("consume_human_approval", metadata["actor"]["kind"])
        if not prepared_execution_digest.startswith("sha256:"):
            raise AuthorityViolation("PREPARED_EXECUTION_DIGEST_REQUIRED")
        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            return {"status": "idempotent", "driverRunId": driver_run_id,
                    "preparedExecutionDigest": prepared_execution_digest}
        stream = HumanApprovalAggregate.stream_id(request_id)
        current = self.store.require_state(stream)
        if current.get("operation") != operation:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_OPERATION_MISMATCH")
        if current.get("promptAssemblyDigest") != prompt_assembly_digest:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_DIGEST_MISMATCH")
        binding = (current.get("scope") or {}).get("approvalBinding") or {}
        checks = (
            ("missionId", mission_id, "MODEL_PROMPT_APPROVAL_MISSION_MISMATCH"),
            ("taskId", task_id, "MODEL_PROMPT_APPROVAL_TASK_MISMATCH"),
            ("driverRunId", driver_run_id, "MODEL_PROMPT_APPROVAL_DRIVER_RUN_MISMATCH"),
            ("targetRoot", resource, "MODEL_PROMPT_APPROVAL_RESOURCE_MISMATCH"),
        )
        for key, offered, code in checks:
            if str(binding.get(key, "")) != str(offered):
                raise AuthorityViolation(code)
        if str(current.get("resource", "")) != str(resource):
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_RESOURCE_MISMATCH")
        if current.get("state") == "consumed":
            if current.get("consumedBy") == use_id:
                return {**current, "status": "idempotent"}
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_CONSUMED")
        if current.get("state") != "approved":
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_NOT_APPROVED")
        if now > current.get("expiresAt", ""):
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_EXPIRED")
        if current.get("remainingUses") != 1:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_ONE_USE_REQUIRED")

        expected = self.store.aggregate_version(stream)
        state = HumanApprovalAggregate.consume(current, use_id, now)
        consumption = {
            "schemaVersion": "1.0.0",
            "requestId": request_id,
            "useId": use_id,
            "consumedAt": now,
            "missionId": mission_id,
            "taskId": task_id,
            "driverRunId": driver_run_id,
            "resource": resource,
            "operation": operation,
            "promptAssemblyDigest": prompt_assembly_digest,
        }
        require("HumanApprovalConsumption", consumption)
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="HumanApprovalConsumed",
            payload={"eventType": "HumanApprovalConsumed", "consumption": consumption},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=mission_id,
            task_id=task_id,
        )
        run = {
            "schemaVersion": "1.0.0", "driverRunId": driver_run_id,
            "driverId": driver_id, "missionId": mission_id, "taskId": task_id,
            "workOrderVersion": 1, "externalRunId": None, "state": "created",
            "reconciliationStatus": "not_required", "createdAt": now,
        }
        require("DriverRun", run)
        run_stream = DriverRunAggregate.stream_id(driver_run_id)
        if self.store.aggregate_version(run_stream) != 0:
            raise AuthorityViolation("MODEL_DRIVER_RUN_ALREADY_EXISTS")
        run_event = commands.envelope(
            event_id=metadata["commandId"] + "-ev2", stream_id=run_stream,
            event_type="DriverRunCreated",
            payload={"eventType": "DriverRunCreated", "driverRun": run},
            metadata=metadata, occurred_at=metadata["issuedAt"],
            mission_id=mission_id, task_id=task_id,
        )
        committed = self._commit(
            [
                AppendRequest(stream, HumanApprovalAggregate.KIND, expected, event, state),
                AppendRequest(run_stream, DriverRunAggregate.KIND, 0, run_event,
                              DriverRunAggregate.create(run)),
            ],
            metadata,
        )
        return {**state, "status": committed.get("status", "applied"),
                "driverRunId": driver_run_id,
                "preparedExecutionDigest": prepared_execution_digest}

    # -- cancellation (M1) ------------------------------------------------

    def cancel_task(
        self, task_id: str, reason: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("CommandMetadata", metadata)
        require_authority("cancel_task", metadata["actor"]["kind"])
        stream = TaskAggregate.stream_id(task_id)
        # Idempotency replay of the same operator command (see
        # submit_human_approval_decision for rationale).
        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            current = self.store.load_state(stream)
            return {
                "status": "idempotent",
                "targetId": task_id,
                "state": current["state"] if current else None,
            }
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)
        state = TaskAggregate.transition(current, "cancelled")
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1", stream_id=stream,
            event_type="TaskTransitioned",
            payload={"eventType": "TaskTransitioned", "taskId": task_id,
                     "fromState": current["state"], "toState": "cancelled", "reason": reason},
            metadata=metadata, occurred_at=metadata["issuedAt"],
            mission_id=current["missionId"], task_id=task_id,
        )
        return self._commit(
            [AppendRequest(stream, TaskAggregate.KIND, expected, event, state)], metadata
        )

    def cancel_driver_run(
        self, driver_run_id: str, reason: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("CommandMetadata", metadata)
        require_authority("cancel_driver_run", metadata["actor"]["kind"])
        stream = DriverRunAggregate.stream_id(driver_run_id)
        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            current = self.store.load_state(stream)
            return {
                "status": "idempotent",
                "targetId": driver_run_id,
                "state": current["state"] if current else None,
            }
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
        # Strip view annotations before contract validation so the stored
        # event payload is contract-conforming (no forbidden additionalProperties).
        from .verification import strip_view
        record = strip_view(verification)
        require("VerificationResult", record)
        require("CommandMetadata", metadata)
        require_authority("produce_verification", metadata["actor"]["kind"])

        if record["verifiedBy"]["kind"] != "verification_plane":
            raise AuthorityViolation(
                "VerificationResult.verifiedBy must be a verification_plane actor, "
                "got %r" % record["verifiedBy"]["kind"]
            )

        stream = ClaimAggregate.stream_id(record["claimId"])
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)

        # A 'verified' status must cite evidence this runtime already holds.
        # Otherwise verification could name evidence ids that do not exist.
        status = record["status"]
        if status["kind"] == "verified":
            known = set(current["evidenceIds"])
            missing = [e for e in status["supportingEvidenceIds"] if e not in known]
            if missing:
                raise AuthorityViolation(
                    "verification cites evidence not recorded on claim %s: %s"
                    % (record["claimId"], ", ".join(sorted(missing)))
                )

        state = ClaimAggregate.record_verification(current, record)

        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="ClaimVerified",
            payload={"eventType": "ClaimVerified", "verification": record},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            claim_id=record["claimId"],
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

    # -- work packet abstraction (session continuity) ---------------------

    def get_next_work_packet(
        self,
        mission_id: str,
        session_id: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Derive the next runnable task as a read-only session work packet."""
        require("CommandMetadata", metadata)
        runnable_tasks = []
        for stream_id, _kind, _version in self.store.all_aggregates():
            if stream_id.startswith("task-"):
                state = self.store.load_state(stream_id)
                if (
                    state
                    and state.get("missionId") == mission_id
                    and state.get("state") == "ready"
                    and int(state["attempt"]) < int(state["maxAttempts"])
                ):
                    runnable_tasks.append(state)
        if not runnable_tasks:
            return {
                "hasWork": False,
                "missionId": mission_id,
                "sessionId": session_id,
                "reason": "no_runnable_tasks",
            }
        task = runnable_tasks[0]
        return {
            "hasWork": True,
            "packetId": task["taskId"],
            "missionId": mission_id,
            "sessionId": session_id,
            "taskId": task["taskId"],
            "title": task.get("title"),
            "state": task["state"],
            "capabilityRequirements": task.get("capabilityRequirements", []),
            "exactNextAction": task.get("exactNextAction") or "execute_task",
            "createdAt": task.get("createdAt"),
        }

    def submit_result(
        self, task_id: str, result: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record an immutable result reference and canonical task transition."""
        require("CommandMetadata", metadata)
        require_authority("submit_result", metadata["actor"]["kind"])
        if set(result) != {"status", "resultRef"}:
            raise ValueError("result must contain only status and resultRef")
        status, result_ref = result["status"], result["resultRef"]
        if status not in ("succeeded", "failed", "cancelled"):
            raise ValueError("result status must be succeeded, failed, or cancelled")
        if not isinstance(result_ref, str) or not result_ref:
            raise ValueError("resultRef must be a non-empty reference string")
        stream = TaskAggregate.stream_id(task_id)
        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            return self._commit([], metadata)
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)
        to_state = "awaiting_verification" if status == "succeeded" else status
        state = TaskAggregate.record_result(current, result_ref)
        state = TaskAggregate.transition(state, to_state)
        event = commands.envelope(
            event_id=metadata["commandId"] + "-result", stream_id=stream,
            event_type="TaskResultSubmitted",
            payload={"eventType": "TaskResultSubmitted", "taskId": task_id,
                     "resultRef": result_ref, "toState": to_state},
            metadata=metadata, occurred_at=metadata["issuedAt"],
            mission_id=current["missionId"], task_id=task_id,
        )
        return self._commit(
            [AppendRequest(stream, TaskAggregate.KIND, expected, event, state)], metadata
        )

    # -- governed discovery (v0.7, additive read-only) ---------------------
    def run_governed_discovery(
        self, request: dict, metadata: dict
    ) -> dict:
        """Run a bounded, read-only discovery as a governed operation.

        Additive and NON-MUTATING: it performs no aggregate transition, writes
        no event, and does not create or enlarge any capability. It only admits
        the request, validates admission authority, runs the Discovery Governor
        + Bounded SEAL scanner, and returns the DiscoveryResult plus an
        evidence-shaped payload that the caller must route through the
        canonical ``record_evidence`` path for authoritative persistence.

        Authority: admission requires a human or system actor (read intent).
        The discovery subsystem itself never grants.
        """
        from .discovery import run_discovery, to_evidence

        require_authority("create_mission", metadata["actor"]["kind"])
        if metadata["actor"]["kind"] not in ("human", "system"):
            raise AuthorityViolation(
                "governed discovery must be requested by human or system, got %r"
                % metadata["actor"]["kind"]
            )

        targets = request.get("targets")
        if not isinstance(targets, list) or not targets:
            raise ValueError("request.targets must be a non-empty list of paths")
        allowed_roots = request.get("allowedRoots")
        enumeration_root = request.get("enumerationRoot")
        guess_budget = int(request.get("guessBudget", 3))

        result = run_discovery(
            targets=targets,
            allowed_roots=allowed_roots,
            enumeration_root=enumeration_root,
            guess_budget=guess_budget,
            requester=str(metadata["actor"].get("actorId", metadata["actor"]["kind"])),
            request_id=metadata.get("commandId", ""),
            expected_markers=request.get("expectedMarkers"),
        )
        mission_id = request.get("missionId", "mission-unknown")
        evidence_id = request.get("evidenceId")
        evidence = to_evidence(
            result, mission_id=mission_id,
            collected_by=metadata["actor"], evidence_id=evidence_id)
        return {
            "status": "ok",
            "requestId": result.request_id,
            "discovery": result.to_dict(),
            "evidence": evidence,
        }
