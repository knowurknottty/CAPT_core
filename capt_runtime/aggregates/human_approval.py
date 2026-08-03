"""Human approval aggregate (M1 governed operator actions, ADR-DT-M1-001).

A HumanApprovalRequest is raised by the execution plane / governance kernel
before a consequential action. A human operator decides (approve / deny).
The aggregate enforces:

* idempotent decisions keyed by the decision's idempotencyKey;
* expiry: a request past `expiresAt` cannot be approved (deny still allowed
  for audit, but approval is refused as `expired`);
* operator binding: the deciding operator must be present in the decision
  (the service layer confirms it matches the authenticated session);
* terminal state: once decided (approved/denied) or expired, no further
  decision is accepted.

This aggregate owns ONLY approval state. It never mutates missions, tasks,
DriverRuns, capabilities, evidence, or verification. Those remain owned by
their respective aggregates and the RuntimeService command path.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet

from ..errors import AuthorityViolation, IllegalTransition

KIND = "human_approval"

APPROVAL_TERMINAL: FrozenSet[str] = frozenset({"approved", "denied", "expired"})

APPROVAL_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    "requested": frozenset({"approved", "denied", "expired"}),
    "approved": frozenset(),
    "denied": frozenset(),
    "expired": frozenset(),
}


class HumanApprovalAggregate(object):
    """Owns a single bounded approval request and its operator decision."""

    KIND = "human_approval"
    OWNED_FIELDS = frozenset(
        {
            "human_approval.state",
            "human_approval.decision",
            "human_approval.operatorId",
            "human_approval.decidedAt",
            "human_approval.note",
            "human_approval.decidedIdempotencyKeys",
        }
    )
    REFERENCE_FIELDS = frozenset({"requestId", "missionId", "taskId"})

    @staticmethod
    def stream_id(request_id: str) -> str:
        return "human_approval-" + request_id

    @staticmethod
    def create(request: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "requestId": request["requestId"],
            "missionId": request["missionId"],
            "taskId": request["taskId"],
            "requestedCapability": request["requestedCapability"],
            "resource": request["resource"],
            "operation": request["operation"],
            "scope": request.get("scope", {}),
            "riskClassification": request["riskClassification"],
            "policyReason": request["policyReason"],
            "requestedBy": request["requestedBy"],
            "expiresAt": request["expiresAt"],
            "remainingUses": request.get("remainingUses"),
            "correlationId": request["correlationId"],
            "createdAt": request["createdAt"],
            "state": "requested",
            "decision": None,
            "operatorId": None,
            "decidedAt": None,
            "note": None,
            "decidedIdempotencyKeys": [],
        }

    @staticmethod
    def decide(
        state: Dict[str, Any],
        decision: Dict[str, Any],
        now: str,
    ) -> Dict[str, Any]:
        """Apply an operator decision.

        `now` is the decision timestamp (RFC3339); expiry is compared
        lexically because the timestamp format is fixed-width zero-padded UTC.
        Idempotent replay (same idempotencyKey) returns state unchanged.
        """
        current = state["state"]
        idek = decision["idempotencyKey"]
        # Idempotent replay: same decision already applied -> no new event.
        if idek in state["decidedIdempotencyKeys"]:
            return state

        if current in APPROVAL_TERMINAL:
            raise IllegalTransition(
                "approval %s is terminal" % state["requestId"], current,
                decision["decision"],
            )

        decision_value = decision["decision"]
        if decision_value == "approve":
            if now > state["expiresAt"]:
                raise AuthorityViolation(
                    "approval %s expired at %s; approval refused"
                    % (state["requestId"], state["expiresAt"])
                )

        if not decision.get("operatorId"):
            raise AuthorityViolation(
                "approval %s decision missing operatorId" % state["requestId"]
            )

        nxt = dict(state)
        nxt["state"] = "approved" if decision_value == "approve" else "denied"
        nxt["decision"] = decision_value
        nxt["operatorId"] = decision["operatorId"]
        nxt["decidedAt"] = decision["decidedAt"]
        nxt["note"] = decision.get("note")
        keys = list(nxt["decidedIdempotencyKeys"])
        if idek not in keys:
            keys.append(idek)
        nxt["decidedIdempotencyKeys"] = keys
        return nxt

    @staticmethod
    def mark_expired(state: Dict[str, Any]) -> Dict[str, Any]:
        if state["state"] in APPROVAL_TERMINAL:
            return state
        nxt = dict(state)
        nxt["state"] = "expired"
        return nxt
