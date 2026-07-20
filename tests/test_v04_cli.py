"""CAPT Solo v0.4 — CLI foundry integration tests.

Exercises every `capt foundry ...` subcommand through the actual CLI entry
point (capt_cli.main) using public APIs only. No direct SQL in tests.
Seeding is done in-process against the same CAPT_SOLO_HOME the CLI uses.
"""

import json
import os
import subprocess
import sys

import pytest

from capt_solo.memory.engine import MemoryEngine
from capt_solo.lifecycle.procedures import ProcedureStore
from capt_solo.foundry import (
    SkillFoundry, ProofEngine, CapabilityRegistry, ClaimGuard,
    KnowledgeBubbleRuntime, ValidationHarness, SkillCurator, Governance,
)
from capt_solo.ctp.journal import CTPRuntime


@pytest.fixture
def cli_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    return tmp_path


def _run(home, *args):
    env = dict(os.environ)
    env["CAPT_SOLO_HOME"] = str(home)
    proc = subprocess.run(
        [sys.executable, "capt_cli.py", "--json", *args],
        capture_output=True, text=True, env=env, cwd=os.getcwd())
    return proc


def _seed_skill(home):
    """Create a verified procedure + published skill via public APIs (in-process)."""
    eng = MemoryEngine()
    ps = ProcedureStore(eng)
    pe = ProofEngine(eng._conn)
    sf = SkillFoundry(eng._conn, pe, ps)
    pid = ps.create("op", steps="echo run", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(
        cid, name="op-skill", permissions=["filesystem:read"],
        verification_requirements=[{"type": "static_analysis", "min_count": 1}])
    sf.validate(sid, ValidationHarness(pe))
    sf.submit_for_review(sid)
    sf.approve(sid, reviewer="captain")
    sf.publish(sid)
    eng.close()
    return sid


def _seed_cap(home):
    eng = MemoryEngine()
    pe = ProofEngine(eng._conn)
    reg = CapabilityRegistry(eng._conn, pe)
    reg.register("cap_x", "does x", "capt_solo")
    pe.record("test_pass", "pytest", "h1", "t", scope="cap_x")
    pe.record("static_analysis", "flake8", "h2", "t", scope="cap_x")
    eng.close()
    return "cap_x"


def _seed_bubble(home):
    eng = MemoryEngine()
    kb = KnowledgeBubbleRuntime(eng._conn)
    b = KnowledgeBubbleRuntime.build_bubble(
        "b", skills=[{"name": "y", "permissions": ["filesystem:read"]}],
        proof=[{"type": "static_analysis", "hash": "h"}],
        trust_metadata={"source": "captain"})
    bid = kb.import_bubble(b)
    eng.close()
    return bid


def test_cli_list_skills(cli_home):
    sid = _seed_skill(cli_home)
    p = _run(cli_home, "foundry", "list-skills")
    assert p.returncode == 0
    data = json.loads(p.stdout)
    assert any(s["skill_id"] == sid for s in data)


def test_cli_skill_inspect(cli_home):
    sid = _seed_skill(cli_home)
    p = _run(cli_home, "foundry", "skill", sid)
    assert p.returncode == 0
    assert json.loads(p.stdout)["lifecycle_state"] == "published"


def test_cli_candidates_empty(cli_home):
    p = _run(cli_home, "foundry", "candidates")
    assert p.returncode == 0
    assert json.loads(p.stdout) == []


def test_cli_validate_review_approve_publish(cli_home):
    eng = MemoryEngine()
    ps = ProcedureStore(eng)
    pe = ProofEngine(eng._conn)
    sf = SkillFoundry(eng._conn, pe, ps)
    pid = ps.create("op", steps="echo run", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(
        cid, name="op-skill", permissions=["filesystem:read"],
        verification_requirements=[{"type": "static_analysis", "min_count": 1}])
    eng.close()
    assert json.loads(_run(cli_home, "foundry", "validate", sid).stdout)["passed"] is True
    assert json.loads(_run(cli_home, "foundry", "review", sid).stdout)["lifecycle"] == "reviewing"
    assert json.loads(_run(cli_home, "foundry", "approve", sid).stdout)["lifecycle"] == "approved"
    assert json.loads(_run(cli_home, "foundry", "publish", sid).stdout)["lifecycle"] == "published"


def test_cli_capabilities(cli_home):
    _seed_cap(cli_home)
    p = _run(cli_home, "foundry", "list-caps")
    assert p.returncode == 0
    assert isinstance(json.loads(p.stdout), list)


def test_cli_cap_verify_prove_govern(cli_home):
    cap = _seed_cap(cli_home)
    v = json.loads(_run(cli_home, "foundry", "verify-cap", cap).stdout)
    assert v["lifecycle"] == "validated"
    assert json.loads(_run(cli_home, "foundry", "prove-cap", cap).stdout)["lifecycle"] == "proven"
    g = json.loads(_run(cli_home, "foundry", "govern-cap", cap).stdout)
    assert g["lifecycle"] == "verified"


def test_cli_bubble_lifecycle(cli_home):
    bid = _seed_bubble(cli_home)
    assert json.loads(_run(cli_home, "foundry", "bubble-validate", bid).stdout)["passed"] is True
    assert json.loads(_run(cli_home, "foundry", "bubble-approve", bid).stdout)["ok"] is True
    res = json.loads(_run(cli_home, "foundry", "bubble-install", bid).stdout)
    assert res["bubble_id"] == bid


def test_cli_curate_and_audit(cli_home):
    _seed_skill(cli_home)
    c = json.loads(_run(cli_home, "foundry", "curate").stdout)
    assert "total" in c
    a = json.loads(_run(cli_home, "foundry", "audit").stdout)
    assert isinstance(a, list)


def test_cli_unknown_action(cli_home):
    p = _run(cli_home, "foundry", "nonexistent")
    assert p.returncode != 0
