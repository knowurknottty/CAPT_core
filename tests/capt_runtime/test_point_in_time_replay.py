"""CAPT-UPG-016 regression tests for exact historical replay."""
from __future__ import annotations

from capt_runtime import commands
from capt_runtime.replay import checkpoint_replay, full_replay, replay_equivalent
from capt_runtime.scenario import TASK_ID, build_scenario
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore


def _transition_meta(command_id: str):
    return commands.command(
        command_id=command_id,
        idempotency_key="idem-" + command_id,
        operation_fingerprint=commands.fingerprint(
            "transition_task", {"taskId": TASK_ID, "to": "succeeded"}
        ),
        correlation_id="corr-upg016",
        actor_id="exec-upg016",
        actor_kind="execution_plane",
        issued_at="2026-08-18T07:32:00Z",
        replay_policy="never",
    )


def test_checkpoint_replay_uses_historical_state_before_folding_post_checkpoint_tail(tmp_path):
    db = str(tmp_path / "runtime.db")
    build_scenario(db)

    store = EventStore(db)
    manifest = store.load_checkpoint("cp-m0a-001")
    checkpoint_position = manifest["ledgerPosition"]["globalSequence"]
    checkpoint_task_version = next(
        item["version"] for item in manifest["taskVersions"]
        if item["streamId"] == "task-" + TASK_ID
    )

    # Mutate the same stream AFTER the checkpoint. A correct checkpoint replay
    # must reconstruct the task as it was at checkpoint_task_version and only
    # then fold this tail transition.
    RuntimeService(store).transition_task(
        TASK_ID,
        "succeeded",
        "post-checkpoint completion",
        _transition_meta("upg016-tail-succeeded"),
    )
    assert store.head_sequence() > checkpoint_position
    assert store.require_state("task-" + TASK_ID)["state"] == "succeeded"
    assert store.aggregate_version("task-" + TASK_ID) > checkpoint_task_version

    full = full_replay(store)
    partial = checkpoint_replay(store, manifest)

    assert replay_equivalent(full, partial)
    assert partial.aggregates["task-" + TASK_ID]["state"] == "succeeded"
    store.close()


def test_linear_replay_fork_creates_new_history_without_reactivating_historical_authority(tmp_path):
    from copy import deepcopy

    from capt_runtime.replay import ledger_identity_to_sequence, replay_to_sequence
    from capt_runtime.scenario import mission_spec

    db = str(tmp_path / "fork.db")
    build_scenario(db)
    store = EventStore(db)
    source_sequence = store.load_checkpoint("cp-m0a-001")["ledgerPosition"]["globalSequence"]
    source_state = replay_to_sequence(store, source_sequence)
    source_digest = source_state.digest()
    source_mission_before = deepcopy(store.require_state("mission-m-m0a-001"))
    capability_streams_before = {
        stream_id for stream_id, kind, _ in store.all_aggregates() if kind == "capability"
    }
    before_head = store.head_sequence()

    fork_mission = deepcopy(mission_spec())
    fork_mission["missionId"] = "m-fork-001"
    fork_mission["rawRequest"] = "Continue from historical state along an alternate governed path."
    fork_mission["normalizedRequest"] = "continue from historical state along alternate governed path"
    fork_mission["createdAt"] = "2026-08-18T07:34:00Z"

    meta = commands.command(
        command_id="cmd-replay-fork-001",
        idempotency_key="idem-replay-fork-001",
        operation_fingerprint=commands.fingerprint(
            "create_replay_fork",
            {
                "forkId": "fork-001",
                "sourceSequence": source_sequence,
                "newMissionId": fork_mission["missionId"],
                "reason": "operator alternate-path investigation",
            },
        ),
        correlation_id="corr-replay-fork-001",
        actor_id="captain",
        actor_kind="human",
        issued_at="2026-08-18T07:34:00Z",
        replay_policy="never",
    )

    result = RuntimeService(store).create_replay_fork(
        "fork-001",
        source_sequence,
        fork_mission,
        "operator alternate-path investigation",
        meta,
    )

    assert result["status"] == "applied"
    assert store.head_sequence() == before_head + 2
    fork_state = store.require_state("replay_fork-fork-001")
    assert fork_state["sourceSequence"] == source_sequence
    assert fork_state["sourceStateDigest"] == source_digest
    assert fork_state["sourceChainDigest"] == ledger_identity_to_sequence(
        store, source_sequence
    )["chainDigest"]
    assert fork_state["newMissionId"] == "m-fork-001"
    assert fork_state["historicalAuthorityReactivated"] is False
    assert fork_state["state"] == "created"

    new_mission = store.require_state("mission-m-fork-001")
    assert new_mission["state"] == "draft"
    assert store.require_state("mission-m-m0a-001") == source_mission_before
    capability_streams_after = {
        stream_id for stream_id, kind, _ in store.all_aggregates() if kind == "capability"
    }
    assert capability_streams_after == capability_streams_before

    # Appending the fork must not alter the historical replay prefix.
    assert replay_to_sequence(store, source_sequence).digest() == source_digest
    store.close()


def test_checkpoint_replay_rejects_manifest_with_wrong_historical_ledger_anchor(tmp_path):
    from copy import deepcopy

    import pytest

    from capt_runtime.checkpoint import manifest_integrity_digest
    from capt_runtime.errors import IntegrityViolation

    db = str(tmp_path / "anchor.db")
    build_scenario(db)
    store = EventStore(db)
    manifest = deepcopy(store.load_checkpoint("cp-m0a-001"))

    # Keep the manifest internally self-consistent while lying about the ledger
    # prefix it claims to represent. Replay must bind the checkpoint to the
    # actual append-only history, not trust a recomputed manifest digest alone.
    manifest["ledgerDigest"] = "sha256:" + "f" * 64
    manifest["integrityDigest"] = manifest_integrity_digest(manifest)

    with pytest.raises(IntegrityViolation, match="ledger digest"):
        checkpoint_replay(store, manifest)
    store.close()


def test_checkpoint_replay_rejects_manifest_with_wrong_historical_event_id(tmp_path):
    from copy import deepcopy

    import pytest

    from capt_runtime.checkpoint import manifest_integrity_digest
    from capt_runtime.errors import IntegrityViolation

    db = str(tmp_path / "event-anchor.db")
    build_scenario(db)
    store = EventStore(db)
    manifest = deepcopy(store.load_checkpoint("cp-m0a-001"))
    manifest["ledgerPosition"]["eventId"] = "ev-not-the-checkpoint-head"
    manifest["integrityDigest"] = manifest_integrity_digest(manifest)

    with pytest.raises(IntegrityViolation, match="eventId"):
        checkpoint_replay(store, manifest)
    store.close()
