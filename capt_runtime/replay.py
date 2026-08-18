"""Deterministic state reconstruction from the event ledger (ADR-0108).

Two paths, guaranteed to agree:
  * full replay      — fold every event from the origin
  * checkpoint replay — trust a verified checkpoint, fold only the tail

Reducers are pure and idempotent at the (stream, version) level, so applying
a duplicate event is a no-op rather than a double-count.
"""

from __future__ import annotations

from typing import Any, Dict

from .aggregates import (
    ArtifactPromotionAggregate,
    CapabilityAggregate,
    ClaimAggregate,
    DriverRunAggregate,
    MissionAggregate,
    TaskAggregate,
)
from .checkpoint import verify_checkpoint
from .contracts import digest
from .errors import IntegrityViolation
from .store import EventStore


class ReplayState(object):
    """Rebuilt runtime state plus the versions it was rebuilt to."""

    __slots__ = ("aggregates", "versions", "applied", "skipped")

    def __init__(self) -> None:
        self.aggregates: Dict[str, Dict[str, Any]] = {}
        self.versions: Dict[str, int] = {}
        self.applied = 0
        self.skipped = 0

    def digest(self) -> str:
        """Content digest of the whole rebuilt state, for equivalence tests."""
        return digest(
            {
                "aggregates": self.aggregates,
                "versions": self.versions,
            }
        )

    def summary(self) -> Dict[str, Any]:
        return {
            "streams": len(self.aggregates),
            "applied": self.applied,
            "skipped": self.skipped,
            "digest": self.digest(),
        }


_CREATION_EVENTS = frozenset(
    {
        "MissionCreated",
        "TaskCreated",
        "CapabilityGranted",
        "DriverRunCreated",
        "ClaimCreated",
        "HumanApprovalRequested",
        "ArtifactPromotionPrepared",
    }
)

# Aggregate kinds omitted from the frozen CheckpointManifest must be rebuilt
# from their events up to the checkpoint before the normal tail is applied.
_CHECKPOINT_EXTENSION_EVENTS = frozenset(
    {
        "HumanApprovalRequested",
        "HumanApprovalDecided",
        "ArtifactPromotionPrepared",
        "ArtifactPromotionAuthorized",
        "ArtifactPromotionAdopted",
        "ArtifactPromotionDiscarded",
    }
)


def _apply(state: ReplayState, envelope: Dict[str, Any]) -> None:
    """Fold one event. Duplicate or stale events are skipped, not applied."""
    stream_id = envelope["streamId"]
    version = envelope["streamVersion"]
    current_version = state.versions.get(stream_id, 0)

    if version <= current_version:
        state.skipped += 1
        return
    if version != current_version + 1:
        raise IntegrityViolation(
            "gap in stream %s: have version %d, next event is %d"
            % (stream_id, current_version, version)
        )

    payload = envelope["payload"]
    event_type = payload["eventType"]
    current = state.aggregates.get(stream_id)

    if event_type not in _CREATION_EVENTS and current is None:
        raise IntegrityViolation(
            "event %s (%s) mutates stream %s which has no prior state"
            % (envelope["eventId"], event_type, stream_id)
        )

    def existing() -> Dict[str, Any]:
        assert current is not None
        return current

    if event_type == "MissionCreated":
        nxt = MissionAggregate.create(payload["missionSpec"])
    elif event_type == "PolicyEvaluated":
        nxt = MissionAggregate.record_policy_decision(
            existing(), payload["policyDecision"]["policyDecisionId"]
        )
        if nxt["state"] == "draft" and payload["policyDecision"]["effect"] in (
            "allow",
            "allow_with_conditions",
        ):
            nxt = MissionAggregate.transition(nxt, "authorized")
    elif event_type == "MissionStateChanged":
        nxt = MissionAggregate.transition(existing(), payload["toState"])
    elif event_type == "TaskCreated":
        nxt = TaskAggregate.create(payload["task"])
    elif event_type == "TaskTransitioned":
        nxt = TaskAggregate.transition(existing(), payload["toState"])
    elif event_type == "TaskResultSubmitted":
        nxt = TaskAggregate.record_result(existing(), payload["resultRef"])
        nxt = TaskAggregate.transition(nxt, payload["toState"])
    elif event_type == "CapabilityGranted":
        nxt = CapabilityAggregate.grant(payload["grant"])
    elif event_type == "CapabilityLeaseActivated":
        nxt = CapabilityAggregate.activate_lease(existing(), payload["lease"])
    elif event_type == "CapabilityUseReserved":
        nxt = CapabilityAggregate.reserve(
            existing(), payload["reservation"], payload["reservation"]["reservedAt"]
        )
    elif event_type == "CapabilityUseFinalized":
        nxt = CapabilityAggregate.finalize(existing(), payload["consumption"])
    elif event_type in ("CapabilityGrantRevoked", "CapabilityLeaseRevoked"):
        nxt = CapabilityAggregate.revoke(existing(), payload["revocation"])
    elif event_type == "DriverRunCreated":
        nxt = DriverRunAggregate.create(payload["driverRun"])
    elif event_type == "DriverRunStateChanged":
        nxt = DriverRunAggregate.transition(existing(), payload["toState"])
    elif event_type == "ClaimCreated":
        nxt = ClaimAggregate.propose(payload["claim"])
    elif event_type == "EvidenceRecorded":
        nxt = ClaimAggregate.attach_evidence(
            existing(), payload["evidence"]["evidenceId"]
        )
    elif event_type == "ClaimVerified":
        nxt = ClaimAggregate.record_verification(existing(), payload["verification"])
    elif event_type == "ClaimGuardDecided":
        nxt = ClaimAggregate.decide(existing(), payload["decision"])
    elif event_type == "HumanApprovalRequested":
        from capt_runtime.aggregates.human_approval import HumanApprovalAggregate
        nxt = HumanApprovalAggregate.create(payload["request"])
    elif event_type == "HumanApprovalDecided":
        from capt_runtime.aggregates.human_approval import HumanApprovalAggregate
        nxt = HumanApprovalAggregate.decide(
            existing(), payload["decision"],
            payload.get("decidedAt") or envelope.get("recordedAt", "")
        )
    elif event_type == "ArtifactPromotionPrepared":
        nxt = ArtifactPromotionAggregate.prepare(payload["promotion"])
    elif event_type == "ArtifactPromotionAuthorized":
        nxt = ArtifactPromotionAggregate.authorize(
            existing(), payload["authorizedBy"], payload["authorizedAt"]
        )
    elif event_type == "ArtifactPromotionAdopted":
        nxt = ArtifactPromotionAggregate.adopt(
            existing(), payload["receipt"], payload["adoptedAt"]
        )
    elif event_type == "ArtifactPromotionDiscarded":
        nxt = ArtifactPromotionAggregate.discard(
            existing(), payload["reason"], payload["discardedAt"]
        )
    elif event_type in ("CheckpointCreated", "MissionResumed"):
        nxt = existing()
    else:
        raise IntegrityViolation("no reducer for event type %r" % event_type)

    state.aggregates[stream_id] = nxt
    state.versions[stream_id] = version
    state.applied += 1


def full_replay(store: EventStore) -> ReplayState:
    """Fold the entire ledger from the origin."""
    store.verify_chain()
    state = ReplayState()
    for envelope in store.read_events(after_sequence=0):
        _apply(state, envelope)
    return state


def checkpoint_replay(
    store: EventStore, manifest: Dict[str, Any]
) -> ReplayState:
    """Load a verified checkpoint's known streams, rebuild extension streams, fold tail.

    The frozen CheckpointManifest does not yet carry human-approval or
    Sol-Reconciliation extension stream versions. Those streams are replayed
    from origin through the checkpoint position; normal checkpointed streams
    continue using the existing checkpoint seed path.
    """
    verify_checkpoint(manifest)
    store.verify_chain()

    state = ReplayState()
    for field in (
        "missionVersions",
        "taskVersions",
        "capabilityVersions",
        "driverRunVersions",
        "claimVersions",
    ):
        for entry in manifest[field]:
            stream_state = store.load_state(entry["streamId"])
            if stream_state is None:
                raise IntegrityViolation(
                    "checkpoint references stream %s that the store does not have"
                    % entry["streamId"]
                )
            state.aggregates[entry["streamId"]] = stream_state
            state.versions[entry["streamId"]] = entry["version"]

    position = manifest["ledgerPosition"]["globalSequence"]

    # Rebuild only extension streams omitted by the frozen checkpoint schema.
    for envelope in store.read_events(after_sequence=0):
        if int(envelope["globalSequence"]) > position:
            break
        if envelope["payload"].get("eventType") in _CHECKPOINT_EXTENSION_EVENTS:
            _apply(state, envelope)

    for envelope in store.read_events(after_sequence=position):
        _apply(state, envelope)
    return state


def replay_equivalent(left: ReplayState, right: ReplayState) -> bool:
    """Deterministic state equality by content digest."""
    return left.digest() == right.digest()
