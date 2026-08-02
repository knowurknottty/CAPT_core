"""Claim and DriverRun aggregates (ADR-0103, ADR-0110).

ClaimAggregate enforces the rule that separates CAPT from an agent that
merely asserts success: a `completion` claim cannot reach `accepted` without
an independent VerificationResult carrying `verified` status.

DriverRunAggregate is CONTRACT AND STATE MODEL ONLY for M0-A. No driver is
integrated (ADR-0111).
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Optional

from ..errors import AuthorityViolation, IllegalTransition

# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------

CLAIM_TERMINAL: FrozenSet[str] = frozenset({"accepted", "rejected", "suppressed"})

CLAIM_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    "proposed": frozenset({"verified", "rejected", "escalated", "qualified", "suppressed"}),
    "verified": frozenset({"accepted", "qualified", "rejected", "escalated"}),
    "qualified": frozenset({"accepted", "rejected", "escalated"}),
    "escalated": frozenset({"accepted", "qualified", "rejected", "suppressed"}),
    "accepted": frozenset(),
    "rejected": frozenset(),
    "suppressed": frozenset(),
}


class ClaimAggregate(object):
    """Owns proposal, evidence links, verification result, and promotion."""

    KIND = "claim"
    OWNED_FIELDS = frozenset(
        {
            "claim.statement",
            "claim.kind",
            "claim.evidenceIds",
            "claim.verificationId",
            "claim.verificationStatus",
            "claim.promotionState",
            "claim.guardVerdict",
            "claim.qualification",
        }
    )
    REFERENCE_FIELDS = frozenset({"claimId", "missionId", "taskId", "sourceProposalId"})

    @staticmethod
    def stream_id(claim_id: str) -> str:
        return "claim-" + claim_id

    @staticmethod
    def propose(claim: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "claimId": claim["claimId"],
            "missionId": claim["missionId"],
            "taskId": claim.get("taskId"),
            "kind": claim["kind"],
            "statement": claim["statement"],
            "evidenceIds": list(claim.get("evidenceIds", [])),
            "verificationId": None,
            "verificationStatus": None,
            "promotionState": "proposed",
            "guardVerdict": None,
            "qualification": None,
            "sourceProposalId": claim.get("sourceProposalId"),
        }

    @staticmethod
    def attach_evidence(state: Dict[str, Any], evidence_id: str) -> Dict[str, Any]:
        if state["promotionState"] in CLAIM_TERMINAL:
            raise IllegalTransition(
                "claim %s is terminal" % state["claimId"],
                state["promotionState"],
                "attach_evidence",
            )
        nxt = dict(state)
        ids = list(nxt["evidenceIds"])
        if evidence_id not in ids:
            ids.append(evidence_id)
        nxt["evidenceIds"] = ids
        return nxt

    @staticmethod
    def record_verification(
        state: Dict[str, Any], verification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Attach an INDEPENDENTLY produced VerificationResult.

        The verification's own contract requires a verification-plane author,
        and `verified` status structurally requires at least one supporting
        evidence id. ClaimGuard therefore cannot manufacture this.
        """
        if verification["claimId"] != state["claimId"]:
            raise AuthorityViolation("verification references a different claim")
        if state["promotionState"] in CLAIM_TERMINAL:
            raise IllegalTransition(
                "claim %s is terminal" % state["claimId"],
                state["promotionState"],
                "record_verification",
            )

        status_kind = verification["status"]["kind"]

        nxt = dict(state)
        nxt["verificationId"] = verification["verificationId"]
        nxt["verificationStatus"] = status_kind
        if status_kind == "verified":
            nxt["promotionState"] = "verified"
        elif status_kind == "contradicted":
            nxt["promotionState"] = "rejected"
        # observed_unverified / inference / inconclusive / not_tested leave the
        # claim `proposed`: observation may persist WITHOUT being promoted.
        return nxt

    @staticmethod
    def decide(state: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a ClaimGuard verdict.

        Central rule (spec 12.2): a COMPLETION claim may only be accepted when
        an independent verification returned `verified`. ClaimGuard may still
        downgrade a verified claim, but it can never upgrade an unverified one.
        """
        verdict = decision["verdict"]
        target = {
            "accept": "accepted",
            "qualify": "qualified",
            "reject": "rejected",
            "escalate": "escalated",
        }[verdict]

        current = state["promotionState"]
        if current in CLAIM_TERMINAL:
            raise IllegalTransition(
                "claim %s is terminal" % state["claimId"], current, target
            )
        if target not in CLAIM_TRANSITIONS.get(current, frozenset()):
            raise IllegalTransition("claim %s" % state["claimId"], current, target)

        if verdict == "accept" and state["kind"] == "completion":
            if state["verificationStatus"] != "verified":
                raise AuthorityViolation(
                    "completion claim %s cannot be accepted: verification status "
                    "is %r, not 'verified'"
                    % (state["claimId"], state["verificationStatus"])
                )
            if not state["evidenceIds"]:
                raise AuthorityViolation(
                    "completion claim %s cannot be accepted with no evidence"
                    % state["claimId"]
                )
            if decision.get("verificationId") != state["verificationId"]:
                raise AuthorityViolation(
                    "ClaimGuard decision must reference the recorded "
                    "verification %r" % state["verificationId"]
                )

        nxt = dict(state)
        nxt["promotionState"] = target
        nxt["guardVerdict"] = verdict
        nxt["qualification"] = decision.get("qualification")
        return nxt


# ---------------------------------------------------------------------------
# DriverRun (state model only for M0-A)
# ---------------------------------------------------------------------------

DRIVER_TERMINAL: FrozenSet[str] = frozenset({"completed", "failed", "cancelled", "reconciled"})

DRIVER_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    "created": frozenset({"submitted", "cancelled", "failed"}),
    "submitted": frozenset({"running", "lost", "cancelled", "failed"}),
    "running": frozenset({"suspended", "completed", "failed", "lost", "cancelled"}),
    "suspended": frozenset({"running", "cancelled", "failed", "lost"}),
    "lost": frozenset({"reconciled", "failed"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
    "reconciled": frozenset(),
}


class DriverRunAggregate(object):
    """Owns driver-run lifecycle and reconciliation status.

    M0-A: contract and state model only. Nothing in this class contacts an
    external process (ADR-0111).
    """

    KIND = "driverrun"
    OWNED_FIELDS = frozenset(
        {
            "driverrun.state",
            "driverrun.reconciliationStatus",
            "driverrun.workOrderVersion",
            "driverrun.externalRunId",
        }
    )
    REFERENCE_FIELDS = frozenset({"driverRunId", "driverId", "missionId", "taskId"})

    @staticmethod
    def stream_id(driver_run_id: str) -> str:
        return "driverrun-" + driver_run_id

    @staticmethod
    def create(run: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "driverRunId": run["driverRunId"],
            "driverId": run["driverId"],
            "missionId": run["missionId"],
            "taskId": run["taskId"],
            "workOrderVersion": run["workOrderVersion"],
            "externalRunId": run.get("externalRunId"),
            "state": "created",
            "reconciliationStatus": "not_required",
        }

    @staticmethod
    def transition(
        state: Dict[str, Any], to_state: str, external_run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        current = state["state"]
        if current in DRIVER_TERMINAL:
            raise IllegalTransition(
                "driver run %s is terminal" % state["driverRunId"], current, to_state
            )
        if to_state not in DRIVER_TRANSITIONS.get(current, frozenset()):
            raise IllegalTransition(
                "driver run %s" % state["driverRunId"], current, to_state
            )
        nxt = dict(state)
        nxt["state"] = to_state
        if external_run_id is not None:
            nxt["externalRunId"] = external_run_id
        if to_state == "lost":
            nxt["reconciliationStatus"] = "required"
        if to_state == "reconciled":
            nxt["reconciliationStatus"] = "resolved_effect_absent"
        return nxt
