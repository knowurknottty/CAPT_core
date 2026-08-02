"""Capability aggregate: grants, leases, reservations, consumption (ADR-0107).

Owns ALL authorization state for one grant. The lease lives inside the grant's
aggregate rather than in its own stream, because a revocation must invalidate
grant and lease atomically. Splitting them would create a window where a
revoked grant still has a live lease (ledger Finding D).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..errors import CapabilityDenied, IllegalTransition


def scope_contains(outer: Dict[str, Any], inner: Dict[str, Any]) -> bool:
    """True when `inner` is equal to or narrower than `outer`.

    A lease may only narrow its grant. Widening is the classic privilege
    escalation path and is rejected structurally.
    """
    if outer["kind"] != inner["kind"]:
        return False

    kind = outer["kind"]

    if kind == "none":
        return True

    if kind == "filesystem":
        outer_root = outer["rootPath"].rstrip("/") or "/"
        inner_root = inner["rootPath"].rstrip("/") or "/"
        if not outer["recursive"]:
            # A non-recursive scope contains only itself.
            return inner_root == outer_root and not inner["recursive"]
        if inner_root == outer_root:
            return True
        # Compare on path-segment boundaries: /tmp/ab must NOT be inside /tmp/a.
        return inner_root.startswith(outer_root + "/")

    if kind == "repository":
        return (
            outer["repositoryId"] == inner["repositoryId"]
            and (outer["refPattern"] == inner["refPattern"] or outer["refPattern"] == "*")
        )

    if kind == "network":
        return set(inner["hosts"]).issubset(set(outer["hosts"]))

    if kind == "tool":
        return set(inner["toolIds"]).issubset(set(outer["toolIds"]))

    return False


class CapabilityAggregate(object):
    """Owns grant, lease, reservations, consumption, revocation, expiration."""

    KIND = "capability"
    OWNED_FIELDS = frozenset(
        {
            "capability.grantState",
            "capability.operations",
            "capability.scope",
            "capability.conditions",
            "capability.maxUses",
            "capability.usesConsumed",
            "capability.validFrom",
            "capability.validUntil",
            "capability.lease",
            "capability.reservations",
            "capability.consumptions",
            "capability.revocation",
        }
    )
    REFERENCE_FIELDS = frozenset(
        {"grantId", "capabilityId", "subjectActorId", "policyDecisionId", "policyBundleDigest"}
    )

    @staticmethod
    def stream_id(grant_id: str) -> str:
        return "capability-" + grant_id

    # -- grant -------------------------------------------------------------

    @staticmethod
    def grant(grant: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "grantId": grant["grantId"],
            "grantState": "granted",
            "capabilityId": grant["capabilityId"],
            "subjectActorId": grant["subject"]["actorId"],
            "operations": list(grant["operations"]),
            "scope": grant["scope"],
            "conditions": list(grant.get("conditions", [])),
            "policyDecisionId": grant["policyDecisionId"],
            "policyBundleDigest": grant["policyBundleDigest"],
            "maxUses": grant.get("maxUses"),
            "usesConsumed": 0,
            "validFrom": grant["validFrom"],
            "validUntil": grant["validUntil"],
            "lease": None,
            "reservations": [],
            "consumptions": [],
            "revocation": None,
        }

    # -- lease -------------------------------------------------------------

    @staticmethod
    def activate_lease(state: Dict[str, Any], lease: Dict[str, Any]) -> Dict[str, Any]:
        if state["grantState"] != "granted":
            raise IllegalTransition(
                "grant %s" % state["grantId"], state["grantState"], "leased"
            )
        if state["revocation"] is not None:
            raise CapabilityDenied("grant %s is revoked" % state["grantId"])
        if lease["grantId"] != state["grantId"]:
            raise CapabilityDenied("lease references a different grant")

        # A lease may only narrow its grant.
        if not set(lease["operations"]).issubset(set(state["operations"])):
            raise CapabilityDenied(
                "lease operations %s exceed grant operations %s"
                % (sorted(lease["operations"]), sorted(state["operations"]))
            )
        if not scope_contains(state["scope"], lease["scope"]):
            raise CapabilityDenied(
                "lease scope is not contained by grant scope", lease["leaseId"]
            )
        if lease["validFrom"] < state["validFrom"] or lease["validUntil"] > state["validUntil"]:
            raise CapabilityDenied(
                "lease validity window exceeds grant window", lease["leaseId"]
            )
        grant_max = state.get("maxUses")
        lease_max = lease.get("maxUses")
        if grant_max is not None and (lease_max is None or lease_max > grant_max):
            raise CapabilityDenied(
                "lease maxUses exceeds grant maxUses", lease["leaseId"]
            )

        nxt = dict(state)
        nxt["grantState"] = "leased"
        nxt["lease"] = {
            "leaseId": lease["leaseId"],
            "missionId": lease["missionId"],
            "taskId": lease["taskId"],
            "executionContextId": lease["executionContextId"],
            "operations": list(lease["operations"]),
            "scope": lease["scope"],
            "maxUses": lease_max,
            "validFrom": lease["validFrom"],
            "validUntil": lease["validUntil"],
            "state": "active",
        }
        return nxt

    # -- the consequential boundary ---------------------------------------

    @staticmethod
    def check_lease(
        state: Dict[str, Any],
        lease_id: str,
        operation: str,
        scope: Dict[str, Any],
        now: str,
    ) -> None:
        """Revalidate a lease IMMEDIATELY before a consequential side effect.

        Spec invariant 7. Every failure mode below is an independent test in
        the conformance suite. Raises CapabilityDenied; never returns False.
        """
        if state["revocation"] is not None:
            raise CapabilityDenied(
                "grant %s was revoked: %s"
                % (state["grantId"], state["revocation"]["reason"]),
                lease_id,
            )

        lease = state.get("lease")
        if lease is None:
            raise CapabilityDenied("no active lease on grant %s" % state["grantId"], lease_id)
        if lease["leaseId"] != lease_id:
            raise CapabilityDenied("lease %s is not active on this grant" % lease_id, lease_id)
        if lease["state"] != "active":
            raise CapabilityDenied(
                "lease %s is %s, not active" % (lease_id, lease["state"]), lease_id
            )

        # String comparison is valid: all timestamps are RFC 3339 UTC with a
        # fixed-width layout, so lexical order equals chronological order.
        if now < lease["validFrom"]:
            raise CapabilityDenied("lease %s is not yet valid" % lease_id, lease_id)
        if now > lease["validUntil"]:
            raise CapabilityDenied("lease %s expired at %s" % (lease_id, lease["validUntil"]), lease_id)
        if now > state["validUntil"]:
            raise CapabilityDenied(
                "grant %s expired at %s" % (state["grantId"], state["validUntil"]), lease_id
            )

        if operation not in lease["operations"]:
            raise CapabilityDenied(
                "operation %r is not in lease %s" % (operation, lease_id), lease_id
            )
        if not scope_contains(lease["scope"], scope):
            raise CapabilityDenied(
                "requested scope is not contained by lease %s" % lease_id, lease_id
            )

        effective_max = lease["maxUses"] if lease["maxUses"] is not None else state["maxUses"]
        if effective_max is not None and state["usesConsumed"] >= effective_max:
            raise CapabilityDenied(
                "lease %s exhausted: %d of %d uses consumed"
                % (lease_id, state["usesConsumed"], effective_max),
                lease_id,
            )

    # -- reservation / finalization ---------------------------------------

    @staticmethod
    def reserve(
        state: Dict[str, Any], reservation: Dict[str, Any], now: str
    ) -> Dict[str, Any]:
        """Record intent to perform ONE consequential use, before the effect.

        The reservation is what makes a crash mid-effect detectable: an open
        reservation after restart means the external world may have changed
        without CAPT knowing (ledger Finding E).
        """
        CapabilityAggregate.check_lease(
            state,
            reservation["leaseId"],
            reservation["operation"],
            state["lease"]["scope"],
            now,
        )

        for existing in state["reservations"]:
            if existing["reservationId"] == reservation["reservationId"]:
                raise CapabilityDenied(
                    "reservation %s already exists" % reservation["reservationId"]
                )
            # Same idempotency key + same fingerprint + still open = duplicate
            # attempt at the same operation.
            if (
                existing["idempotencyKey"] == reservation["idempotencyKey"]
                and existing["state"] == "open"
            ):
                raise CapabilityDenied(
                    "an open reservation already holds idempotency key %s"
                    % reservation["idempotencyKey"]
                )

        nxt = dict(state)
        nxt["reservations"] = list(state["reservations"]) + [
            {
                "reservationId": reservation["reservationId"],
                "leaseId": reservation["leaseId"],
                "operation": reservation["operation"],
                "operationFingerprint": reservation["operationFingerprint"],
                "idempotencyKey": reservation["idempotencyKey"],
                "state": "open",
            }
        ]
        return nxt

    @staticmethod
    def finalize(
        state: Dict[str, Any], consumption: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Close a reservation and record the audited consumption.

        An `indeterminate` outcome leaves the reservation in
        awaiting_reconciliation: it does NOT free the use, and it does NOT
        permit an automatic retry (spec invariant 12).
        """
        reservation_id = consumption["reservationId"]
        found = None
        for existing in state["reservations"]:
            if existing["reservationId"] == reservation_id:
                found = existing
                break
        if found is None:
            raise CapabilityDenied("no reservation %s" % reservation_id)
        if found["state"] != "open":
            raise CapabilityDenied(
                "reservation %s is already %s; duplicate consumption rejected"
                % (reservation_id, found["state"])
            )

        outcome = consumption["outcome"]
        new_reservation_state = (
            "awaiting_reconciliation" if outcome == "indeterminate" else "finalized"
        )

        nxt = dict(state)
        nxt["reservations"] = [
            dict(r, state=new_reservation_state) if r["reservationId"] == reservation_id else r
            for r in state["reservations"]
        ]
        nxt["consumptions"] = list(state["consumptions"]) + [
            {
                "consumptionId": consumption["consumptionId"],
                "reservationId": reservation_id,
                "leaseId": consumption["leaseId"],
                "outcome": outcome,
                "sideEffectIdentity": consumption.get("sideEffectIdentity"),
            }
        ]

        # A use is counted for succeeded AND indeterminate. Not counting an
        # indeterminate use would let an unknown-outcome operation be retried
        # for free, which is exactly the double-effect risk.
        if outcome in ("succeeded", "indeterminate"):
            nxt["usesConsumed"] = int(state["usesConsumed"]) + 1

        effective_max = (
            state["lease"]["maxUses"]
            if state["lease"] and state["lease"]["maxUses"] is not None
            else state["maxUses"]
        )
        if effective_max is not None and nxt["usesConsumed"] >= effective_max:
            nxt["grantState"] = "consumed"
            if nxt["lease"] is not None:
                nxt["lease"] = dict(nxt["lease"], state="exhausted")

        return nxt

    # -- revocation --------------------------------------------------------

    @staticmethod
    def revoke(state: Dict[str, Any], revocation: Dict[str, Any]) -> Dict[str, Any]:
        """Terminal, irreversible. Kills grant and lease in one transition."""
        if state["revocation"] is not None:
            raise IllegalTransition(
                "grant %s" % state["grantId"], "revoked", "revoked"
            )
        nxt = dict(state)
        nxt["grantState"] = "revoked"
        nxt["revocation"] = {
            "revocationId": revocation["revocationId"],
            "targetKind": revocation["targetKind"],
            "targetId": revocation["targetId"],
            "reason": revocation["reason"],
            "revokedBy": revocation["revokedBy"]["actorId"],
        }
        if nxt["lease"] is not None:
            nxt["lease"] = dict(nxt["lease"], state="revoked")
        return nxt

    @staticmethod
    def expire(state: Dict[str, Any], now: str) -> Dict[str, Any]:
        """Mark expiry. Expiry is a fact about time, not a discretionary act."""
        if state["revocation"] is not None:
            return state
        if now <= state["validUntil"]:
            return state
        nxt = dict(state)
        nxt["grantState"] = "expired"
        if nxt["lease"] is not None:
            nxt["lease"] = dict(nxt["lease"], state="expired")
        return nxt

    @staticmethod
    def open_reservations(state: Dict[str, Any]) -> List[str]:
        return [r["reservationId"] for r in state["reservations"] if r["state"] == "open"]
