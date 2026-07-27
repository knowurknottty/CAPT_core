"""CLI integration tests for evidence / mission / selfmod commands (Phase 11)."""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(*args):
    # --json is a global flag; place it before the subcommand group.
    return subprocess.run(["python3", "capt_cli.py", "--json", *args], cwd=REPO,
                         capture_output=True, text=True, timeout=60)


def test_evidence_reuse_decision_equivalent():
    r = _run("evidence", "reuse-decision", "claim-x", "--vsi", "equivalent")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["state_identity"] == "equivalent"
    assert "action" in d
    assert d["reason"]


def test_evidence_status_empty():
    r = _run("evidence", "status")
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d["total"] == 0


def test_mission_checkpoint_and_resume():
    r = _run("mission", "checkpoint", "--mission-id", "cli-test", "--objective",
             "verify evidence engine", "--phase", "3", "--next", "write docs",
             "--head", "a0124c1")
    assert r.returncode == 0, r.stderr
    r2 = _run("mission", "resume", "cli-test")
    assert r2.returncode == 0, r2.stderr
    d = json.loads(r2.stdout)
    assert d["mission_id"] == "cli-test"
    assert "next_action" in d


def test_selfmod_propose_and_diff():
    r = _run("selfmod", "propose", "--mission-id", "cli-sm", "--change",
             "improve skill wording", "--scope", "project_local", "--diff",
             "old->new", "--rollback", "git revert")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    rid = d["record_id"]
    assert d["status"] in ("proposed", "approved")
    r2 = _run("selfmod", "diff", rid, "--mission-id", "cli-sm")
    assert r2.returncode == 0
    d2 = json.loads(r2.stdout)
    assert d2["diff"] == "old->new"


def test_selfmod_global_requires_approval_path():
    r = _run("selfmod", "propose", "--mission-id", "cli-sm2", "--change",
             "change global policy", "--scope", "global_policy", "--diff",
             "x->y", "--rollback", "rb")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["status"] == "quarantined"
