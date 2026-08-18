"""Authoritative artifact-promotion transaction state (CAPT-UPG-009).

ClaimGuard does not own this lifecycle. Verification proves an artifact property;
a separate promotion transaction binds source/destination/digest and governs
whether that verified candidate becomes canonical workspace state.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, FrozenSet

from ..errors import AuthorityViolation, IllegalTransition, IntegrityViolation


PROMOTION_TERMINAL: FrozenSet[str] = frozenset({"adopted", "discarded"})


class ArtifactPromotionAggregate(object):
    KIND = "artifact_promotion"

    @staticmethod
    def stream_id(promotion_id: str) -> str:
        return "artifact_promotion-" + promotion_id

    @staticmethod
    def prepare(spec: Dict[str, Any]) -> Dict[str, Any]:
        required = (
            "promotionId", "candidateId", "workspaceId", "sourcePath",
            "destinationPath", "contentDigest", "claimId", "verificationId",
            "evidenceId", "preparedAt",
        )
        missing = [key for key in required if not spec.get(key)]
        if missing:
            raise ValueError("artifact promotion spec missing fields: %s" % missing)
        source = str(Path(spec["sourcePath"]).expanduser().resolve(strict=False))
        destination = str(Path(spec["destinationPath"]).expanduser().resolve(strict=False))
        if source == destination:
            raise IntegrityViolation("promotion source and destination must differ")
        return {
            "promotionId": spec["promotionId"],
            "candidateId": spec["candidateId"],
            "workspaceId": spec["workspaceId"],
            "sourcePath": source,
            "destinationPath": destination,
            "contentDigest": spec["contentDigest"],
            "claimId": spec["claimId"],
            "verificationId": spec["verificationId"],
            "evidenceId": spec["evidenceId"],
            "preparedAt": spec["preparedAt"],
            "authorizedAt": None,
            "authorizedBy": None,
            "adoptedAt": None,
            "discardedAt": None,
            "discardReason": None,
            "adoptionReceipt": None,
            "state": "prepared",
        }

    @staticmethod
    def authorize(state: Dict[str, Any], actor_id: str, authorized_at: str) -> Dict[str, Any]:
        if state["state"] != "prepared":
            raise IllegalTransition("artifact promotion %s" % state["promotionId"], state["state"], "authorized")
        nxt = dict(state)
        nxt["state"] = "authorized"
        nxt["authorizedAt"] = authorized_at
        nxt["authorizedBy"] = actor_id
        return nxt

    @staticmethod
    def adopt(state: Dict[str, Any], receipt: Dict[str, Any], adopted_at: str) -> Dict[str, Any]:
        if state["state"] == "adopted":
            # Mechanical recovery may discover that the filesystem side effect
            # completed before EventStore acknowledgement. Exact same digest and
            # destination are safe to reconcile, anything else is not.
            prior = state.get("adoptionReceipt") or {}
            if prior.get("destinationPath") == receipt.get("destinationPath") and prior.get("contentDigest") == receipt.get("contentDigest"):
                return dict(state)
            raise IllegalTransition("artifact promotion %s" % state["promotionId"], state["state"], "adopted")
        if state["state"] != "authorized":
            raise IllegalTransition("artifact promotion %s" % state["promotionId"], state["state"], "adopted")
        if receipt.get("destinationPath") != state["destinationPath"]:
            raise AuthorityViolation("adoption receipt destination does not match authorized destination")
        if receipt.get("contentDigest") != state["contentDigest"]:
            raise AuthorityViolation("adoption receipt digest does not match authorized digest")
        nxt = dict(state)
        nxt["state"] = "adopted"
        nxt["adoptedAt"] = adopted_at
        nxt["adoptionReceipt"] = dict(receipt)
        return nxt

    @staticmethod
    def discard(state: Dict[str, Any], reason: str, discarded_at: str) -> Dict[str, Any]:
        if state["state"] in PROMOTION_TERMINAL:
            raise IllegalTransition("artifact promotion %s" % state["promotionId"], state["state"], "discarded")
        nxt = dict(state)
        nxt["state"] = "discarded"
        nxt["discardedAt"] = discarded_at
        nxt["discardReason"] = reason
        return nxt
