"""Canonical RuntimeService extensions for governed upgrade transactions.

This is a subclass of the existing RuntimeService, selected by the canonical
composition root. It is not a parallel runtime or authority path.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

from . import commands
from .aggregates.artifact_promotion import ArtifactPromotionAggregate
from .aggregates.bot import BotAggregate
from .aggregates.claim_driver import ClaimAggregate
from .aggregates.cognitive_candidate import CognitiveCandidateAggregate
from .aggregates.cohort_state import CohortAggregate
from .aggregates.lab_board import LabBoardAggregate
from .aggregates.mission_task import MissionAggregate
from .aggregates.skill_candidate import SkillCandidateAggregate
from .artifact_workspace import atomic_adopt_verified_artifact, file_digest
from .authority import require_authority
from .contracts import digest, require
from .errors import AuthorityViolation, IdempotencyConflict, IntegrityViolation
from .services import RuntimeService
from .store import AppendRequest


class GovernedRuntimeService(RuntimeService):
    """RuntimeService plus explicitly governed Sol-Reconciliation transactions."""

    def _idempotent_projection(
        self, stream: str, label: str, metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if self.store.find_idempotent(metadata["idempotencyKey"]) is None:
            return None
        result = dict(self._commit([], metadata))
        result[label] = self.store.load_state(stream)
        return result

    # -- CAPT Bot foundation ---------------------------------------------

    def register_bot(
        self, manifest: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("BotManifest", manifest)
        require("CommandMetadata", metadata)
        require_authority("register_bot", metadata["actor"]["kind"])
        stream = BotAggregate.stream_id(manifest["botId"])
        replay = self._idempotent_projection(stream, "bot", metadata)
        if replay is not None:
            return replay
        if self.store.aggregate_version(stream) != 0:
            raise AuthorityViolation("BOT_ID_ALREADY_EXISTS")
        if manifest.get("roleKind") == "delegate":
            mission_id = str(manifest.get("missionId") or "")
            if self.store.load_state(MissionAggregate.stream_id(mission_id)) is None:
                raise AuthorityViolation("DELEGATE_MISSION_NOT_FOUND")
        state = BotAggregate.create(manifest)
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1", stream_id=stream,
            event_type="BotRegistered",
            payload={"eventType": "BotRegistered", "bot": manifest},
            metadata=metadata, occurred_at=metadata["issuedAt"],
            mission_id=manifest.get("missionId"),
        )
        result = self._commit([AppendRequest(stream, BotAggregate.KIND, 0, event, state)], metadata)
        return {**result, "bot": state}

    def propose_cognitive_candidate(
        self, candidate: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("CognitiveCandidate", candidate)
        require("CommandMetadata", metadata)
        require_authority("propose_cognitive_candidate", metadata["actor"]["kind"])
        stream = CognitiveCandidateAggregate.stream_id(candidate["candidateId"])
        replay = self._idempotent_projection(stream, "candidate", metadata)
        if replay is not None:
            return replay
        if self.store.aggregate_version(stream) != 0:
            raise AuthorityViolation("COGNITIVE_CANDIDATE_ID_ALREADY_EXISTS")
        bot = self.store.load_state(BotAggregate.stream_id(str(candidate["botId"])))
        if bot is None:
            raise AuthorityViolation("COGNITIVE_CANDIDATE_BOT_NOT_FOUND")
        if candidate["promotionMode"] != bot["cognitionPolicy"].get("promotionMode"):
            raise AuthorityViolation("COGNITIVE_PROMOTION_MODE_MISMATCH")
        state = CognitiveCandidateAggregate.create(candidate)
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1", stream_id=stream,
            event_type="CognitiveCandidateProposed",
            payload={"eventType": "CognitiveCandidateProposed", "candidate": candidate},
            metadata=metadata, occurred_at=metadata["issuedAt"],
        )
        result = self._commit(
            [AppendRequest(stream, CognitiveCandidateAggregate.KIND, 0, event, state)], metadata
        )
        return {**result, "candidate": state}

    def decide_cognitive_candidate(
        self, candidate_id: str, decision: str, reason: Optional[str],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        require("CommandMetadata", metadata)
        require_authority("decide_cognitive_candidate", metadata["actor"]["kind"])
        stream = CognitiveCandidateAggregate.stream_id(candidate_id)
        replay = self._idempotent_projection(stream, "candidate", metadata)
        if replay is not None:
            return replay
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)
        state = CognitiveCandidateAggregate.decide(
            current, decision, metadata["actor"], metadata["issuedAt"], reason
        )
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1", stream_id=stream,
            event_type="CognitiveCandidateDecided",
            payload={"eventType": "CognitiveCandidateDecided", "candidateId": candidate_id,
                     "decision": decision, "decidedBy": metadata["actor"],
                     "decidedAt": metadata["issuedAt"], "reason": reason},
            metadata=metadata, occurred_at=metadata["issuedAt"],
        )
        result = self._commit(
            [AppendRequest(stream, CognitiveCandidateAggregate.KIND, expected, event, state)], metadata
        )
        return {**result, "candidate": state}

    def create_skill_candidate(
        self, candidate: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("SkillCandidate", candidate)
        require("CommandMetadata", metadata)
        require_authority("create_skill_candidate", metadata["actor"]["kind"])
        stream = SkillCandidateAggregate.stream_id(candidate["skillId"])
        replay = self._idempotent_projection(stream, "candidate", metadata)
        if replay is not None:
            return replay
        if self.store.aggregate_version(stream) != 0:
            raise AuthorityViolation("SKILL_CANDIDATE_ID_ALREADY_EXISTS")
        if self.store.load_state(BotAggregate.stream_id(str(candidate["botId"]))) is None:
            raise AuthorityViolation("SKILL_CANDIDATE_BOT_NOT_FOUND")
        state = SkillCandidateAggregate.create(candidate)
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1", stream_id=stream,
            event_type="SkillCandidateCreated",
            payload={"eventType": "SkillCandidateCreated", "candidate": candidate},
            metadata=metadata, occurred_at=metadata["issuedAt"],
        )
        result = self._commit(
            [AppendRequest(stream, SkillCandidateAggregate.KIND, 0, event, state)], metadata
        )
        return {**result, "candidate": state}

    def transition_skill_candidate(
        self, skill_id: str, to_state: str, reason: Optional[str],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        require("CommandMetadata", metadata)
        require_authority("transition_skill_candidate", metadata["actor"]["kind"])
        stream = SkillCandidateAggregate.stream_id(skill_id)
        replay = self._idempotent_projection(stream, "candidate", metadata)
        if replay is not None:
            return replay
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)
        state = SkillCandidateAggregate.transition(current, to_state, metadata["actor"], reason)
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1", stream_id=stream,
            event_type="SkillCandidateTransitioned",
            payload={"eventType": "SkillCandidateTransitioned", "skillId": skill_id,
                     "fromState": current["lifecycleState"], "toState": to_state,
                     "actor": metadata["actor"], "reason": reason},
            metadata=metadata, occurred_at=metadata["issuedAt"],
        )
        result = self._commit(
            [AppendRequest(stream, SkillCandidateAggregate.KIND, expected, event, state)], metadata
        )
        return {**result, "candidate": state}

    def create_lab_board_item(
        self, item: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("LabBoardItem", item)
        require("CommandMetadata", metadata)
        require_authority("create_lab_board_item", metadata["actor"]["kind"])
        stream = LabBoardAggregate.stream_id(item["itemId"])
        replay = self._idempotent_projection(stream, "item", metadata)
        if replay is not None:
            return replay
        if self.store.aggregate_version(stream) != 0:
            raise AuthorityViolation("LAB_BOARD_ITEM_ID_ALREADY_EXISTS")
        mission_id = item.get("missionId")
        if mission_id is not None and self.store.load_state(MissionAggregate.stream_id(str(mission_id))) is None:
            raise AuthorityViolation("LAB_BOARD_MISSION_NOT_FOUND")
        state = LabBoardAggregate.create(item)
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1", stream_id=stream,
            event_type="LabBoardItemCreated",
            payload={"eventType": "LabBoardItemCreated", "item": item},
            metadata=metadata, occurred_at=metadata["issuedAt"],
            mission_id=item.get("missionId"),
        )
        result = self._commit(
            [AppendRequest(stream, LabBoardAggregate.KIND, 0, event, state)], metadata
        )
        return {**result, "item": state}

    def transition_lab_board_item(
        self, item_id: str, to_state: str, reason: Optional[str],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        require("CommandMetadata", metadata)
        require_authority("transition_lab_board_item", metadata["actor"]["kind"])
        stream = LabBoardAggregate.stream_id(item_id)
        replay = self._idempotent_projection(stream, "item", metadata)
        if replay is not None:
            return replay
        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)
        state = LabBoardAggregate.transition(
            current, to_state, metadata["actor"], reason, metadata["issuedAt"]
        )
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1", stream_id=stream,
            event_type="LabBoardItemTransitioned",
            payload={"eventType": "LabBoardItemTransitioned", "itemId": item_id,
                     "fromState": current["state"], "toState": to_state,
                     "actor": metadata["actor"], "reason": reason},
            metadata=metadata, occurred_at=metadata["issuedAt"],
            mission_id=current.get("missionId"),
        )
        result = self._commit(
            [AppendRequest(stream, LabBoardAggregate.KIND, expected, event, state)], metadata
        )
        return {**result, "item": state}

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
                "authorizedBy": metadata["actor"]["actorId"],
                "authorizedAt": metadata["issuedAt"],
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
            payload={
                "eventType": "ArtifactPromotionAdopted",
                "promotionId": promotion_id,
                "receipt": receipt,
                "adoptedAt": metadata["issuedAt"],
            },
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
            payload={
                "eventType": "ArtifactPromotionDiscarded",
                "promotionId": promotion_id,
                "reason": reason,
                "discardedAt": metadata["issuedAt"],
            },
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
        )
        result = self._commit(
            [AppendRequest(stream, ArtifactPromotionAggregate.KIND, expected, event, state)], metadata
        )
        return {**result, "promotion": state}

    def persist_cohort_snapshot(
        self,
        snapshot: Dict[str, Any],
        claim_id: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Durably persist Cohort state and admit its evidence atomically.

        The Cohort state stream and Claim evidence link commit under one outer
        idempotency identity. A crash cannot leave a claim pointing at Cohort
        evidence whose authoritative Cohort state was never persisted.
        """
        require_authority("persist_cohort", metadata["actor"]["kind"])
        cohort_id = str(snapshot["cohortId"])
        stream = CohortAggregate.stream_id(cohort_id)
        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            offered = metadata.get("operationFingerprint")
            if offered and prior["operation_fingerprint"] != offered:
                raise IdempotencyConflict("cohort persistence idempotency conflict")
            return {
                "status": "idempotent",
                "cohort": self.store.load_state(stream),
                "claim": self.store.load_state(ClaimAggregate.stream_id(claim_id)),
            }

        expected = self.store.aggregate_version(stream)
        offered = dict(snapshot)
        if offered.get("evidenceIds"):
            raise AuthorityViolation("cohort snapshot may not supply evidence authority")
        if expected == 0:
            if offered.get("latestSteer") is not None:
                raise AuthorityViolation("initial cohort snapshot may not supply steering authority")
            state = CohortAggregate.create(offered)
            event_type = "CohortCreated"
        else:
            current = self.store.require_state(stream)
            for field in ("required", "roster", "participantCap", "roundCap"):
                offered_value = offered.get(field)
                current_value = current.get(field)
                if field in ("required", "roster"):
                    if sorted(set(offered_value or [])) != sorted(set(current_value or [])):
                        raise AuthorityViolation("cohort quorum/roster/cap configuration is immutable after creation")
                elif int(offered_value) != int(current_value):
                    raise AuthorityViolation("cohort quorum/roster/cap configuration is immutable after creation")
            if int(offered.get("epoch", 0)) != int(current.get("epoch", 0)):
                raise AuthorityViolation("cohort snapshot persistence may not change deliberation epoch")
            offered_steer = offered.get("latestSteer")
            if offered_steer is not None and offered_steer != current.get("latestSteer"):
                raise AuthorityViolation("cohort snapshot may not forge steering authority")
            offered["latestSteer"] = current.get("latestSteer")
            offered["evidenceIds"] = []
            state = CohortAggregate.replace_snapshot(current, offered)
            event_type = "CohortSnapshotPersisted"

        # Digest excludes evidenceIds so the evidence record is not circular.
        material = {key: value for key, value in state.items() if key != "evidenceIds"}
        state_digest = digest(material)
        evidence_id = "ev-cohort-%s-v%d" % (cohort_id, expected + 1)
        state = CohortAggregate.attach_evidence(state, evidence_id)

        cohort_event = commands.envelope(
            event_id=metadata["commandId"] + "-cohort",
            stream_id=stream,
            event_type=event_type,
            payload={"eventType": event_type, "snapshot": state},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=state["missionId"],
            task_id=state["taskId"],
        )

        claim_stream = ClaimAggregate.stream_id(claim_id)
        claim_expected = self.store.aggregate_version(claim_stream)
        claim_current = self.store.require_state(claim_stream)
        claim_state = ClaimAggregate.attach_evidence(claim_current, evidence_id)
        evidence_meta = self._inner_metadata(
            metadata,
            "record_evidence",
            {"claimId": claim_id, "evidenceId": evidence_id},
            "system",
            "capt-runtime",
            "cohort-evidence",
        )
        evidence = {
            "schemaVersion": "1.0.0",
            "evidenceId": evidence_id,
            "missionId": state["missionId"],
            "evidence": {
                "kind": "artifact_hash",
                "artifactPath": "/cohort/" + cohort_id,
                "artifactDigest": state_digest,
            },
            "collectedBy": {"actorId": "capt-runtime", "kind": "system"},
            "collectedAt": metadata["issuedAt"],
            "trust": "capt_authoritative",
        }
        require("EvidenceRecord", evidence)
        evidence_event = commands.envelope(
            event_id=metadata["commandId"] + "-evidence",
            stream_id=claim_stream,
            event_type="EvidenceRecorded",
            payload={"eventType": "EvidenceRecorded", "evidence": evidence},
            metadata=evidence_meta,
            occurred_at=metadata["issuedAt"],
            mission_id=state["missionId"],
            claim_id=claim_id,
        )

        result = self._commit(
            [
                AppendRequest(stream, CohortAggregate.KIND, expected, cohort_event, state),
                AppendRequest(claim_stream, ClaimAggregate.KIND, claim_expected, evidence_event, claim_state),
            ],
            metadata,
        )
        return {**result, "cohort": state, "evidence": evidence, "claim": claim_state}
