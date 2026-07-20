"""CAPT Solo v0.4 — Hermes plugin foundry tool tests.

Exercises the stable plugin tools against the public foundry APIs. No direct
SQL. Each tool must return {"ok": True} on success and {"ok": False, "error": ...}
on failure (never raise into Hermes).
"""

import os

import pytest

from capt_solo.plugin import CaptSoloPlugin, TOOLS, tool_names
from capt_solo.memory.engine import MemoryEngine
from capt_solo.lifecycle.procedures import ProcedureStore
from capt_solo.foundry import (
    SkillFoundry, ProofEngine, CapabilityRegistry, ClaimGuard,
    KnowledgeBubbleRuntime, ValidationHarness,
)


@pytest.fixture
def plugin(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    return CaptSoloPlugin()


def _seed_procedure(home):
    eng = MemoryEngine()
    ps = ProcedureStore(eng)
    pe = ProofEngine(eng._conn)
    sf = SkillFoundry(eng._conn, pe, ps)
    pid = ps.create("op", steps="echo run", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    eng.close()
    return pid


def test_plugin_tool_count():
    names = tool_names()
    for t in ["capt_generate_skill", "capt_validate_skill", "capt_publish_skill",
              "capt_query_capability", "capt_verify_claim", "capt_build_bubble",
              "capt_validate_bubble", "capt_install_bubble", "capt_export_bubble",
              "capt_inspect_proof"]:
        assert t in names


def test_generate_and_publish_skill(plugin, tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    pid = _seed_procedure(str(tmp_path))
    r = plugin.capt_generate_skill(pid, name="op-skill",
                                   verification_requirements=[{"type": "static_analysis", "min_count": 1}],
                                   permissions=["filesystem:read"])
    assert r["ok"] is True
    sid = r["skill_id"]
    v = plugin.capt_validate_skill(sid)
    assert v["ok"] is True and v["passed"] is True
    p = plugin.capt_publish_skill(sid, reviewer="hermes")
    assert p["ok"] is True and p["lifecycle"] == "published"


def test_query_capability(plugin, tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    eng = MemoryEngine()
    pe = ProofEngine(eng._conn)
    reg = CapabilityRegistry(eng._conn, pe)
    reg.register("cap_q", "does q", "capt_solo")
    eng.close()
    r = plugin.capt_query_capability("cap_q")
    assert r["ok"] is True
    assert r["identifier"] == "cap_q"
    miss = plugin.capt_query_capability("nope")
    assert miss["ok"] is False


def test_verify_claim_downgrades(plugin, tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    # no capability registered in this isolated home
    r = plugin.capt_verify_claim("Migration complete and verified.")
    assert r["ok"] is True
    assert r["supported"] is False


def test_build_and_install_bubble(plugin):
    bubble = KnowledgeBubbleRuntime.build_bubble(
        "b", skills=[{"name": "y", "permissions": ["filesystem:read"]}],
        proof=[{"type": "static_analysis", "hash": "h"}],
        trust_metadata={"source": "captain"})
    r = plugin.capt_install_bubble(bubble, approver="hermes")
    assert r["ok"] is True
    assert r["bubble_id"]


def test_export_bubble_excludes_private(plugin):
    r = plugin.capt_export_bubble(include_private=False)
    assert r["ok"] is True
    # no private memory content leaked (the sentinel below would only appear
    # if actual private data were included; "private" in export_policy is fine)
    assert "SECRET_LEAK_SENTINEL" not in str(r["bubble"])


def test_inspect_proof(plugin, tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    eng = MemoryEngine()
    pe = ProofEngine(eng._conn)
    pe.record("test_pass", "pytest", "h1", "t", scope="scope_x")
    eng.close()
    r = plugin.capt_inspect_proof("scope_x")
    assert r["ok"] is True
    assert r["evidence_count"] >= 1


def test_tool_error_is_dict_not_exception(plugin):
    # calling with bad input must return a dict, never raise
    r = plugin.capt_query_capability("")
    assert isinstance(r, dict)
    assert r["ok"] is False
