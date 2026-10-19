"""Process-death crash recovery tests for the directory switch; no live runtime."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "capt_ui/surfaces/desktop_swift/script/reversible_runtime_switch.py"
MODULE = runpy.run_path(str(PATH))
RECOVER = MODULE["recover_interrupted_switch"]
OLD = "1" * 40
NEW = "2" * 40

def venv(path, sha):
    (path / "bin").mkdir(parents=True)
    (path / "CAPT_SOURCE_HEAD").write_text(sha)
    (path / "bin/capt").write_text("fixture")
    return path

def gate(state):
    return dict(authenticatedRuntimeService=True, quiescent=True,
                checkpointVerified=True, runtimeStopped=True,
                stateRoot=str(state), checkpointHeadSequence=7,
                checkpointChainDigest="sha256:" + "a" * 64)

def post(state):
    return dict(authenticatedRuntimeService=True, sourceDigestsVerified=True,
                eventStoreContinuityVerified=True, processHealthy=True,
                sourceSha=OLD, stateRoot=str(state))

@pytest.mark.parametrize("crash_point", ["after_old_move", "after_candidate_move", "during_postcheck"])
def test_process_death_preserves_restorable_runtime(tmp_path, crash_point):
    active = venv(tmp_path / "runtime-venv", OLD)
    candidate = venv(tmp_path / "releases" / "candidate", NEW)
    backups = tmp_path / "backups"
    child = r"""
import os,runpy,sys
from pathlib import Path
lib=runpy.run_path(sys.argv[1])
active,candidate,backups=map(Path,sys.argv[2:5])
crash=sys.argv[5]
orig=os.replace
def replace(src,dst):
    out=orig(src,dst)
    if (crash=="after_old_move" and Path(src)==active) or (
        crash=="after_candidate_move" and Path(src)==candidate
    ):
        os._exit(79)
    return out
os.replace=replace
gate=lambda:dict(authenticatedRuntimeService=True,quiescent=True,
    checkpointVerified=True,runtimeStopped=True,stateRoot=str(active.parent),
    checkpointHeadSequence=7,checkpointChainDigest="sha256:"+"a"*64)
def post():
    if crash=="during_postcheck":os._exit(79)
    return {}
lib["switch_runtime"](
    active,candidate,backups,"2"*40,gate,post,lambda:True
)
"""
    child_result = subprocess.run([sys.executable, "-c", child, str(PATH),
                                   str(active), str(candidate), str(backups),
                                   crash_point], capture_output=True, text=True)
    assert child_result.returncode == 79, child_result.stderr
    assert len(list(backups.glob("*/release.json"))) == 1

    # Recovery needs a *fresh* governed gate. A failed gate changes nothing.
    with pytest.raises(Exception, match="RECOVERY_GOVERNED_PREFLIGHT_REQUIRED"):
        RECOVER(active, candidate, backups, lambda: {}, lambda: post(tmp_path))

    result = RECOVER(active, candidate, backups,
                     lambda: gate(tmp_path), lambda: post(tmp_path))
    assert result["status"] == "rolled_back"
    assert (active / "CAPT_SOURCE_HEAD").read_text() == OLD
    assert (candidate / "CAPT_SOURCE_HEAD").read_text() == NEW
    journal = json.loads(next(backups.glob("*/release.json")).read_text())
    assert journal["phase"] == "rolled_back"
    assert journal["recoveryAuthenticated"] is True
    assert RECOVER(active, candidate, backups,
                   lambda: gate(tmp_path), lambda: post(tmp_path)) == {
        "status": "nothing_pending"
    }


def test_failed_postcheck_does_not_claim_certified_rollback(tmp_path):
    active = venv(tmp_path / "runtime-venv", OLD)
    candidate = venv(tmp_path / "releases" / "candidate", NEW)
    backups = tmp_path / "backups"
    # Normal switch rollback already records the rollback, so create a
    # durable, interrupted journal fixture instead.
    journal_dir = backups / "pending"
    journal_dir.mkdir(parents=True)
    (journal_dir / "release.json").write_text(json.dumps({
        "phase": "prepared", "sourceSha": NEW, "previousSourceSha": OLD,
        "stateRoot": str(tmp_path), "checkpointHeadSequence": 7,
        "checkpointChainDigest": "sha256:" + "a" * 64
    }))
    with pytest.raises(Exception, match="RECOVERY_AUTHENTICATED_POSTCHECK_REQUIRED"):
        RECOVER(active, candidate, backups, lambda: gate(tmp_path),
                lambda: dict(authenticatedRuntimeService=False))
    journal = json.loads((journal_dir / "release.json").read_text())
    assert journal["phase"] == "restored_pending_authentication"
    assert (active / "CAPT_SOURCE_HEAD").read_text() == OLD
    assert RECOVER(active, candidate, backups, lambda: gate(tmp_path),
                   lambda: post(tmp_path))["status"] == "rolled_back"
