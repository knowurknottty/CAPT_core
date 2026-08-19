"""Discriminating command-path tests for CAPT-UPG-011."""
from __future__ import annotations

from capt_runtime import commands
from capt_runtime.cohort import (
    BoundedCohort,
    Contribution,
    ContributionOutcome,
    DeliberationEpoch,
    load_cohort_state,
    persist_cohort_evidence,
)
from capt_runtime.composition import create_runtime
from capt_runtime.steered_service import SteeredRuntimeService
from capt_runtime.store import EventStore


def _meta(name: str):
    return commands.command(
        command_id="cmd-" + name,
        idempotency_key="idem-" + name,
        operation_fingerprint=commands.fingerprint(name, {"name": name}),
        correlation_id="corr-steer",
        actor_id="capt-runtime",
        actor_kind="system",
        issued_at="2026-08-18T00:00:00Z",
        replay_policy="never",
    )


def _seed_claim_and_cohort(store: EventStore, cohort_id: str = "coh-steer") -> None:
    svc = SteeredRuntimeService(store)
    claim = {
        "schemaVersion": "1.0.0",
        "claimId": "cl-steer",
        "missionId": "m-steer",
        "kind": "completion",
        "statement": "Cohort steering test claim.",
        "evidenceIds": [],
        "promotionState": "proposed",
        "proposedBy": {"actorId": "capt-runtime", "kind": "system"},
        "proposedAt": "2026-08-18T00:00:00Z",
    }
    svc.propose_claim(claim, _meta("claim"))

    epoch = DeliberationEpoch("m-steer", "t-steer")
    cohort = BoundedCohort(
        required={"planner", "critic"},
        roster={"planner", "critic"},
        participant_cap=2,
        round_cap=3,
    )
    cohort.record(Contribution("c-old-1", "planner", 0, 0, ContributionOutcome.PASS, 5))
    cohort.record(Contribution("c-old-2", "critic", 0, 0, ContributionOutcome.PASS, 6))
    persist_cohort_evidence(cohort_id, cohort, epoch, "cl-steer", store, _meta("persist"))


def _steer_command(directive: str = "Focus on security closure", idem: str = "idem-steer-command"):
    return {
        "schemaVersion": "1.0.0",
        "commandId": "cmd-steer-command",
        "operatorId": "operator-1",
        "sessionId": "session-1",
        "correlationId": "corr-steer",
        "idempotencyKey": idem,
        "timestamp": "2026-08-18T00:01:00Z",
        "op": "steer_deliberation",
        "payload": {
            "cohortId": "coh-steer",
            "directive": directive,
            "reason": "operator correction",
        },
    }


def test_operator_command_causes_authoritative_epoch_transition_and_restart_preserves_it(tmp_path):
    ledger = str(tmp_path / "steer.db")
    runtime = create_runtime(ledger)
    _seed_claim_and_cohort(runtime.store)
    before_streams = list(runtime.store.all_aggregates())
    before_capability_streams = sorted(s for s, kind, _ in before_streams if kind == "capability")

    command_service = runtime.command_service("operator-1", "session-1")
    receipt = command_service.execute(_steer_command())
    assert receipt["status"] == "accepted", receipt
    assert receipt["streamId"] == "cohort-coh-steer"
    assert receipt["result"]["epoch"] == 1

    state = runtime.store.require_state("cohort-coh-steer")
    assert state["epoch"] == 1
    assert state["latestSteer"]["directive"] == "Focus on security closure"
    assert state["latestSteer"]["steeredBy"] == "operator-1"

    # Old PASSes remain durable evidence but are stale in the new epoch.
    rebuilt = load_cohort_state("coh-steer", runtime.store)
    assert rebuilt is not None
    cohort, epoch = rebuilt
    assert epoch.epoch == 1
    assert cohort.stopping_reason(epoch) is None
    assert all(not c.admissible_current(epoch) for c in cohort.contributions)

    after_capability_streams = sorted(
        s for s, kind, _ in runtime.store.all_aggregates() if kind == "capability"
    )
    assert after_capability_streams == before_capability_streams
    version_after_steer = runtime.store.aggregate_version("cohort-coh-steer")
    runtime.close()

    reopened = EventStore(ledger)
    restored = reopened.require_state("cohort-coh-steer")
    assert restored["epoch"] == 1
    assert restored["latestSteer"]["directive"] == "Focus on security closure"
    assert reopened.aggregate_version("cohort-coh-steer") == version_after_steer
    reopened.close()


def test_exact_steer_retry_is_idempotent_and_conflicting_replay_is_rejected(tmp_path):
    ledger = str(tmp_path / "steer.db")
    runtime = create_runtime(ledger)
    _seed_claim_and_cohort(runtime.store)
    command_service = runtime.command_service("operator-1", "session-1")

    first = command_service.execute(_steer_command())
    assert first["status"] == "accepted"
    version = runtime.store.aggregate_version("cohort-coh-steer")

    same = command_service.execute(_steer_command())
    assert same["status"] == "idempotent"
    assert same["result"]["epoch"] == 1
    assert runtime.store.aggregate_version("cohort-coh-steer") == version

    conflict = command_service.execute(
        _steer_command(directive="Silently expand filesystem authority")
    )
    assert conflict["status"] == "rejected"
    assert runtime.store.aggregate_version("cohort-coh-steer") == version
    state = runtime.store.require_state("cohort-coh-steer")
    assert state["latestSteer"]["directive"] == "Focus on security closure"
    runtime.close()


def test_unauthenticated_identity_cannot_steer(tmp_path):
    runtime = create_runtime(str(tmp_path / "steer.db"))
    _seed_claim_and_cohort(runtime.store)
    command_service = runtime.command_service("operator-1", "session-1")
    cmd = _steer_command()
    cmd["operatorId"] = "other-operator"
    receipt = command_service.execute(cmd)
    assert receipt["status"] == "rejected"
    assert receipt["classification"] == "unauthorized"
    assert runtime.store.require_state("cohort-coh-steer")["epoch"] == 0
    runtime.close()


def test_steered_cohort_full_replay_preserves_human_epoch_transition(tmp_path):
    from capt_runtime.replay import full_replay

    runtime = create_runtime(str(tmp_path / "steer-replay.db"))
    _seed_claim_and_cohort(runtime.store)
    receipt = runtime.command_service("operator-1", "session-1").execute(_steer_command())
    assert receipt["status"] == "accepted"
    replay = full_replay(runtime.store)
    state = replay.aggregates["cohort-coh-steer"]
    assert state["epoch"] == 1
    assert state["latestSteer"]["steeredBy"] == "operator-1"
    assert state["latestSteer"]["directive"] == "Focus on security closure"
    runtime.close()
