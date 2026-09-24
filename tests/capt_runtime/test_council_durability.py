from __future__ import annotations

from dataclasses import replace

import pytest

from capt_runtime import commands
from capt_runtime.council import (
    ClaimObservation, ClaimStance, CouncilLaunchAuthorization, CouncilTier,
    analyze_claims, council_digest,
)
from capt_runtime.errors import AuthorityViolation, IdempotencyConflict
from capt_runtime.governed_service import GovernedRuntimeService
from capt_runtime.replay import full_replay
from capt_runtime.store import EventStore
from tests.capt_runtime.test_council_alpha import make_council


def meta(name: str, *, idem: str | None = None, fingerprint: str | None = None):
    return commands.command(
        command_id="cmd-" + name,
        idempotency_key=idem or ("idem-" + name),
        operation_fingerprint=fingerprint or commands.fingerprint(name, {"name": name}),
        correlation_id="corr-council",
        actor_id="capt-runtime", actor_kind="system",
        issued_at="2026-09-10T18:00:00Z", replay_policy="never",
    )

def test_admitted_council_is_durable_idempotent_and_replayable(tmp_path):
    db = str(tmp_path / "council.db")
    store = EventStore(db)
    svc = GovernedRuntimeService(store)
    definition = make_council(CouncilTier.SMALL)
    auth = CouncilLaunchAuthorization(council_digest(definition))

    first = svc.admit_council_plan(definition, auth, meta("admit"))
    assert first["council"]["logicalVesselCount"] == 6
    assert first["council"]["analysisHistory"] == []
    assert store.aggregate_version("council-council-small") == 1

    retry = svc.admit_council_plan(definition, auth, meta("admit"))
    assert retry["status"] == "idempotent"
    assert store.aggregate_version("council-council-small") == 1
    store.close()

    reopened = EventStore(db)
    assert full_replay(reopened).aggregates["council-council-small"] == reopened.require_state("council-council-small")
    reopened.close()

def test_existing_council_identity_cannot_be_rebound_to_new_topology(tmp_path):
    store = EventStore(str(tmp_path / "council-immutable.db"))
    svc = GovernedRuntimeService(store)
    definition = make_council(CouncilTier.SMALL)
    svc.admit_council_plan(
        definition, CouncilLaunchAuthorization(council_digest(definition)), meta("admit-a")
    )
    changed = replace(
        definition,
        cohorts=(replace(definition.cohorts[0], model_id="other-model"),) + definition.cohorts[1:],
    )
    with pytest.raises(AuthorityViolation, match="identity already exists"):
        svc.admit_council_plan(
            changed, CouncilLaunchAuthorization(council_digest(changed)), meta("admit-b")
        )
    store.close()


def test_council_idempotency_key_reuse_with_different_fingerprint_fails(tmp_path):
    store = EventStore(str(tmp_path / "council-idem.db"))
    svc = GovernedRuntimeService(store)
    definition = make_council(CouncilTier.SMALL)
    auth = CouncilLaunchAuthorization(council_digest(definition))
    svc.admit_council_plan(definition, auth, meta("first", idem="idem-fixed", fingerprint="sha256:" + "1" * 64))
    with pytest.raises(IdempotencyConflict):
        svc.admit_council_plan(definition, auth, meta("second", idem="idem-fixed", fingerprint="sha256:" + "2" * 64))
    store.close()

def test_analysis_append_preserves_dissent_raw_observations_and_unverified_state(tmp_path):
    db = str(tmp_path / "council-analysis.db")
    store = EventStore(db)
    svc = GovernedRuntimeService(store)
    definition = make_council(CouncilTier.SMALL)
    svc.admit_council_plan(
        definition, CouncilLaunchAuthorization(council_digest(definition)), meta("admit-analysis")
    )
    analysis = analyze_claims(definition, (
        ClaimObservation("a", "claim A", "c00", "c00-v0001", ClaimStance.SUPPORT, 0.8, ("ev-1",)),
        ClaimObservation("a", "claim A", "c01", "c01-v0001", ClaimStance.DISSENT, 0.9, ("ev-2",)),
    ))

    result = svc.record_council_analysis(definition.council_id, analysis, meta("analysis"))
    recorded = result["council"]["analysisHistory"][0]
    assert recorded["claims"][0]["status"] == "disputed"
    assert recorded["claims"][0]["verificationState"] == "unverified"
    assert {item["stance"] for item in recorded["rawObservations"]} == {"support", "dissent"}
    assert result["council"]["verificationState"] == "unverified"
    store.close()

    reopened = EventStore(db)
    replayed = full_replay(reopened).aggregates["council-council-small"]
    assert replayed == reopened.require_state("council-council-small")
    assert replayed["analysisHistory"][0]["claims"][0]["dissentCohorts"] == ["c01"]
    reopened.close()

def test_admitted_council_schedule_is_durable_idempotent_and_replayable(tmp_path):
    db = str(tmp_path / "council-schedule.db")
    store = EventStore(db)
    svc = GovernedRuntimeService(store)
    definition = make_council(CouncilTier.SMALL)
    svc.admit_council_plan(
        definition, CouncilLaunchAuthorization(council_digest(definition)), meta("admit-schedule")
    )

    capacity = {"p0": 1, "p1": 1}
    first = svc.schedule_admitted_council(
        definition.council_id, capacity, meta("schedule", idem="idem-schedule")
    )
    schedule = first["schedule"]
    assert schedule["logicalVesselCount"] == 6
    assert schedule["physicalSlotCount"] == 2
    assert schedule["waveCount"] == 1
    assert schedule["providerCapacity"] == [
        {"providerId": "p0", "maxConcurrentJobs": 1},
        {"providerId": "p1", "maxConcurrentJobs": 1},
    ]
    assert first["council"]["scheduleHistory"] == [schedule]

    retry = svc.schedule_admitted_council(
        definition.council_id, capacity, meta("schedule", idem="idem-schedule")
    )
    assert retry["status"] == "idempotent"
    assert retry["schedule"]["scheduleDigest"] == schedule["scheduleDigest"]
    store.close()

    reopened = EventStore(db)
    replayed = full_replay(reopened).aggregates["council-council-small"]
    assert replayed == reopened.require_state("council-council-small")
    assert replayed["scheduleHistory"][0]["scheduleDigest"] == schedule["scheduleDigest"]
    reopened.close()


def test_authoritative_council_schedule_requires_positive_capacity_and_system_authority(tmp_path):
    store = EventStore(str(tmp_path / "council-schedule-auth.db"))
    svc = GovernedRuntimeService(store)
    definition = make_council(CouncilTier.SMALL)
    svc.admit_council_plan(
        definition, CouncilLaunchAuthorization(council_digest(definition)), meta("admit-auth")
    )
    with pytest.raises(AuthorityViolation, match="CAPACITY_INVALID"):
        svc.schedule_admitted_council(
            definition.council_id, {"p0": 0, "p1": 1}, meta("bad-capacity")
        )
    human = commands.command(
        command_id="cmd-human-schedule",
        idempotency_key="idem-human-schedule",
        operation_fingerprint=commands.fingerprint("schedule_council", {"councilId": definition.council_id}),
        correlation_id="corr-council",
        actor_id="operator", actor_kind="human",
        issued_at="2026-09-10T18:00:00Z", replay_policy="never",
    )
    with pytest.raises(AuthorityViolation):
        svc.schedule_admitted_council(
            definition.council_id, {"p0": 1, "p1": 1}, human
        )
    store.close()


def test_checkpoint_tracks_council_stream_for_replay_equivalence(tmp_path):
    from capt_runtime.checkpoint import create_checkpoint
    from capt_runtime.replay import checkpoint_replay, replay_equivalent

    store = EventStore(str(tmp_path / "council-checkpoint.db"))
    svc = GovernedRuntimeService(store)
    definition = make_council(CouncilTier.SMALL)
    svc.admit_council_plan(
        definition, CouncilLaunchAuthorization(council_digest(definition)), meta("admit-cp")
    )
    manifest = create_checkpoint(
        store, "cp-council", "2026-09-10T18:05:00Z", "sha256:" + "d" * 64
    )
    assert manifest["councilVersions"] == [
        {"streamId": "council-council-small", "version": 1}
    ]
    assert replay_equivalent(full_replay(store), checkpoint_replay(store, manifest))
    store.close()
