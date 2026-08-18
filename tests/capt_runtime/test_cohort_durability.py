"""Discriminating durability tests for CAPT-UPG-010."""
from __future__ import annotations

import pytest

from capt_runtime import commands
from capt_runtime.cohort import (
    BoundedCohort,
    Contribution,
    ContributionOutcome,
    DeliberationEpoch,
    load_cohort_state,
    persist_cohort_evidence,
)
from capt_runtime.errors import AuthorityViolation
from capt_runtime.governed_service import GovernedRuntimeService
from capt_runtime.replay import full_replay
from capt_runtime.store import EventStore


def _meta(name: str, *, kind: str = "system", idem: str | None = None):
    return commands.command(
        command_id="cmd-" + name,
        idempotency_key=idem or ("idem-" + name),
        operation_fingerprint=commands.fingerprint(name, {"name": name}),
        correlation_id="corr-cohort",
        actor_id="capt-runtime" if kind == "system" else "cog-1",
        actor_kind=kind,
        issued_at="2026-08-18T00:00:00Z",
        replay_policy="never",
    )


def _seed_claim(store: EventStore, claim_id: str = "cl-cohort") -> None:
    svc = GovernedRuntimeService(store)
    claim = {
        "schemaVersion": "1.0.0",
        "claimId": claim_id,
        "missionId": "m-cohort",
        "kind": "completion",
        "statement": "Cohort produced a bounded deliberation result.",
        "evidenceIds": [],
        "promotionState": "proposed",
        "proposedBy": {"actorId": "capt-runtime", "kind": "system"},
        "proposedAt": "2026-08-18T00:00:00Z",
    }
    svc.propose_claim(claim, _meta("claim"))


def _cohort() -> tuple[BoundedCohort, DeliberationEpoch]:
    epoch = DeliberationEpoch("m-cohort", "t-cohort")
    cohort = BoundedCohort(
        required={"planner", "critic"},
        roster={"planner", "critic"},
        participant_cap=2,
        round_cap=3,
    )
    cohort.record(Contribution("c-1", "planner", 0, 0, ContributionOutcome.PASS, 10))
    cohort.record(Contribution("c-2", "critic", 0, 0, ContributionOutcome.PASS, 11))
    return cohort, epoch


def test_cohort_state_and_claim_evidence_commit_then_reconstruct_after_reopen(tmp_path):
    db = str(tmp_path / "cohort.db")
    store = EventStore(db)
    _seed_claim(store)
    cohort, epoch = _cohort()

    state = persist_cohort_evidence(
        "coh-1", cohort, epoch, "cl-cohort", store, _meta("persist-1")
    )
    assert state["cohortId"] == "coh-1"
    assert state["stoppingReason"] == "SILENCE_QUORUM"
    assert state["participantCursors"] == {"planner": 10, "critic": 11}
    assert store.aggregate_version("cohort-coh-1") == 1
    claim = store.require_state("claim-cl-cohort")
    assert state["evidenceIds"][0] in claim["evidenceIds"]
    store.close()

    reopened = EventStore(db)
    rebuilt = load_cohort_state("coh-1", reopened)
    assert rebuilt is not None
    rebuilt_cohort, rebuilt_epoch = rebuilt
    assert rebuilt_epoch.epoch == 0
    assert rebuilt_cohort.stopping_reason(rebuilt_epoch) == "SILENCE_QUORUM"
    assert {c.contribution_id for c in rebuilt_cohort.contributions} == {"c-1", "c-2"}

    replay = full_replay(reopened)
    assert replay.aggregates["cohort-coh-1"] == reopened.require_state("cohort-coh-1")
    reopened.close()


def test_cohort_can_continue_after_restart_without_duplicate_contribution_or_evidence(tmp_path):
    db = str(tmp_path / "cohort.db")
    store = EventStore(db)
    _seed_claim(store)
    cohort, epoch = _cohort()
    persist_cohort_evidence("coh-2", cohort, epoch, "cl-cohort", store, _meta("persist-a"))
    store.close()

    reopened = EventStore(db)
    rebuilt = load_cohort_state("coh-2", reopened)
    assert rebuilt is not None
    cohort2, epoch2 = rebuilt
    cohort2.next_round()
    cohort2.record(Contribution("c-3", "planner", 0, 1, ContributionOutcome.PASS, 20))
    cohort2.record(Contribution("c-4", "critic", 0, 1, ContributionOutcome.PASS, 21))
    persist_cohort_evidence("coh-2", cohort2, epoch2, "cl-cohort", reopened, _meta("persist-b"))

    assert reopened.aggregate_version("cohort-coh-2") == 2
    state = reopened.require_state("cohort-coh-2")
    assert [c["contributionId"] for c in state["contributions"]] == ["c-1", "c-2", "c-3", "c-4"]
    assert len(state["evidenceIds"]) == 2

    # Exact retry is idempotent and does not create a third event/evidence link.
    result = GovernedRuntimeService(reopened).persist_cohort_snapshot(
        {
            **state,
            "evidenceIds": [],
        },
        "cl-cohort",
        _meta("persist-b"),
    )
    assert result["status"] == "idempotent"
    assert reopened.aggregate_version("cohort-coh-2") == 2
    reopened.close()


def test_cohort_cursor_regression_and_contribution_deletion_fail_closed(tmp_path):
    store = EventStore(str(tmp_path / "cohort.db"))
    _seed_claim(store)
    cohort, epoch = _cohort()
    persist_cohort_evidence("coh-3", cohort, epoch, "cl-cohort", store, _meta("persist-x"))
    current = store.require_state("cohort-coh-3")

    bad = {**current, "contributions": [dict(current["contributions"][0])], "evidenceIds": []}
    with pytest.raises(AuthorityViolation):
        GovernedRuntimeService(store).persist_cohort_snapshot(
            bad, "cl-cohort", _meta("persist-delete")
        )

    bad_cursor = {
        **current,
        "participantCursors": {**current["participantCursors"], "planner": 1},
        "evidenceIds": [],
    }
    with pytest.raises((AuthorityViolation, ValueError)):
        GovernedRuntimeService(store).persist_cohort_snapshot(
            bad_cursor, "cl-cohort", _meta("persist-regress")
        )
    store.close()
