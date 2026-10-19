from pathlib import Path

from capt_runtime.release_readiness import assess_release_snapshot

BASE = Path("/tmp/capt-fixture")
IDENTITY = {"integrity": "ok", "ledgerPath": str(BASE / "runtime.db"),
            "headSequence": 17, "ledgerChainDigest": "sha256:" + "f" * 64}
CHECKPOINT = {"integrityVerified": True, "globalSequence": 17,
              "recoveryState": "clean", "canDispatchConsequential": True,
              "openReservations": [], "checkpointId": "cp-test"}
OLD = "1" * 40
NEW = "2" * 40


def assess(identity=None, checkpoint=None, reservations=None,
           runs=None, tools=None):
    return assess_release_snapshot(
        IDENTITY if identity is None else identity,
        CHECKPOINT if checkpoint is None else checkpoint,
        [] if reservations is None else reservations,
        [] if runs is None else runs,
        [] if tools is None else tools,
        state_root=BASE, installed_source=OLD, candidate_source=NEW,
    )


def test_clean_authenticated_witness_can_enter_quiescence():
    v = assess()
    assert v["eligibleForQuiescence"] is True
    assert v["blockers"] == []


def test_indeterminate_historical_reservation_blocks_activation():
    cp = {**CHECKPOINT, "recoveryState": "awaiting_reconciliation",
          "canDispatchConsequential": False, "openReservations": ["res-unknown"]}
    v = assess(checkpoint=cp, reservations=["res-unknown"])
    assert not v["eligibleForQuiescence"]
    assert "UNRESOLVED_RESERVATIONS" in v["blockers"]
    assert "CHECKPOINT_RECOVERY_NOT_CLEAN" in v["blockers"]


def test_mismatched_projection_or_unverified_checkpoint_fails_closed():
    cp = {**CHECKPOINT, "integrityVerified": False}
    v = assess(checkpoint=cp, reservations=["res-historical"])
    assert not v["eligibleForQuiescence"]
    assert "RESERVATION_PROJECTION_MISMATCH" in v["blockers"]
    assert "CHECKPOINT_INTEGRITY_UNVERIFIED" in v["blockers"]


def test_active_driver_run_and_tool_execution_block_release():
    v = assess(runs=["driverrun-1"], tools=["tool-1"])
    assert not v["eligibleForQuiescence"]
    assert "ACTIVE_EXECUTION" in v["blockers"]
