import runpy
from pathlib import Path
import pytest

SWITCH = runpy.run_path(str(Path(__file__).resolve().parents[2] /
    "capt_ui/surfaces/desktop_swift/script/reversible_runtime_switch.py"))["switch_runtime"]
OLD = "1" * 40
NEW = "2" * 40

def _venv(path, head):
    (path/"bin").mkdir(parents=True)
    (path/"CAPT_SOURCE_HEAD").write_text(head)
    (path/"bin/capt").write_text("smoke")
    return path

def _gate(state):
    return dict(authenticatedRuntimeService=True,quiescent=True,
        checkpointVerified=True,runtimeStopped=True,stateRoot=str(state),
        checkpointHeadSequence=7,checkpointChainDigest="sha256:"+"0"*64)

def _post(state):
    return dict(authenticatedRuntimeService=True,sourceDigestsVerified=True,
        eventStoreContinuityVerified=True,processHealthy=True,
        sourceSha=NEW,stateRoot=str(state))

def test_reversible_runtime_switch_keeps_previous(tmp_path):
    active=_venv(tmp_path/"runtime-venv",OLD)
    candidate=_venv(tmp_path/"candidates"/"candidate",NEW)
    backup=SWITCH(active,candidate,tmp_path/"backups",NEW,
        lambda:_gate(tmp_path),lambda:_post(tmp_path),lambda:True)
    assert (active/"CAPT_SOURCE_HEAD").read_text()==NEW
    assert (backup/"CAPT_SOURCE_HEAD").read_text()==OLD
    assert not candidate.exists()

def test_postcheck_failure_rolls_back_without_deleting_candidate(tmp_path):
    active=_venv(tmp_path/"runtime-venv",OLD)
    candidate=_venv(tmp_path/"candidates"/"candidate",NEW)
    def bad_postcheck():
        raise RuntimeError("authenticated postcheck failed")
    with pytest.raises(RuntimeError,match="authenticated postcheck failed"):
        SWITCH(active,candidate,tmp_path/"backups",NEW,
            lambda:_gate(tmp_path),bad_postcheck,lambda:True)
    assert (active/"CAPT_SOURCE_HEAD").read_text()==OLD
    assert (candidate/"CAPT_SOURCE_HEAD").read_text()==NEW
    journals=list((tmp_path/"backups").glob("*/release.json"))
    assert len(journals)==1
    assert '"rolled_back"' in journals[0].read_text()

def test_missing_governed_gate_leaves_both_untouched(tmp_path):
    active=_venv(tmp_path/"runtime-venv",OLD)
    candidate=_venv(tmp_path/"candidates"/"candidate",NEW)
    with pytest.raises(Exception,match="GOVERNED_RELEASE_PREFLIGHT_REQUIRED"):
        SWITCH(active,candidate,tmp_path/"backups",NEW,
            lambda:{},lambda:_post(tmp_path),lambda:True)
    assert (active/"CAPT_SOURCE_HEAD").read_text()==OLD
    assert (candidate/"CAPT_SOURCE_HEAD").read_text()==NEW
