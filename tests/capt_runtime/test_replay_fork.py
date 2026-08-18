"""CAPT-UPG-016 tests for point-in-time replay and linear fork preparation."""

from copy import deepcopy

import pytest

from capt_runtime import scenario
from capt_runtime.errors import IntegrityViolation
from capt_runtime.replay_fork import (
    prepare_linear_fork,
    replay_at_sequence,
    verify_linear_fork,
)
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore


def _scenario_store(tmp_path):
    db = tmp_path / "runtime.db"
    scenario.build_scenario(str(db))
    return EventStore(str(db))


def test_point_in_time_replay_excludes_future_events_and_is_read_only(tmp_path):
    store = _scenario_store(tmp_path)
    before_head = store.head_sequence()
    before_chain = store.head_chain()

    early = replay_at_sequence(store, 1)
    current = replay_at_sequence(store, before_head)

    assert early.applied == 1
    assert early.digest() != current.digest()
    assert store.head_sequence() == before_head
    assert store.head_chain() == before_chain
    store.close()


def test_linear_fork_binds_source_prefix_and_allows_later_source_appends(tmp_path):
    store = _scenario_store(tmp_path)
    selected = store.head_sequence()
    checkpoint = store.latest_checkpoint()
    assert checkpoint is not None
    before_head = store.head_sequence()

    manifest = prepare_linear_fork(
        store,
        fork_id="fork-1",
        selected_sequence=selected,
        created_at="2026-08-18T00:00:00Z",
        checkpoint_manifest=checkpoint,
        requested_continuation={"operatorIntent": "Explore an alternate next step."},
    )

    assert store.head_sequence() == before_head
    assert manifest["authority"]["rewritesHistory"] is False
    assert manifest["authority"]["mayDispatch"] is False
    assert manifest["authority"]["requiresGovernedAdoption"] is True
    assert verify_linear_fork(store, manifest)["sourcePrefixVerified"] is True

    # Legal source history may grow after preparation without invalidating the
    # historical prefix the fork references.
    service = RuntimeService(store)
    service.transition_task(
        scenario.TASK_ID,
        "suspended",
        "operator paused after fork preparation",
        scenario._meta(
            "fork-later-suspend",
            scenario.EXECUTION_ACTOR,
            "2026-08-18T00:01:00Z",
            "transition_task",
            {"taskId": scenario.TASK_ID, "to": "suspended"},
        ),
    )
    assert store.head_sequence() > selected
    verified = verify_linear_fork(store, manifest)
    assert verified["selectedSequence"] == selected
    assert verified["laterSourceEventsAllowed"] is True
    store.close()


def test_linear_fork_rejects_manifest_tamper_and_future_sequence(tmp_path):
    store = _scenario_store(tmp_path)
    manifest = prepare_linear_fork(
        store,
        fork_id="fork-2",
        selected_sequence=store.head_sequence(),
        created_at="2026-08-18T00:00:00Z",
    )

    tampered = deepcopy(manifest)
    tampered["source"]["selectedChainDigest"] = "sha256:" + "f" * 64
    with pytest.raises(IntegrityViolation, match="manifest digest mismatch"):
        verify_linear_fork(store, tampered)

    with pytest.raises(ValueError, match="exceeds ledger head"):
        prepare_linear_fork(
            store,
            fork_id="future",
            selected_sequence=store.head_sequence() + 1,
            created_at="2026-08-18T00:00:00Z",
        )
    store.close()


def test_checkpoint_newer_than_selected_sequence_is_rejected(tmp_path):
    store = _scenario_store(tmp_path)
    checkpoint = store.latest_checkpoint()
    assert checkpoint is not None
    checkpoint_sequence = checkpoint["ledgerPosition"]["globalSequence"]
    assert checkpoint_sequence > 0

    with pytest.raises(IntegrityViolation, match="newer than selected"):
        prepare_linear_fork(
            store,
            fork_id="fork-old",
            selected_sequence=checkpoint_sequence - 1,
            created_at="2026-08-18T00:00:00Z",
            checkpoint_manifest=checkpoint,
        )
    store.close()
