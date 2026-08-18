"""Canonical RuntimeService extensions for governed upgrade transactions.

This is a subclass of the existing RuntimeService, selected by the canonical
composition root. It is not a parallel runtime or authority path.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

from . import commands
from .aggregates.artifact_promotion import ArtifactPromotionAggregate
from .artifact_workspace import atomic_adopt_verified_artifact, file_digest
from .authority import require_authority
from .errors import AuthorityViolation, IdempotencyConflict, IntegrityViolation
from .services import RuntimeService
from .store import AppendRequest


class GovernedRuntimeService(RuntimeService):
    """RuntimeService plus explicitly governed Sol-Reconciliation transactions."""

    def _event_by_identity(
        self, event_type: str, identity_key: str, identity_value: str
    ) -> Optional[Dict[str, Any]]:
        for env in self.store.read_events():
            payload = env.get("payload") or {}
            if payload.get("eventType") != event_type:
                continue
            record = payload.get("verification") if event_type == "ClaimVerified" else payload.get("evidence")
            if isinstance(record, Mapping) and record.get(identity_key) == identity_value:
                return dict(record)
        return None

    def prepare_artifact_promotion(
        self, spec: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require_authority("prepare_artifact_promotion", metadata["actor"]["kind"])
        stream = ArtifactPromotionAggregate.stream_id(spec["promotionId"])
        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            offered = metadata.get("operationFingerprint")
            if offered and prior["operation_fingerprint"] != offered:
                raise IdempotencyConflict("artifact promotion prepare idempotency conflict")
            current = self.store.load_state(stream)
            return {"status": "idempotent", "promotion": current}
        expected = self.store.aggregate_version(stream)
        if expected != 0:
            raise AuthorityViolation("artifact promotion identity already exists")
        state = ArtifactPromotionAggregate.prepare(spec)
        if file_digest(state["sourcePath"]) != state["contentDigest"]:
            raise IntegrityViolation("staged artifact digest does not match promotion specification")
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="ArtifactPromotionPrepared",
            payload={"eventType": "ArtifactPromotionPrepared", "promotion": state},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
        )
        result = self._commit(
            [AppendRequest(stream, ArtifactPromotionAggregate.KIND, expected, event, state)], metadata
        )
        return {**result, "promotion": state}

    def _require_current_artifact_verification(self, state: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        claim_stream = "claim-" + str(state["claimId"])
        claim = self.store.require_state(claim_stream)
        if claim.get("verificationId") != state["verificationId"]:
            raise AuthorityViolation("artifact promotion verification is no longer the claim's current verification")
        if claim.get("verificationStatus") != "verified":
            raise AuthorityViolation("artifact promotion requires current verified claim state")
        if state["evidenceId"] not in (claim.get("evidenceIds") or []):
            raise AuthorityViolation("artifact promotion evidence is not recorded on the claim")

        verification = self._event_by_identity(
            "ClaimVerified", "verificationId", str(state["verificationId"])
        )
        if verification is None:
            raise AuthorityViolation("recorded verification event is unavailable")
        status = verification.get("status") or {}
        if status.get("kind") != "verified":
            raise AuthorityViolation("referenced verification is not verified")
        if state["evidenceId"] not in (status.get("supportingEvidenceIds") or []):
            raise AuthorityViolation("verification does not cite the promotion evidence")

        evidence = self._event_by_identity("EvidenceRecorded", "evidenceId", str(state["evidenceId"]))
        if evidence is None:
            raise AuthorityViolation("recorded artifact evidence is unavailable")
        observation = evidence.get("evidence") or {}
        if observation.get("kind") != "artifact_hash":
            raise AuthorityViolation("promotion evidence is not artifact-hash evidence")
        if observation.get("artifactDigest") != state["contentDigest"]:
            raise AuthorityViolation("promotion evidence digest does not match staged artifact")
        if file_digest(str(state["sourcePath"])) != state["contentDigest"]:
            raise IntegrityViolation("staged artifact changed after verification")
        return verification, evidence

    def authorize_artifact_promotion(
        self, promotion_id: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require_authority("authorize_artifact_promotion", metadata["actor"]["kind"])
        stream = ArtifactPromotionAggregate.stream_id(promotion_id)
        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            current = self.store.load_state(stream)
            return {"status": "idempotent", "promotion": current}
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)
        verification, evidence = self._require_current_artifact_verification(current)
        state = ArtifactPromotionAggregate.authorize(
            current, metadata["actor"]["actorId"], metadata["issuedAt"]
        )
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="ArtifactPromotionAuthorized",
            payload={
                "eventType": "ArtifactPromotionAuthorized",
                "promotionId": promotion_id,
                "verificationId": verification["verificationId"],
                "evidenceId": evidence["evidenceId"],
                "contentDigest": current["contentDigest"],
                "destinationPath": current["destinationPath"],
            },
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
        )
        result = self._commit(
            [AppendRequest(stream, ArtifactPromotionAggregate.KIND, expected, event, state)], metadata
        )
        return {**result, "promotion": state}

    def adopt_artifact_promotion(
        self, promotion_id: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require_authority("adopt_artifact_promotion", metadata["actor"]["kind"])
        stream = ArtifactPromotionAggregate.stream_id(promotion_id)
        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            current = self.store.load_state(stream)
            return {"status": "idempotent", "promotion": current}
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)
        if current.get("state") != "authorized":
            raise AuthorityViolation("artifact promotion is not authorized for adoption")

        # Re-check current verification if staged source still exists. If the
        # destination already contains the exact digest, atomic_adopt handles
        # process-death reconciliation after a prior os.replace.
        destination = str(current["destinationPath"])
        destination_matches = False
        try:
            destination_matches = file_digest(destination) == current["contentDigest"]
        except (OSError, IOError):
            destination_matches = False
        if not destination_matches:
            self._require_current_artifact_verification(current)

        receipt = atomic_adopt_verified_artifact(
            str(current["sourcePath"]), destination, str(current["contentDigest"])
        )
        state = ArtifactPromotionAggregate.adopt(current, receipt, metadata["issuedAt"])
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="ArtifactPromotionAdopted",
            payload={"eventType": "ArtifactPromotionAdopted", "promotionId": promotion_id, "receipt": receipt},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
        )
        result = self._commit(
            [AppendRequest(stream, ArtifactPromotionAggregate.KIND, expected, event, state)], metadata
        )
        return {**result, "promotion": state}

    def discard_artifact_promotion(
        self, promotion_id: str, reason: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require_authority("discard_artifact_promotion", metadata["actor"]["kind"])
        stream = ArtifactPromotionAggregate.stream_id(promotion_id)
        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            current = self.store.load_state(stream)
            return {"status": "idempotent", "promotion": current}
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)
        state = ArtifactPromotionAggregate.discard(current, reason, metadata["issuedAt"])
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="ArtifactPromotionDiscarded",
            payload={"eventType": "ArtifactPromotionDiscarded", "promotionId": promotion_id, "reason": reason},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
        )
        result = self._commit(
            [AppendRequest(stream, ArtifactPromotionAggregate.KIND, expected, event, state)], metadata
        )
        return {**result, "promotion": state}
