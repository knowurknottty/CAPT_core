"""CAPT Universal Workspace — schema, consistency, and CLI integration tests.

Positive + negative. Proves invalid workspace state is rejected (per Prompt #1 §13).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "capt_cli.py"
WS = pytest.importorskip("capt_solo.workspace")


# ---------------------------------------------------------------------------
# Live workspace (the one we just built) must be internally consistent
# ---------------------------------------------------------------------------

def test_live_workspace_validates():
    checks = WS.validate_workspace()
    fails = [c for c in checks if c.status == "fail"]
    assert not fails, f"live workspace has failing checks: {[c.summary for c in fails]}"


def test_live_task_records_valid():
    errs = WS._validate_task_records()
    assert not errs, f"task record errors: {errs}"


def test_live_task_dependencies_acyclic():
    errs = WS._validate_task_dependencies()
    assert not errs, f"dependency errors: {errs}"


def test_live_checkpoint_consistent_with_head():
    ck = WS._checkpoint_staleness()
    assert not ck["error"], ck["error"]
    assert ck["commit"] == ck["head"], "CHECKPOINT commit must equal HEAD in a clean session"


# ---------------------------------------------------------------------------
# Schema validation (valid + invalid fixtures)
# ---------------------------------------------------------------------------

def _valid_task():
    return {
        "task_id": "TASK-900", "title": "fixture", "subsystem": "X", "phase": "S1",
        "priority": 1, "status": "ready", "dependencies": [], "invariants": ["I-01"],
        "required_evidence": ["x"], "required_tests": ["t"], "owner_gate": "none",
        "assigned_agent": None, "source": "test", "created_at": "2026-07-26T00:00:00Z",
        "updated_at": "2026-07-26T00:00:00Z", "completion_commit": None,
        "required_capabilities": ["filesystem_read"],
    }


def test_valid_task_passes_schema():
    schema = WS.load_schema("task")
    errs = WS._validate_against_schema(_valid_task(), schema)
    assert not errs, errs


def test_invalid_task_missing_required_field():
    schema = WS.load_schema("task")
    rec = _valid_task()
    del rec["title"]
    errs = WS._validate_against_schema(rec, schema)
    assert any("title" in e for e in errs), errs


def test_invalid_task_bad_status_enum():
    schema = WS.load_schema("task")
    rec = _valid_task()
    rec["status"] = "in_progress"  # not in enum
    errs = WS._validate_against_schema(rec, schema)
    assert any("status" in e for e in errs), errs


def test_invalid_task_bad_owner_gate():
    schema = WS.load_schema("task")
    rec = _valid_task()
    rec["owner_gate"] = "self_approved"  # not in enum
    errs = WS._validate_against_schema(rec, schema)
    assert any("owner_gate" in e for e in errs), errs


def test_invalid_task_bad_completion_commit():
    schema = WS.load_schema("task")
    rec = _valid_task()
    rec["completion_commit"] = "not-a-sha"
    errs = WS._validate_against_schema(rec, schema)
    assert any("completion_commit" in e for e in errs), errs


def test_invalid_task_bad_invariants():
    schema = WS.load_schema("task")
    rec = _valid_task()
    rec["invariants"] = ["I-99"]
    errs = WS._validate_against_schema(rec, schema)
    assert any("invariants" in e for e in errs), errs


def test_invalid_task_additional_property():
    schema = WS.load_schema("task")
    rec = _valid_task()
    rec["evil_field"] = "should not be allowed"
    errs = WS._validate_against_schema(rec, schema)
    assert any("evil_field" in e for e in errs), errs


def test_valid_checkpoint_passes_schema():
    schema = WS.load_schema("checkpoint")
    rec = {
        "checkpoint_id": "CKPT-1", "branch": "main", "commit": "abc1234",
        "completed": "x", "in_progress": "y", "active_files": ["a"],
        "tests_status": "463 passed", "root_cause": "n/a", "next_command": "make",
        "next_commit_boundary": "z", "owner_gate": "none",
        "generated_at": "2026-07-26T00:00:00Z",
    }
    errs = WS._validate_against_schema(rec, schema)
    assert not errs, errs


def test_invalid_checkpoint_bad_commit():
    schema = WS.load_schema("checkpoint")
    rec = {
        "checkpoint_id": "CKPT-1", "branch": "main", "commit": "zzz",
        "completed": "x", "in_progress": "y", "active_files": ["a"],
        "tests_status": "463 passed", "root_cause": "n/a", "next_command": "make",
        "next_commit_boundary": "z", "owner_gate": "none",
        "generated_at": "2026-07-26T00:00:00Z",
    }
    errs = WS._validate_against_schema(rec, schema)
    assert any("commit" in e for e in errs), errs


# ---------------------------------------------------------------------------
# Missing-file / dirty detection
# ---------------------------------------------------------------------------

def test_missing_required_file_detected(tmp_path, monkeypatch):
    # Point REPO_ROOT at a bare temp dir missing AGENTS.md
    monkeypatch.setattr(WS, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(WS, "ARCH_DIR", tmp_path / "architecture")
    checks = WS.validate_workspace()
    fails = [c for c in checks if c.cid == "workspace.files"]
    assert fails and fails[0].status == "fail"


def test_dirty_worktree_detected(monkeypatch):
    # Simulate git status returning a modified file
    def fake_git(args):
        if args == ["status", "--porcelain"]:
            return 0, " M capt_solo/workspace.py"
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return 0, "integration/full-public-architecture"
        if args == ["rev-parse", "HEAD"]:
            return 0, "dc806b4" * 5
        if args[:2] == ["merge-base", "--is-ancestor"]:
            return 0, ""
        return 0, ""
    monkeypatch.setattr(WS, "_git", fake_git)
    st = WS.workspace_status()
    assert st["clean"] is False


# ---------------------------------------------------------------------------
# Task dependency graph
# ---------------------------------------------------------------------------

def test_circular_dependency_detected(tmp_path):
    d = tmp_path / "tasks"
    d.mkdir()
    (d / "TASK-001.json").write_text(json.dumps({
        "task_id": "TASK-001", "title": "a", "subsystem": "x", "phase": "S1",
        "priority": 1, "status": "ready", "dependencies": ["TASK-002"],
        "invariants": ["I-01"], "required_evidence": [], "required_tests": [],
        "owner_gate": "none", "assigned_agent": None, "source": "t",
        "created_at": "2026-07-26T00:00:00Z", "updated_at": "2026-07-26T00:00:00Z",
        "completion_commit": None, "required_capabilities": []}))
    (d / "TASK-002.json").write_text(json.dumps({
        "task_id": "TASK-002", "title": "b", "subsystem": "x", "phase": "S1",
        "priority": 1, "status": "ready", "dependencies": ["TASK-001"],
        "invariants": ["I-01"], "required_evidence": [], "required_tests": [],
        "owner_gate": "none", "assigned_agent": None, "source": "t",
        "created_at": "2026-07-26T00:00:00Z", "updated_at": "2026-07-26T00:00:00Z",
        "completion_commit": None, "required_capabilities": []}))
    monkeypatch_dir = tmp_path
    # validate_task_dependencies reads REPO_ROOT/tasks; monkeypatch REPO_ROOT
    import capt_solo.workspace as wsm
    orig = wsm.REPO_ROOT
    wsm.REPO_ROOT = tmp_path
    try:
        errs = wsm._validate_task_dependencies()
    finally:
        wsm.REPO_ROOT = orig
    assert any("cycle" in e for e in errs), errs


def test_dangling_dependency_detected(tmp_path):
    import capt_solo.workspace as wsm
    d = tmp_path / "tasks"
    d.mkdir()
    (d / "TASK-001.json").write_text(json.dumps({
        "task_id": "TASK-001", "title": "a", "subsystem": "x", "phase": "S1",
        "priority": 1, "status": "ready", "dependencies": ["TASK-999"],
        "invariants": ["I-01"], "required_evidence": [], "required_tests": [],
        "owner_gate": "none", "assigned_agent": None, "source": "t",
        "created_at": "2026-07-26T00:00:00Z", "updated_at": "2026-07-26T00:00:00Z",
        "completion_commit": None, "required_capabilities": []}))
    orig = wsm.REPO_ROOT
    wsm.REPO_ROOT = tmp_path
    try:
        errs = wsm._validate_task_dependencies()
    finally:
        wsm.REPO_ROOT = orig
    assert any("dangling" in e for e in errs), errs


# ---------------------------------------------------------------------------
# Capability mismatch (honest handling)
# ---------------------------------------------------------------------------

def test_next_task_respects_capabilities(tmp_path):
    # TASK-204 requires shell_execution; if an agent lacks it, next_task must skip it
    # when it's the only ready task. Build a minimal scenario in tmp_path.
    import capt_solo.workspace as wsm
    d = tmp_path / "tasks"
    d.mkdir()
    rec = {
        "task_id": "TASK-001", "title": "needs shell", "subsystem": "x", "phase": "S1",
        "priority": 1, "status": "ready", "dependencies": [], "invariants": ["I-01"],
        "required_evidence": [], "required_tests": [], "owner_gate": "none",
        "assigned_agent": None, "source": "t", "created_at": "2026-07-26T00:00:00Z",
        "updated_at": "2026-07-26T00:00:00Z", "completion_commit": None,
        "required_capabilities": ["shell_execution"],
    }
    (d / "TASK-001.json").write_text(json.dumps(rec))
    orig = wsm.REPO_ROOT
    wsm.REPO_ROOT = tmp_path
    try:
        # agent without shell_execution
        t = wsm.next_task({"filesystem_read": True, "shell_execution": False})
        assert t is None, "should not return a task requiring unmet capabilities"
        # agent with shell_execution
        t2 = wsm.next_task({"filesystem_read": True, "shell_execution": True})
        assert t2 is not None and t2["task_id"] == "TASK-001"
    finally:
        wsm.REPO_ROOT = orig


# ---------------------------------------------------------------------------
# Stale checkpoint detection
# ---------------------------------------------------------------------------

def test_stale_checkpoint_detected(tmp_path, monkeypatch):
    import capt_solo.workspace as wsm
    (tmp_path / "CHECKPOINT.md").write_text(
        "# CHECKPOINT\n- **commit**: `deadbeef`\n")
    monkeypatch.setattr(wsm, "REPO_ROOT", tmp_path)
    # git merge-base --is-ancestor deadbeef HEAD -> non-zero (not ancestor)
    def fake_git(args):
        if args[:2] == ["merge-base", "--is-ancestor"]:
            return 1, ""  # not ancestor => stale
        if args == ["rev-parse", "HEAD"]:
            return 0, "abc1234"
        return 0, ""
    monkeypatch.setattr(wsm, "_git", fake_git)
    ck = wsm._checkpoint_staleness()
    assert ck["stale"] is True


# ---------------------------------------------------------------------------
# Bootstrap ordering
# ---------------------------------------------------------------------------

def test_bootstrap_reading_list_ordered():
    rl = WS.bootstrap_reading_list()
    assert rl[0].startswith("AGENTS.md")
    assert "CURRENT_STATE.md" in rl[1]
    assert "CHECKPOINT.md" in rl[2]


# ---------------------------------------------------------------------------
# CLI integration (real subprocess — proves the commands actually work)
# ---------------------------------------------------------------------------

def _run(args):
    return subprocess.run([sys.executable, str(CLI)] + args, cwd=str(REPO),
                          capture_output=True, text=True)


def test_cli_workspace_validate_exit_zero():
    r = _run(["--json", "workspace", "validate"])
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["ok"] is True


def test_cli_workspace_status_exit_zero():
    r = _run(["workspace", "status"])
    assert r.returncode == 0
    assert "branch:" in r.stdout


def test_cli_workspace_bootstrap_exit_zero():
    r = _run(["workspace", "bootstrap"])
    assert r.returncode == 0
    assert "AGENTS.md" in r.stdout


def test_cli_workspace_next_returns_task():
    r = _run(["--json", "workspace", "next"])
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert "task_id" in d


def test_cli_workspace_capabilities_exit_zero():
    r = _run(["workspace", "capabilities"])
    assert r.returncode == 0
    assert "network_access" in r.stdout


def test_cli_workspace_tasks_exit_zero():
    r = _run(["--json", "workspace", "tasks"])
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert isinstance(d, list) and len(d) >= 1
