"""Phase 3F — Autobiographical Memory tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from capt_solo.memory.autobiographical import (
    AutobiographicalMemory, EntryKind,
)
from capt_solo.memory.engine import MemoryEngine


@pytest.fixture
def abm():
    with tempfile.TemporaryDirectory() as d:
        e = AutobiographicalMemory(db_path=Path(d) / "abm.db")
        yield e
        e._eng.close()


def test_f_add_entry_identity_evidence_linked(abm):
    e = abm.add_entry(subject_identity="agent-1", kind=EntryKind.EVENT.value,
                      content="completed the build", confidence=0.9,
                      source_episodes=["ep-1"], source_evidence=["ev-1"])
    assert e.entry_id
    assert e.subject_identity == "agent-1"
    assert e.source_episodes == ["ep-1"]
    assert e.source_evidence == ["ev-1"]


def test_f_observation_vs_inference_distinct(abm):
    obs = abm.add_entry(subject_identity="a", kind=EntryKind.OBSERVATION.value,
                        content="I ran the tests", confidence=1.0)
    inf = abm.add_entry(subject_identity="a", kind=EntryKind.INFERENCE.value,
                        content="the build is stable", confidence=0.6,
                        uncertainty=0.3)
    assert obs.kind == "observation"
    assert inf.kind == "inference"
    assert inf.provenance == "inference"  # marked, not silently fact


def test_f_revision_retains_prior(abm):
    e1 = abm.add_entry(subject_identity="a", kind=EntryKind.EVENT.value,
                       content="v0.4.0 released")
    e2 = abm.revise(e1.entry_id, new_content="v0.4.1 released", reason="fix")
    # prior retained, linked
    prior = abm.get_entry(e1.entry_id)
    assert prior is not None
    assert prior.superseded_by == e2.entry_id
    assert e2.revision_of == e1.entry_id
    # history walks back to original
    hist = abm.revision_history(e2.entry_id)
    assert [h.entry_id for h in hist] == [e1.entry_id, e2.entry_id]
    assert hist[0].content == "v0.4.0 released"


def test_f_conflicting_interpretations_retained(abm):
    a = abm.add_entry(subject_identity="x", kind=EntryKind.THEME.value,
                      content="user prefers concise output")
    b = abm.add_entry(subject_identity="x", kind=EntryKind.THEME.value,
                      content="user prefers verbose explanations")
    abm.mark_conflict(a.entry_id, b.entry_id)
    ga = abm.get_entry(a.entry_id)
    gb = abm.get_entry(b.entry_id)
    assert b.entry_id in ga.conflicts_with
    assert a.entry_id in gb.conflicts_with
    # both still present (no deletion)
    assert abm.get_entry(a.entry_id) and abm.get_entry(b.entry_id)


def test_f_uncertainty_validated(abm):
    with pytest.raises(Exception):
        abm.add_entry(subject_identity="a", kind=EntryKind.EVENT.value,
                      content="x", uncertainty=5.0)


def test_f_list_by_subject_and_kind(abm):
    abm.add_entry(subject_identity="a", kind=EntryKind.EVENT.value, content="1")
    abm.add_entry(subject_identity="b", kind=EntryKind.EVENT.value, content="2")
    abm.add_entry(subject_identity="a", kind=EntryKind.THEME.value, content="3")
    assert len(abm.list_entries(subject_identity="a")) == 2
    assert len(abm.list_entries(subject_identity="a", kind=EntryKind.THEME.value)) == 1


def test_f_export_import_persistence(abm):
    e = abm.add_entry(subject_identity="a", kind=EntryKind.EVENT.value,
                      content="persist", source_evidence=["ev-9"])
    eid = e.entry_id
    path = Path(tempfile.mkdtemp()) / "exp.json"
    abm._eng.export_json(path)
    with tempfile.TemporaryDirectory() as d:
        e2 = MemoryEngine(db_path=Path(d) / "m.db")
        e2.import_json(path)
        abm2 = AutobiographicalMemory(engine=e2)
        got = abm2.get_entry(eid)
        assert got is not None
        assert got.content == "persist"
        assert got.source_evidence == ["ev-9"]
        e2.close()


def test_f_delete(abm):
    e = abm.add_entry(subject_identity="a", kind=EntryKind.EVENT.value, content="x")
    assert abm.delete_entry(e.entry_id) is True
    assert abm.get_entry(e.entry_id) is None
