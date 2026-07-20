"""CAPT Solo v0.3 — Procedural Memory tests.

Covers: creation, versioning, candidate extraction, missing-field handling,
successful run, failed run, verification evidence, deprecation, retrieval.
"""

import pytest

from capt_solo.lifecycle.procedures import ProcedureStore, Procedure
from capt_solo.memory.engine import MemoryEngine


@pytest.fixture
def procs(mem_engine):
    return ProcedureStore(mem_engine)


def test_procedure_create(procs):
    pid = procs.create("run-tests", trigger="on ci", steps="1. pytest",
                       verification="exit 0", namespace="proj")
    assert pid
    p = procs.get(pid)
    assert p.name == "run-tests"
    assert p.version == 1
    assert p.lifecycle_state == "candidate"  # new procedures start as candidate


def test_procedure_versioning(procs):
    pid = procs.create("deploy", steps="v1")
    v1 = procs.get(pid).version
    procs.revise(pid, steps="v2", verification="smoke")
    p = procs.get(pid)
    assert p.version == v1 + 1
    assert p.steps == "v2"
    # prior version preserved
    hist1 = procs.get_version(pid, 1)
    hist2 = procs.get_version(pid, 2)
    assert hist1["steps"] == "v1"
    assert hist2["steps"] == "v2"


def test_procedure_revision_never_overwrites_prior(procs):
    pid = procs.create("x", steps="orig")
    procs.revise(pid, steps="new")
    # get_version returns the specific historical version
    v1 = procs.get_version(pid, 1)
    assert v1["steps"] == "orig"
    assert v1["version"] == 1


def test_procedure_record_run_success(procs):
    pid = procs.create("t", steps="s", verification="v")
    rid = procs.record_run(pid, outcome="success", verification_result="exit 0")
    assert rid
    p = procs.get(pid)
    assert p.success_count == 1
    assert p.failure_count == 0
    assert p.last_verified_at is not None


def test_procedure_record_run_failure(procs):
    pid = procs.create("t", steps="s")
    procs.record_run(pid, outcome="failure", failure_reason="boom")
    p = procs.get(pid)
    assert p.failure_count == 1
    assert p.success_count == 0


def test_procedure_not_promoted_by_repetition_alone(procs):
    pid = procs.create("t", steps="s")
    for _ in range(5):
        procs.record_run(pid, outcome="success", verification_result="ok")
    p = procs.get(pid)
    # repeated runs are evidence but do NOT auto-promote to durable/verified
    assert p.lifecycle_state == "candidate"
    assert p.success_count == 5


def test_procedure_deprecate(procs):
    pid = procs.create("t", steps="s")
    procs.deprecate(pid, reason="obsolete")
    assert procs.get(pid).lifecycle_state == "deprecated"


def test_procedure_build_execution_context(procs):
    pid = procs.create("t", trigger="tr", steps="s", verification="v",
                       preconditions="pc", expected_outputs="eo")
    ctx = procs.build_execution_context(pid)
    assert ctx["trigger"] == "tr"
    assert ctx["steps"] == "s"
    assert ctx["preconditions"] == "pc"
    assert "version" in ctx


def test_procedure_candidate_extraction_missing_fields(procs):
    # incomplete: only name + trigger, missing steps/verification
    pid = procs.create("partial", trigger="when X", steps="", verification="")
    p = procs.get(pid)
    assert p.lifecycle_state == "candidate"
    # missing fields flagged
    missing = procs.missing_fields(pid)
    assert "steps" in missing or "verification" in missing


def test_procedure_list_filter(procs):
    procs.create("a", namespace="proj")
    procs.create("b", namespace="other")
    lst = procs.list(namespace="proj")
    assert len(lst) == 1
    assert lst[0].name == "a"


def test_procedure_runs_query(procs, mem_engine):
    pid = procs.create("t", steps="s")
    procs.record_run(pid, outcome="success")
    procs.record_run(pid, outcome="failure", failure_reason="x")
    runs = [dict(r) for r in mem_engine._conn.execute(
        "SELECT * FROM procedure_runs WHERE procedure_id=?", (pid,)).fetchall()]
    assert len(runs) == 2
    assert sum(1 for r in runs if r["outcome"] == "failure") == 1
