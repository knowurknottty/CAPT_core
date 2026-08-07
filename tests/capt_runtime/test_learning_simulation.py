"""Learning Plane (Gate 10) and Simulation Plane M0 (Gate 11) tests."""

import pytest

from capt_runtime import learning as L
from capt_runtime import simulation as S
from capt_runtime.errors import AuthorityViolation


def _traj(verified, cg):
    return {
        "schemaVersion": "1.0.0",
        "trajectoryId": "tr-1",
        "missionId": "m-1",
        "verified": verified,
        "claimGuardPassed": cg,
    }


def test_trajectory_requires_verification():
    with pytest.raises(AuthorityViolation):
        L.accept_trajectory(_traj(verified=False, cg=True))


def test_trajectory_requires_claimguard():
    with pytest.raises(AuthorityViolation):
        L.accept_trajectory(_traj(verified=True, cg=False))


def test_trajectory_accepted_when_verified_and_cg():
    assert L.accept_trajectory(_traj(verified=True, cg=True))["trajectoryId"] == "tr-1"


def test_reward_requires_admissible_trajectory():
    with pytest.raises(AuthorityViolation):
        L.compile_reward(_traj(verified=False, cg=True), 1.0)


def test_reward_compiled():
    sig = L.compile_reward(_traj(verified=True, cg=True), 0.5)
    assert sig["value"] == 0.5


def test_strategy_registry():
    s = L.register_strategy("GRPO", "st-grpo", enabled=False)
    assert s["kind"] == "GRPO"


def test_candidate_registry():
    c = L.register_candidate({
        "schemaVersion": "1.0.0", "candidateId": "mc-1",
        "sourceTrajectoryId": "tr-1", "artifactDigest": "sha256:" + "a" * 64})
    assert c["candidateId"] == "mc-1"


def test_promotion_human_governed_only():
    with pytest.raises(AuthorityViolation):
        L.decide_promotion({}, "auto_promote", "ai", "2026-08-03T00:00:00Z")
    d = L.decide_promotion({}, "promote", "human-1", "2026-08-03T00:00:00Z")
    assert d["decision"] == "promote"


def test_no_live_training_guard():
    assert L.assert_no_live_training() is None


def test_simulation_environment_isolated():
    env = S.create_environment("sim-1", "sha256:" + "e" * 64, "sha256:" + "d" * 64)
    assert env["productionAuthority"] is False and env["isSimulation"] is True


def test_simulation_rejects_production_authority():
    bad = {"schemaVersion": "1.0.0", "simId": "sim-1",
           "environmentDigest": "sha256:" + "e" * 64, "datasetDigest": "sha256:" + "d" * 64,
           "isSimulation": True, "productionAuthority": True}
    with pytest.raises(AuthorityViolation):
        S.assert_no_production_authority(bad)


def test_simulation_marker():
    m = S.mark_simulation("mk-1", "sim-1", "result")
    assert m["kind"] == "result"


def test_environment_digest_reproducible():
    snap = {"seed": 1, "config": {"a": 1}}
    assert S.environment_digest(snap) == S.environment_digest(snap)
    assert S.environment_digest(snap) != S.environment_digest({"seed": 2})


def test_simulation_result_cannot_become_production():
    payload = {"fromSimulation": True, "isSimulation": True, "productionAuthority": False}
    with pytest.raises(AuthorityViolation):
        S.reject_simulation_as_production(payload)  # missing marker
    payload["simulationMarker"] = S.mark_simulation("mk-2", "sim-1", "result")
    S.reject_simulation_as_production(payload)  # now accepted (marked)
