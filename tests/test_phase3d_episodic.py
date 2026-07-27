"""Phase 3D — Episodic Memory + SessionStore convergence + ECHO compatibility.

Tests the canonical EpisodicMemory store (Layer 3) backed by MemoryEngine,
reusing canonical fields. Verifies episode creation, event ordering, context,
evidence/provenance, identity linkage, confidence/uncertainty, retrieval,
replay/consolidation eligibility, retention, consent, and migration (via engine
export/import). Does NOT copy external ECHO source (clean implementation).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from capt_solo.memory.engine import MemoryEngine
from capt_solo.memory.episodic import (
    EpisodeEvent,
    EpisodicMemory,
    EPISODIC_NAMESPACE,
)


@pytest.fixture
def epi():
    with tempfile.TemporaryDirectory() as d:
        e = EpisodicMemory(db_path=Path(d) / "epi.db")
        yield e
        e._eng.close()


def test_d_create_episode_carries_canonical_fields(epi):
    ep = epi.create_episode(
        context="user fixed the build",
        identity_link="agent-1",
        evidence_refs=["ev-1"],
        confidence=0.9,
        uncertainty=0.05,
        retention="durable",
        consent="granted",
        events=[EpisodeEvent(event_id="e1", kind="observation",
                              content="build passed", timestamp=1.0)],
    )
    assert ep.episode_id
    assert ep.identity_link == "agent-1"
    assert ep.evidence_refs == ["ev-1"]
    assert ep.confidence == 0.9
    assert ep.uncertainty == 0.05
    assert ep.consent == "granted"
    assert len(ep.events) == 1
    assert ep.events[0].sequence == 0


def test_d_event_ordering_preserved(epi):
    ep = epi.create_episode(context="c", events=[
        EpisodeEvent(event_id="a", kind="observation", content="first", timestamp=1.0),
        EpisodeEvent(event_id="b", kind="inference", content="second", timestamp=2.0),
    ])
    ep2 = epi.append_event(ep.episode_id, EpisodeEvent(
        event_id="c", kind="outcome", content="third", timestamp=3.0))
    seqs = [e.sequence for e in ep2.events]
    assert seqs == [0, 1, 2]
    assert ep2.events[2].content == "third"


def test_d_uncertainty_validated(epi):
    with pytest.raises(Exception):
        epi.create_episode(context="c", uncertainty=2.0)


def test_d_replay_and_consolidation_eligibility(epi):
    ep = epi.create_episode(context="c")
    epi.mark_replay_eligible(ep.episode_id, True)
    epi.mark_consolidation_eligible(ep.episode_id, True)
    got = epi.get_episode(ep.episode_id)
    assert got.replay_eligible is True
    assert got.consolidation_eligible is True


def test_d_list_by_identity(epi):
    epi.create_episode(context="c1", identity_link="agent-1")
    epi.create_episode(context="c2", identity_link="agent-2")
    a1 = epi.list_episodes(identity_link="agent-1")
    assert len(a1) == 1
    assert a1[0].identity_link == "agent-1"


def test_d_retrieval_canonical(epi):
    ep = epi.create_episode(context="deployment succeeded",
                             confidence=0.8, evidence_refs=["ev-x"])
    rec = epi.to_canonical(ep.episode_id)
    assert rec is not None
    assert rec.confidence.value == 0.8
    assert rec.source_evidence.evidence_refs == ["ev-x"]
    assert rec.identity.identity_link is None  # episode had no identity_link


def test_d_episode_persists_via_export_import(epi):
    ep = epi.create_episode(context="persist me",
                             events=[EpisodeEvent(event_id="e1", kind="observation",
                                                  content="x", timestamp=1.0)])
    epid = ep.episode_id
    path = Path(tempfile.mkdtemp()) / "exp.json"
    epi._eng.export_json(path)
    with tempfile.TemporaryDirectory() as d3:
        e3 = MemoryEngine(db_path=Path(d3) / "m3.db")
        e3.import_json(path)
        epi3 = EpisodicMemory(engine=e3)
        got = epi3.get_episode(epid)
        assert got is not None
        assert got.context == "persist me"
        assert len(got.events) == 1
        e3.close()


def test_d_delete_episode(epi):
    ep = epi.create_episode(context="temp")
    assert epi.delete_episode(ep.episode_id) is True
    assert epi.get_episode(ep.episode_id) is None


def test_d_sessionstore_compatibility_namespace(epi):
    # Episodes live in the episodic namespace; SessionStore remains separate.
    ep = epi.create_episode(context="c")
    listed = epi._eng.list(namespace=EPISODIC_NAMESPACE, limit=10)
    assert any(m.memory_id == ep.episode_id for m in listed)
