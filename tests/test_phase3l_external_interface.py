"""Phase 3L — External interface hardening tests (API facade + CLI canon)."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from capt_solo.capt_facade import CAPT
from capt_solo.memory.engine import MemoryEngine


def test_l_api_facade_co_located_engine():
    with tempfile.TemporaryDirectory() as d:
        capt = CAPT(db_path=Path(d) / "capt.db")
        # all stores share one engine
        assert capt.episodic._eng is capt.knowledge._eng is capt.evidence._eng
        capt.close()


def test_l_api_end_to_end_flow():
    with tempfile.TemporaryDirectory() as d:
        capt = CAPT(db_path=Path(d) / "capt.db")
        # evidence -> knowledge (verified requires corroboration)
        e = capt.add_evidence(claim="stable", source_refs=["ci"],
                              status="corroborated")
        k = capt.add_knowledge(statement="system stable",
                               evidence_refs=[e.evidence_id])
        capt.knowledge.promote_status(k.knowledge_id, "verified")
        assert capt.knowledge.get_knowledge(k.knowledge_id).status == "verified"
        # episode
        ep = capt.create_episode(context="deploy", identity_link="agent-1")
        assert ep.episode_id
        # autobiographical
        ab = capt.add_autobiographical(subject_identity="agent-1",
                                       kind="event", content="did X")
        assert ab.entry_id
        assert capt.verify_runtime() is True
        capt.close()


def test_l_api_execution_boundary_enforced():
    with tempfile.TemporaryDirectory() as d:
        capt = CAPT(db_path=Path(d) / "capt.db")
        from capt_solo.execution.boundaries import Capabilities
        # no consent -> denied
        res = capt.run_execution(subject="s", scope="skill:run",
                                 capabilities=Capabilities(), func=lambda: "x")
        assert res.ok is False
        capt.close()


def test_l_cli_canon_self_check():
    r = subprocess.run([sys.executable, "-m", "capt_cli", "canon", "self-check"],
                       capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    assert r.returncode == 0
    assert "ok:" in r.stdout


def test_l_cli_canon_research_health():
    r = subprocess.run([sys.executable, "-m", "capt_cli", "canon", "research-health"],
                       capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    assert r.returncode == 0
    # empty registry -> empty health dict; CLI prints (empty) or blank line
    assert r.returncode == 0


def test_l_cli_canon_episodes_empty():
    r = subprocess.run([sys.executable, "-m", "capt_cli", "canon", "episodes"],
                       capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    assert r.returncode == 0
    assert "(empty)" in r.stdout or "[]" in r.stdout
