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
    ReplayForkAggregate,
    TaskAggregate,
    ToolExecutionAggregate,
)
from .authority import require_authority
from .contracts import digest, require
from .driver_run import DriverRunAggregate as _DispatchBoundaryAggregate
from .errors import AuthorityViolation, ConcurrencyError, IdempotencyConflict
from .replay import ledger_identity_to_sequence, replay_to_sequence
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


    # -- historical replay fork -------------------------------------------

    def create_replay_fork_from_intent(
        self, intent: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build a new draft MissionSpec inside RuntimeService and bind it to history."""
        require("ReplayForkIntent", intent)
        require("CommandMetadata", metadata)
        require_authority("create_replay_fork", metadata["actor"]["kind"])
        mission_intent = intent["missionIntent"]
        if mission_intent.get("requiresApproval"):
            raise AuthorityViolation(
                "replay fork creation cannot auto-create approval authority"
            )
        mission_spec = self._build_mission_spec_from_intent(mission_intent)
        return self.create_replay_fork(
            str(intent["forkId"]),
            int(intent["sourceSequence"]),
            mission_spec,
            str(intent["reason"]),
            metadata,
        )

    def create_replay_fork(
        self,
        fork_id: str,
        source_sequence: int,
        new_mission_spec: Dict[str, Any],
        reason: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create new governed history without reactivating historical authority."""
        require("MissionSpec", new_mission_spec)
        require("CommandMetadata", metadata)
        require_authority("create_replay_fork", metadata["actor"]["kind"])

        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            offered = metadata.get("operationFingerprint")
            if offered and prior["operation_fingerprint"] != offered:
                raise IdempotencyConflict("replay fork idempotency conflict")
            current = self.store.require_state(ReplayForkAggregate.stream_id(fork_id))
            return {"status": "idempotent", "fork": current, "replayed": True}

        fork_stream = ReplayForkAggregate.stream_id(fork_id)
        if self.store.aggregate_version(fork_stream) != 0:
            raise AuthorityViolation("replay fork identity already exists")
        mission_stream = MissionAggregate.stream_id(new_mission_spec["missionId"])
        if self.store.aggregate_version(mission_stream) != 0:
            raise AuthorityViolation("replay fork requires a new mission identity")

        source_sequence = int(source_sequence)
        head = self.store.head_sequence()
        if source_sequence < 0:
            raise AuthorityViolation("replay fork sourceSequence must be >= 0")
        if source_sequence > head:
            raise AuthorityViolation(
                "replay fork sourceSequence %d exceeds ledger head %d"
                % (source_sequence, head)
            )
        historical = replay_to_sequence(self.store, source_sequence)
        source_identity = ledger_identity_to_sequence(self.store, source_sequence)
        fork_record = ReplayForkAggregate.create(
            {
                "forkId": fork_id,
                "sourceSequence": source_sequence,
                "sourceEventId": source_identity["eventId"],
                "sourceStateDigest": historical.digest(),
                "sourceChainDigest": source_identity["chainDigest"],
                "newMissionId": new_mission_spec["missionId"],
                "reason": reason,
                "createdBy": dict(metadata["actor"]),
                "createdAt": metadata["issuedAt"],
                "historicalAuthorityReactivated": False,
            }
        )
        fork_event = commands.envelope(
            event_id=metadata["commandId"] + "-fork",
            stream_id=fork_stream,
            event_type="ReplayForkCreated",
            payload={"eventType": "ReplayForkCreated", "fork": fork_record},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=new_mission_spec["missionId"],
        )
        result = self._commit(
            [
                AppendRequest(fork_stream, ReplayForkAggregate.KIND, 0, fork_event, fork_record),
                self._append_create_mission(new_mission_spec, metadata),
            ],
            metadata,
        )
        return {**result, "fork": fork_record}

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
            "externalCommitments": list(intent.get("externalCommitments") or []),
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
            "maxAttempts": int(intent.get("maxAttempts", 1)),
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
            "operations": list(intent.get("operations") or ["repository.read"]),
            "capabilitySubject": intent.get("capabilitySubject"),
            "capabilityConditions": list(intent.get("capabilityConditions") or []),
            "capabilityMaxUses": intent.get("capabilityMaxUses"),
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
            "externalCommitments": list(intent.get("externalCommitments") or []),
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

    def plan_task_for_existing_mission(
        self, intent: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Plan one new governed task under an already-durable mission.

        The outer request is human-authored operator intent, but TaskCreated
        remains authored by the cognitive plane. The existing Mission stream is
        never recreated or rewritten by this operation.
        """
        require("OperatorMissionIntent", intent)
        require("CommandMetadata", metadata)
        if metadata.get("actor", {}).get("kind") != "human":
            raise AuthorityViolation("EXISTING_MISSION_TASK_REQUEST_MUST_BE_HUMAN_AUTHORED")

        mission_id = str(intent.get("missionId") or "").strip()
        task_id = str(intent.get("taskId") or "").strip()
        if not mission_id or not task_id:
            raise AuthorityViolation("EXISTING_MISSION_OR_SUCCESSOR_TASK_ID_MISSING")

        mission_stream = MissionAggregate.stream_id(mission_id)
        mission = self.store.load_state(mission_stream)
        if mission is None:
            raise AuthorityViolation("EXISTING_MISSION_NOT_FOUND")
        if mission.get("state") in ("completed", "failed", "cancelled"):
            raise AuthorityViolation("EXISTING_MISSION_IS_TERMINAL")

        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            offered = metadata.get("operationFingerprint")
            if offered and prior["operation_fingerprint"] != offered:
                raise IdempotencyConflict(
                    "idempotency key %r reused with a different operation fingerprint"
                    % metadata["idempotencyKey"]
                )
            return {"status": "idempotent", "missionId": mission_id, "taskId": task_id}

        task_stream = TaskAggregate.stream_id(task_id)
        if self.store.aggregate_version(task_stream) != 0:
            raise AuthorityViolation("SUCCESSOR_TASK_ID_ALREADY_EXISTS")
        task = self._build_task_from_intent(intent, task_id)
        task_meta = self._inner_metadata(
            metadata, "create_task", {"taskId": task_id, "missionId": mission_id},
            "cognitive_plane", "cog-1", "task",
        )
        result = dict(self._commit([self._append_create_task(task, task_meta)], metadata))
        result.update({"missionId": mission_id, "taskId": task_id})
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
        if self.store.find_idempotent(metadata["idempotencyKey"]) is not None:
            return self._commit([], metadata)

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
        require_authority("transition_mission", metadata["actor"]["kind"])
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
        if any(
            condition.get("kind") == "requires_approval"
            for condition in grant.get("conditions", [])
        ) or grant.get("approvalRequestId"):
            raise AuthorityViolation(
                "HUMAN_APPROVAL_GRANT_MUST_USE_ATOMIC_APPROVAL_TRANSFER"
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

    def _find_policy_decision(self, policy_decision_id: str) -> Optional[Dict[str, Any]]:
        for env in self.store.read_events():
            payload = env["payload"]
            if payload["eventType"] == "PolicyEvaluated":
                decision = payload["policyDecision"]
                if decision["policyDecisionId"] == policy_decision_id:
                    return decision
        return None

    def _policy_decision_exists(self, policy_decision_id: str) -> bool:
        return self._find_policy_decision(policy_decision_id) is not None

    def issue_grant_from_human_approval(
        self,
        request_id: str,
        grant: Dict[str, Any],
        metadata: Dict[str, Any],
        *,
        use_id: str,
        now: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atomically consume one exact human approval and issue one exact grant.

        The approval, PolicyDecision, and CapabilityGrant must agree on mission,
        task, capability, operations, scope, and external commitments.  This is
        the generic causal bridge from human consent to executable capability;
        the approval is consumed in the same commit that creates the grant.
        """
        require("CapabilityGrant", grant)
        require("CommandMetadata", metadata)
        require_authority("issue_grant", metadata["actor"]["kind"])
        expected_fingerprint = commands.fingerprint(
            "issue_grant_from_human_approval",
            {"requestId": request_id, "grant": grant, "useId": use_id},
        )
        if metadata["operationFingerprint"] != expected_fingerprint:
            raise IdempotencyConflict(
                "issue_grant_from_human_approval operation fingerprint does not match semantic request"
            )
        if grant["issuedBy"]["kind"] != "governance_kernel":
            raise AuthorityViolation(
                "CapabilityGrant.issuedBy must be a governance_kernel actor, got %r"
                % grant["issuedBy"]["kind"]
            )
        if grant.get("approvalRequestId") != request_id:
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_REQUEST_ID_MISMATCH")

        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            if prior["operation_fingerprint"] != expected_fingerprint:
                raise IdempotencyConflict(
                    "idempotency key %r reused with a different approval-to-grant request"
                    % metadata["idempotencyKey"]
                )
            approval = self.store.load_state(HumanApprovalAggregate.stream_id(request_id))
            capability = self.store.load_state(CapabilityAggregate.stream_id(grant["grantId"]))
            return {
                "status": "idempotent",
                "requestId": request_id,
                "approvalState": approval.get("state") if approval else None,
                "grantId": grant["grantId"],
                "grantState": capability.get("grantState") if capability else None,
            }

        decision = self._find_policy_decision(grant["policyDecisionId"])
        if decision is None:
            raise AuthorityViolation(
                "grant %s cites unknown policy decision %s"
                % (grant["grantId"], grant["policyDecisionId"])
            )
        if decision["effect"] not in ("allow", "allow_with_conditions"):
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_POLICY_NOT_ALLOW")

        approval_stream = HumanApprovalAggregate.stream_id(request_id)
        approval_expected = self.store.aggregate_version(approval_stream)
        approval = self.store.require_state(approval_stream)
        consumed_at = now or metadata["issuedAt"]

        if approval.get("state") != "approved":
            raise AuthorityViolation("HUMAN_APPROVAL_NOT_APPROVED")
        if consumed_at > approval.get("expiresAt", ""):
            raise AuthorityViolation("HUMAN_APPROVAL_EXPIRED")
        if approval.get("remainingUses") != 1:
            raise AuthorityViolation("HUMAN_APPROVAL_ONE_USE_REQUIRED")

        approval_ops = list(approval.get("operations") or [])
        decision_ops = list(decision.get("requestedOperations") or [])
        grant_ops = list(grant.get("operations") or [])
        if not approval_ops:
            raise AuthorityViolation("HUMAN_APPROVAL_OPERATIONS_REQUIRED_FOR_CAPABILITY")
        approval_subject = approval.get("capabilitySubject")
        if not isinstance(approval_subject, dict):
            raise AuthorityViolation("HUMAN_APPROVAL_SUBJECT_REQUIRED_FOR_CAPABILITY")
        approval_conditions = list(approval.get("capabilityConditions") or [])
        approval_max_uses = approval.get("capabilityMaxUses")
        if isinstance(approval_max_uses, bool) or not isinstance(approval_max_uses, int):
            raise AuthorityViolation("HUMAN_APPROVAL_MAX_USES_REQUIRED_FOR_CAPABILITY")
        if len(approval_ops) != len(set(approval_ops)):
            raise AuthorityViolation("HUMAN_APPROVAL_DUPLICATE_OPERATIONS")
        if len(decision_ops) != len(set(decision_ops)):
            raise AuthorityViolation("HUMAN_APPROVAL_POLICY_DUPLICATE_OPERATIONS")
        if len(grant_ops) != len(set(grant_ops)):
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_DUPLICATE_OPERATIONS")
        if set(approval_ops) != set(decision_ops) or set(approval_ops) != set(grant_ops):
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_OPERATIONS_MISMATCH")

        if approval.get("requestedCapability") != grant.get("capabilityId"):
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_CAPABILITY_MISMATCH")
        if approval.get("missionId") != decision.get("missionId"):
            raise AuthorityViolation("HUMAN_APPROVAL_POLICY_MISSION_MISMATCH")
        if approval.get("taskId") != decision.get("taskId"):
            raise AuthorityViolation("HUMAN_APPROVAL_POLICY_TASK_MISMATCH")
        if approval.get("scope") != decision.get("requestedScope"):
            raise AuthorityViolation("HUMAN_APPROVAL_POLICY_SCOPE_MISMATCH")
        if approval.get("scope") != grant.get("scope"):
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_SCOPE_MISMATCH")
        if approval_subject != decision.get("subject") or approval_subject != grant.get("subject"):
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_SUBJECT_MISMATCH")
        if approval_conditions != list(decision.get("conditions") or []):
            raise AuthorityViolation("HUMAN_APPROVAL_POLICY_CONDITIONS_MISMATCH")
        if approval_conditions != list(grant.get("conditions") or []):
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_CONDITIONS_MISMATCH")
        if approval_max_uses != grant.get("maxUses"):
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_MAX_USES_MISMATCH")
        if decision.get("policyBundleDigest") != grant.get("policyBundleDigest"):
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_POLICY_DIGEST_MISMATCH")
        if grant.get("issuedAt", "") < approval.get("decidedAt", ""):
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_ISSUED_BEFORE_DECISION")
        if grant.get("validUntil", "") > approval.get("expiresAt", ""):
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_OUTLIVES_APPROVAL")

        approval_commitments = list(approval.get("externalCommitments") or [])
        decision_commitments = list(decision.get("externalCommitments") or [])
        grant_commitments = list(grant.get("externalCommitments") or [])
        if approval_commitments != decision_commitments:
            raise AuthorityViolation("HUMAN_APPROVAL_POLICY_COMMITMENT_MISMATCH")
        if approval_commitments != grant_commitments:
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_COMMITMENT_MISMATCH")

        approval_state = HumanApprovalAggregate.consume(approval, use_id, consumed_at)
        consumption = {
            "schemaVersion": "1.0.0",
            "requestId": request_id,
            "useId": use_id,
            "consumedAt": consumed_at,
            "missionId": approval["missionId"],
            "taskId": approval["taskId"],
            "grantId": grant["grantId"],
            "capabilityId": grant["capabilityId"],
            "operations": grant_ops,
            "scope": grant["scope"],
            "subject": grant["subject"],
            "conditions": list(grant.get("conditions") or []),
            "maxUses": grant["maxUses"],
            "externalCommitments": grant_commitments,
        }
        require("HumanApprovalCapabilityConsumption", consumption)

        grant_stream = CapabilityAggregate.stream_id(grant["grantId"])
        if self.store.aggregate_version(grant_stream) != 0:
            raise AuthorityViolation("HUMAN_APPROVAL_GRANT_ALREADY_EXISTS")
        grant_state = CapabilityAggregate.grant(grant)

        approval_event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=approval_stream,
            event_type="HumanApprovalConsumedForCapability",
            payload={
                "eventType": "HumanApprovalConsumedForCapability",
                "consumption": consumption,
            },
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=approval["missionId"],
            task_id=approval["taskId"],
        )
        grant_event = commands.envelope(
            event_id=metadata["commandId"] + "-ev2",
            stream_id=grant_stream,
            event_type="CapabilityGranted",
            payload={"eventType": "CapabilityGranted", "grant": grant},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=approval["missionId"],
            task_id=approval["taskId"],
        )
        committed = self._commit(
            [
                AppendRequest(
                    approval_stream,
                    HumanApprovalAggregate.KIND,
                    approval_expected,
                    approval_event,
                    approval_state,
                ),
                AppendRequest(
                    grant_stream,
                    CapabilityAggregate.KIND,
                    0,
                    grant_event,
                    grant_state,
                ),
            ],
            metadata,
        )
        return {
            "status": committed.get("status", "applied"),
            "requestId": request_id,
            "approvalState": approval_state["state"],
            "grantId": grant["grantId"],
            "grantState": grant_state["grantState"],
        }

    def activate_lease(
        self, lease: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("CapabilityLease", lease)
        require("CommandMetadata", metadata)
        require_authority("activate_lease", metadata["actor"]["kind"])
        if self.store.find_idempotent(metadata["idempotencyKey"]) is not None:
            return self._commit([], metadata)

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
        if self.store.find_idempotent(metadata["idempotencyKey"]) is not None:
            return self._commit([], metadata)

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
        if self.store.find_idempotent(metadata["idempotencyKey"]) is not None:
            return self._commit([], metadata)

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
        current = self.store.require_state(stream)
        target_kind = revocation["targetKind"]
        target_id = revocation["targetId"]
        if target_kind == "grant":
            if target_id != grant_id:
                raise AuthorityViolation(
                    "revocation targetId %r does not match grant %r" % (target_id, grant_id)
                )
        else:
            lease = current.get("lease")
            if lease is None:
                raise AuthorityViolation("cannot revoke lease: grant has no active lease record")
            if target_id != lease.get("leaseId"):
                raise AuthorityViolation(
                    "revocation targetId %r does not match active lease %r"
                    % (target_id, lease.get("leaseId"))
                )
        state = CapabilityAggregate.revoke(current, revocation)

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

    # -- tool execution (state model only; no adapter is contacted) ----------

    def prepare_tool_execution(
        self, execution: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("ToolExecution", execution)
        require("CommandMetadata", metadata)
        require_authority("prepare_tool_execution", metadata["actor"]["kind"])
        stream = ToolExecutionAggregate.stream_id(execution["toolExecutionId"])
        expected = self.store.aggregate_version(stream)
        state = ToolExecutionAggregate.create(execution)
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1", stream_id=stream,
            event_type="ToolExecutionPrepared",
            payload={"eventType": "ToolExecutionPrepared", "execution": state},
            metadata=metadata, occurred_at=metadata["issuedAt"],
        )
        return self._commit(
            [AppendRequest(stream, ToolExecutionAggregate.KIND, expected, event, state)],
            metadata,
        )

    def transition_tool_execution(
        self, tool_execution_id: str, to_state: str, patch: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        require("CommandMetadata", metadata)
        require_authority("transition_tool_execution", metadata["actor"]["kind"])
        stream = ToolExecutionAggregate.stream_id(tool_execution_id)
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)
        effective_patch = dict(patch)
        effective_patch.setdefault("updatedAt", metadata["issuedAt"])
        state = ToolExecutionAggregate.transition(current, to_state, effective_patch)
        if to_state == "admitted":
            event_type = "ToolExecutionAdmitted"
        elif to_state == "dispatching":
            event_type = "ToolExecutionDispatching"
        elif to_state == "effect_observed":
            event_type = "ToolExecutionEffectObserved"
        elif to_state == "settling":
            event_type = "ToolExecutionSettling"
        else:
            event_type = "ToolExecutionTerminated"
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1", stream_id=stream,
            event_type=event_type, payload={"eventType": event_type, "execution": state},
            metadata=metadata, occurred_at=metadata["issuedAt"],
        )
        return self._commit(
            [AppendRequest(stream, ToolExecutionAggregate.KIND, expected, event, state)],
            metadata,
        )

    def settle_predispatch_tool_execution(
        self,
        grant_id: str,
        consumption: Dict[str, Any],
        tool_execution_id: str,
        result: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Atomically close pre-dispatch capability authority and ToolExecution."""
        require("CapabilityConsumptionRecord", consumption)
        require("ToolResult", result)
        require("CommandMetadata", metadata)
        require_authority("finalize_use", metadata["actor"]["kind"])
        require_authority("transition_tool_execution", metadata["actor"]["kind"])
        if consumption["outcome"] != "failed" or consumption.get("sideEffectIdentity") is not None:
            raise AuthorityViolation("PREDISPATCH_SETTLEMENT_MUST_BE_FAILED_WITHOUT_EFFECT")
        if result["status"] not in {"denied", "failed"} or result.get("sideEffectIdentity") is not None:
            raise AuthorityViolation("PREDISPATCH_RESULT_MUST_PROVE_NO_EFFECT")
        if self.store.find_idempotent(metadata["idempotencyKey"]) is not None:
            return self._commit([], metadata)

        capability_stream = CapabilityAggregate.stream_id(grant_id)
        tool_stream = ToolExecutionAggregate.stream_id(tool_execution_id)
        capability_expected = self.store.aggregate_version(capability_stream)
        tool_expected = self.store.aggregate_version(tool_stream)
        capability_current = self.store.require_state(capability_stream)
        tool_current = self.store.require_state(tool_stream)
        if tool_current["state"] not in {"prepared", "admitted"} or tool_current["dispatchBoundary"] != "not_started":
            raise AuthorityViolation("PREDISPATCH_SETTLEMENT_AFTER_DISPATCH_FORBIDDEN")
        if tool_current.get("grantId") != grant_id or tool_current.get("leaseId") != consumption["leaseId"]:
            raise AuthorityViolation("PREDISPATCH_SETTLEMENT_AUTHORITY_MISMATCH")
        reservation_id = consumption["reservationId"]
        if tool_current.get("reservationId") not in {None, reservation_id}:
            raise AuthorityViolation("PREDISPATCH_SETTLEMENT_RESERVATION_MISMATCH")

        capability_state = CapabilityAggregate.finalize(capability_current, consumption)
        tool_state = ToolExecutionAggregate.transition(
            tool_current,
            "failed",
            {
                "reservationId": reservation_id,
                "result": result,
                "resultDigest": digest(result),
                "sideEffectIdentity": None,
                "worldReceipt": None,
                "settlementStatus": "settled",
                "reconciliationReason": None,
                "dispatchBoundary": "not_started",
                "updatedAt": metadata["issuedAt"],
            },
        )
        capability_event = commands.envelope(
            event_id=metadata["commandId"] + "-capability",
            stream_id=capability_stream,
            event_type="CapabilityUseFinalized",
            payload={"eventType": "CapabilityUseFinalized", "consumption": consumption},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
        )
        tool_event = commands.envelope(
            event_id=metadata["commandId"] + "-tool",
            stream_id=tool_stream,
            event_type="ToolExecutionTerminated",
            payload={"eventType": "ToolExecutionTerminated", "execution": tool_state},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
        )
        return self._commit(
            [
                AppendRequest(
                    capability_stream,
                    CapabilityAggregate.KIND,
                    capability_expected,
                    capability_event,
                    capability_state,
                ),
                AppendRequest(
                    tool_stream,
                    ToolExecutionAggregate.KIND,
                    tool_expected,
                    tool_event,
                    tool_state,
                ),
            ],
            metadata,
        )

    # -- driver run (state model only; no driver is contacted) -------------

    def create_driver_run(
        self, run: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("DriverRun", run)
        require("CommandMetadata", metadata)
        require_authority("create_driver_run", metadata["actor"]["kind"])

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
        require_authority("transition_driver_run", metadata["actor"]["kind"])
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
        # P0.1: the expiry check and the consumption commit below execute as one
        # atomic section under the store lock: approval expiry is revalidated
        # against authoritative wall-clock consumption time immediately
        # before authority is consumed, with no interleaving writer able to
        # slip between the check and the commit (TOCTOU). The command-carried
        # `now` is retained as provenance evidence only.
        with self.store.authority_section():
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
            # P0.1: one authoritative consumption timestamp for the whole
            # check-then-consume sequence. Expiry is revalidated against
            # current wall-clock time in addition to the command-carried
            # timestamp: a stale command time must not extend authority, and
            # the aggregate's own check uses the same authoritative value.
            consumed_at = _now_rfc3339()
            if now > current.get("expiresAt", ""):
                raise AuthorityViolation("MODEL_PROMPT_APPROVAL_EXPIRED")
            if consumed_at > current.get("expiresAt", ""):
                raise AuthorityViolation("MODEL_PROMPT_APPROVAL_EXPIRED")
            if current.get("remainingUses") != 1:
                raise AuthorityViolation("MODEL_PROMPT_APPROVAL_ONE_USE_REQUIRED")

            expected = self.store.aggregate_version(stream)
            state = HumanApprovalAggregate.consume(current, use_id, consumed_at)
            consumption = {
                "schemaVersion": "1.0.0",
                "requestId": request_id,
                "useId": use_id,
                "consumedAt": consumed_at,
                "commandIssuedAt": now,
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
                "reconciliationStatus": "not_required", "createdAt": consumed_at,
                "dispatchBoundary": "not_dispatched",
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

    def record_driver_dispatch_boundary(
        self, driver_run_id: str, dispatch_boundary: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Durably record provider dispatch-boundary progress for a driver run.

        Crash-consistent ordering is the caller's duty: the driver records
        ``request_started`` BEFORE the irreversible external call, so a crash
        between the record and the call can only overstate progress in the
        safe direction (retry forbidden, never silent redispatch). Recording
        never dispatches; it only persists the boundary marker. Boundary
        moves are forward-monotonic at the aggregate: a stale recorder may
        re-record the current boundary (idempotent) but may never move it
        backward.
        """
        require("CommandMetadata", metadata)
        require_authority("record_driver_dispatch_boundary", metadata["actor"]["kind"])
        stream = DriverRunAggregate.stream_id(driver_run_id)
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)
        recorded_at = _now_rfc3339()
        # Boundary vocabulary/monotonicity is owned by the boundary-capable
        # aggregate (capt_runtime.driver_run); the service aggregate
        # (aggregates.claim_driver.DriverRunAggregate) carries the durable
        # field. One order table, one source of truth.
        state = _DispatchBoundaryAggregate.record_dispatch_boundary(
            current, dispatch_boundary, recorded_at
        )
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="DriverRunDispatchBoundaryRecorded",
            payload={
                "eventType": "DriverRunDispatchBoundaryRecorded",
                "driverRunId": driver_run_id,
                "dispatchBoundary": dispatch_boundary,
                "previousDispatchBoundary": current.get("dispatchBoundary", "unknown"),
                "recordedAt": recorded_at,
            },
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=current.get("missionId"),
            task_id=current.get("taskId"),
        )
        # _commit reads idempotencyKey/operationFingerprint from metadata;
        # it accepts no such keyword arguments. The caller (desktop runtime
        # service) mints a unique idempotency key per boundary record.
        return self._commit(
            [AppendRequest(stream, DriverRunAggregate.KIND, expected, event, state)],
            metadata,
        )

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

    def propose_claim_with_evidence(
        self,
        claim: Dict[str, Any],
        evidence_records: List[tuple[Dict[str, Any], Dict[str, Any]]],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Persist a new claim and its cited evidence in one ledger transaction.

        ClaimCreated must be the first event in the claim aggregate so replay can
        construct state. EvidenceRecorded events follow in the same atomic
        commit, eliminating a durable claim-without-evidence crash window.
        """
        require("ClaimRecord", claim)
        require("CommandMetadata", metadata)
        require_authority("propose_claim", metadata["actor"]["kind"])
        if claim["promotionState"] != "proposed":
            raise AuthorityViolation(
                "a new claim must enter as 'proposed', got %r" % claim["promotionState"]
            )

        evidence_ids = [evidence["evidenceId"] for evidence, _ in evidence_records]
        if list(claim.get("evidenceIds", [])) != evidence_ids:
            raise AuthorityViolation(
                "atomic claim evidenceIds must exactly match persisted evidence records"
            )

        stream = ClaimAggregate.stream_id(claim["claimId"])
        expected = self.store.aggregate_version(stream)
        state = ClaimAggregate.propose(claim)
        claim_event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="ClaimCreated",
            payload={"eventType": "ClaimCreated", "claim": claim},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=claim["missionId"],
            claim_id=claim["claimId"],
        )
        appends = [AppendRequest(stream, ClaimAggregate.KIND, expected, claim_event, state)]

        version = expected + 1
        for evidence, evidence_metadata in evidence_records:
            require("EvidenceRecord", evidence)
            require("CommandMetadata", evidence_metadata)
            require_authority("record_evidence", evidence_metadata["actor"]["kind"])
            if evidence["missionId"] != claim["missionId"]:
                raise AuthorityViolation("evidence references a different mission")
            state = ClaimAggregate.attach_evidence(state, evidence["evidenceId"])
            evidence_event = commands.envelope(
                event_id=evidence_metadata["commandId"] + "-ev1",
                stream_id=stream,
                event_type="EvidenceRecorded",
                payload={"eventType": "EvidenceRecorded", "evidence": evidence},
                metadata=evidence_metadata,
                occurred_at=evidence_metadata["issuedAt"],
                mission_id=evidence["missionId"],
                task_id=evidence.get("taskId"),
                claim_id=claim["claimId"],
            )
            appends.append(
                AppendRequest(stream, ClaimAggregate.KIND, version, evidence_event, state)
            )
            version += 1

        return self._commit(appends, metadata)

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

    def review_claim_with_human_attestation(
        self,
        claim_id: str,
        disposition: str,
        operator_id: str,
        note: Optional[str],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Atomically close an awaiting-verification claim from human review.

        The human supplies only the attestation/disposition.  CAPT's verification
        plane records the EvidenceRecord + VerificationResult, ClaimGuard owns
        promotion, and system authority owns the task transition.  All four
        events commit as one command so a crash cannot strand a half-reviewed
        completion claim.
        """
        require("CommandMetadata", metadata)
        require_authority("submit_human_claim_review", metadata["actor"]["kind"])
        if metadata["actor"]["actorId"] != operator_id:
            raise AuthorityViolation("human claim review operator identity mismatch")
        if disposition not in {"accept", "reject"}:
            raise AuthorityViolation("human claim review disposition must be accept or reject")

        claim_stream = ClaimAggregate.stream_id(claim_id)
        claim_expected = self.store.aggregate_version(claim_stream)
        claim_state = self.store.require_state(claim_stream)
        if claim_state.get("kind") != "completion":
            raise AuthorityViolation("human claim review requires a completion claim")
        if claim_state.get("promotionState") != "proposed":
            raise AuthorityViolation("human claim review requires a proposed claim")
        task_id = claim_state.get("taskId")
        if not task_id:
            raise AuthorityViolation("human claim review requires a task-bound claim")
        task_stream = TaskAggregate.stream_id(task_id)
        task_expected = self.store.aggregate_version(task_stream)
        task_state = self.store.require_state(task_stream)
        if task_state.get("missionId") != claim_state.get("missionId"):
            raise AuthorityViolation("claim and task mission identity mismatch")
        if task_state.get("state") != "awaiting_verification":
            raise AuthorityViolation("human claim review requires task awaiting_verification")

        mission_id = str(claim_state["missionId"])
        mission_stream = MissionAggregate.stream_id(mission_id)
        mission_state = self.store.load_state(mission_stream)
        mission_expected = (
            self.store.aggregate_version(mission_stream)
            if mission_state is not None else None
        )
        mission_tasks = []
        for candidate_stream, candidate_kind, _candidate_version in self.store.all_aggregates():
            if candidate_kind != TaskAggregate.KIND:
                continue
            candidate = self.store.load_state(candidate_stream)
            if candidate and candidate.get("missionId") == mission_id:
                mission_tasks.append(candidate)

        issued_at = metadata["issuedAt"]
        correlation_id = metadata["correlationId"]
        base_command = metadata["commandId"]
        base_key = metadata["idempotencyKey"]
        statement = (note or "").strip() or (
            "Operator confirmed the provider result satisfies the requested acceptance criteria."
            if disposition == "accept"
            else "Operator rejected the provider result against the requested acceptance criteria."
        )
        evidence_id = "ev-human-" + digest({
            "claimId": claim_id, "operatorId": operator_id,
            "disposition": disposition, "statement": statement,
        })
        evidence = {
            "schemaVersion": "1.0.0",
            "evidenceId": evidence_id,
            "missionId": claim_state["missionId"],
            "taskId": task_id,
            "evidence": {
                "kind": "human_attestation",
                "attestedBy": {"actorId": operator_id, "kind": "human"},
                "statement": statement,
            },
            "collectedBy": {"actorId": "verification_pipeline", "kind": "verification_plane"},
            "collectedAt": issued_at,
            "trust": "capt_authoritative",
        }
        require("EvidenceRecord", evidence)

        verification_id = "vr-human-" + digest({
            "claimId": claim_id, "evidenceId": evidence_id,
            "disposition": disposition,
        })
        verification_status = (
            {"kind": "verified", "supportingEvidenceIds": [evidence_id]}
            if disposition == "accept"
            else {"kind": "observed_unverified", "reason": statement}
        )
        verification = {
            "schemaVersion": "1.0.0",
            "verificationId": verification_id,
            "claimId": claim_id,
            "strategy": "human_review",
            "status": verification_status,
            "verifiedBy": {"actorId": "verification_pipeline", "kind": "verification_plane"},
            "verifiedAt": issued_at,
        }
        require("VerificationResult", verification)
        verdict = "accept" if disposition == "accept" else "reject"
        decision = {
            "schemaVersion": "1.0.0",
            "decisionId": "dec-human-" + digest({
                "claimId": claim_id, "verificationId": verification_id,
                "verdict": verdict,
            }),
            "claimId": claim_id,
            "verdict": verdict,
            "qualification": None,
            "rationale": "Human review disposition %s; attestation evidence %s." % (
                disposition, evidence_id
            ),
            "verificationId": verification_id,
            "decidedBy": {"actorId": "claim_guard", "kind": "claim_authority"},
            "decidedAt": issued_at,
        }
        require("ClaimGuardDecision", decision)

        def phase_meta(suffix: str, actor_id: str, actor_kind: str, operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
            return commands.command(
                command_id=base_command + ":" + suffix,
                idempotency_key=base_key + ":" + suffix,
                operation_fingerprint=commands.fingerprint(operation, payload),
                correlation_id=correlation_id,
                actor_id=actor_id,
                actor_kind=actor_kind,
                issued_at=issued_at,
                replay_policy="never",
            )

        evidence_meta = phase_meta("evidence", "verification_pipeline", "verification_plane", "record_evidence", {"evidenceId": evidence_id})
        verification_meta = phase_meta("verification", "verification_pipeline", "verification_plane", "produce_verification", {"verificationId": verification_id})
        decision_meta = phase_meta("claim-guard", "claim_guard", "claim_authority", "decide_claim", {"decisionId": decision["decisionId"]})
        task_meta = phase_meta("task", "runtime", "system", "transition_task", {"taskId": task_id, "disposition": disposition})
        require_authority("record_evidence", evidence_meta["actor"]["kind"])
        require_authority("produce_verification", verification_meta["actor"]["kind"])
        require_authority("decide_claim", decision_meta["actor"]["kind"])
        require_authority("transition_task", task_meta["actor"]["kind"])

        state = ClaimAggregate.attach_evidence(claim_state, evidence_id)
        evidence_event = commands.envelope(
            event_id=evidence_meta["commandId"] + "-ev1",
            stream_id=claim_stream,
            event_type="EvidenceRecorded",
            payload={"eventType": "EvidenceRecorded", "evidence": evidence},
            metadata=evidence_meta,
            occurred_at=issued_at,
            mission_id=claim_state["missionId"],
            task_id=task_id,
            claim_id=claim_id,
        )
        state = ClaimAggregate.record_verification(state, verification)
        verification_event = commands.envelope(
            event_id=verification_meta["commandId"] + "-ev1",
            stream_id=claim_stream,
            event_type="ClaimVerified",
            payload={"eventType": "ClaimVerified", "verification": verification},
            metadata=verification_meta,
            occurred_at=issued_at,
            claim_id=claim_id,
        )
        state = ClaimAggregate.decide(state, decision)
        decision_event = commands.envelope(
            event_id=decision_meta["commandId"] + "-ev1",
            stream_id=claim_stream,
            event_type="ClaimGuardDecided",
            payload={"eventType": "ClaimGuardDecided", "decision": decision},
            metadata=decision_meta,
            occurred_at=issued_at,
            claim_id=claim_id,
        )
        to_state = "succeeded" if disposition == "accept" else "failed"
        final_task = TaskAggregate.transition(task_state, to_state)
        task_event = commands.envelope(
            event_id=task_meta["commandId"] + "-ev1",
            stream_id=task_stream,
            event_type="TaskTransitioned",
            payload={
                "eventType": "TaskTransitioned", "taskId": task_id,
                "fromState": task_state["state"], "toState": to_state,
                "reason": "human review %s after independent ClaimGuard evaluation" % disposition,
            },
            metadata=task_meta,
            occurred_at=issued_at,
            mission_id=claim_state["missionId"],
            task_id=task_id,
        )
        final_mission_state = mission_state.get("state") if mission_state else None
        mission_append = None
        terminal_task_states = {"succeeded", "failed", "cancelled"}
        all_other_tasks_terminal = all(
            str(candidate.get("taskId")) == str(task_id)
            or candidate.get("state") in terminal_task_states
            for candidate in mission_tasks
        )
        if (
            disposition == "accept"
            and mission_state is not None
            and mission_state.get("state") == "executing"
            and all_other_tasks_terminal
        ):
            mission_meta = phase_meta(
                "mission", "runtime", "system", "transition_mission",
                {"missionId": mission_id, "toState": "completed"},
            )
            require_authority("transition_mission", mission_meta["actor"]["kind"])
            final_mission = MissionAggregate.transition(mission_state, "completed")
            mission_event = commands.envelope(
                event_id=mission_meta["commandId"] + "-ev1",
                stream_id=mission_stream,
                event_type="MissionStateChanged",
                payload={
                    "eventType": "MissionStateChanged",
                    "fromState": mission_state["state"],
                    "toState": "completed",
                    "reason": "verified task accepted and all other mission tasks are terminal",
                },
                metadata=mission_meta,
                occurred_at=issued_at,
                mission_id=mission_id,
            )
            mission_append = AppendRequest(
                mission_stream, MissionAggregate.KIND,
                int(mission_expected), mission_event, final_mission,
            )
            final_mission_state = "completed"

        appends = [
            AppendRequest(claim_stream, ClaimAggregate.KIND, claim_expected, evidence_event, ClaimAggregate.attach_evidence(claim_state, evidence_id)),
            AppendRequest(claim_stream, ClaimAggregate.KIND, claim_expected + 1, verification_event, ClaimAggregate.record_verification(ClaimAggregate.attach_evidence(claim_state, evidence_id), verification)),
            AppendRequest(claim_stream, ClaimAggregate.KIND, claim_expected + 2, decision_event, state),
            AppendRequest(task_stream, TaskAggregate.KIND, task_expected, task_event, final_task),
        ]
        if mission_append is not None:
            appends.append(mission_append)
        commit = self._commit(appends, metadata)
        return {
            "claimId": claim_id,
            "taskId": task_id,
            "evidenceId": evidence_id,
            "verificationId": verification_id,
            "verdict": verdict,
            "claimState": state["promotionState"],
            "taskState": to_state,
            "missionState": final_mission_state,
            "eventIds": commit.get("eventIds", []),
        }

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
