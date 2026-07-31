"""CAPT Solo v0.5 — canonical composition root tests.

Outcome B: CAPTRuntime.load() is the single production construction site.
Covers: single-owner identity, mandatory MemoryUseGate (deny + allow),
governed execute (CTP commit/abort, KHSB events, checkpoint, ClaimGuard
evaluation, evidence+hash), idempotent KHSB delivery, resume by session.
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from capt_solo.api import (
    CAPTRuntime,
    GateDeniedError,
    RuntimeConfiguration,
)
from capt_solo.ctp.journal import CTPRuntime
from capt_solo.foundry import ProofRequirement
from capt_solo.contextpack import RecordRef


def _digest(embedded) -> str:
    return hashlib.sha256(
        json.dumps(embedded, sort_keys=True, default=str).encode()
    ).hexdigest()


@pytest.fixture
def rt(tmp_path):
    cfg = RuntimeConfiguration(
        db_path=tmp_path / "memory.db",
        journal_dir=tmp_path / "ctp",
        evidence_dir=tmp_path / "evidence",
        event_log_path=tmp_path / "khsb" / "events.jsonl",
    )
    r = CAPTRuntime.load(cfg)
    yield r
    r.close()


def _event_log_text(rt) -> str:
    if not rt.events.path.exists():
        return ""
    return rt.events.path.read_text(encoding="utf-8")


def _fact_evidence(value: str):
    return [RecordRef("evidence:fact", _digest({"fact": value}), "test", {"fact": value})]


# --- single owner / shared components --------------------------------------

def test_single_owner_shared_components(rt):
    assert rt.lifecycle._eng is rt.engine
    assert rt.lifecycle._ctp is rt.ctp
    assert rt.lifecycle._bus is rt.bus
    assert rt.registry._conn is rt.engine._conn
    assert rt.proof._conn is rt.engine._conn
    assert rt.claimguard._reg is rt.registry
    assert rt.runtime_id


def test_each_runtime_has_unique_identity(rt, tmp_path):
    rt2 = CAPTRuntime.load(rt.config)
    try:
        assert rt2.runtime_id != rt.runtime_id
    finally:
        rt2.close()


# --- mandatory MemoryUseGate ------------------------------------------------

def test_gate_denies_when_contextpack_blocks(rt):
    # evidence fact "9.9.9" is NOT rendered -> FIDELITY_BLOCK -> mandatory deny
    with pytest.raises(GateDeniedError):
        rt.execute(
            lambda r: {"ran": True},
            mission_id="m-deny",
            objective="blocked op",
            records={"selected": "should be recorded"},
            evidence=_fact_evidence("9.9.9"),
            rendered_context="MISSION m-deny objective=blocked op",
        )
    log = _event_log_text(rt)
    assert "mission.operation.completed" not in log
    assert "mission.operation.started" not in log  # refused before transaction


def test_gate_records_selection_kinds(rt):
    result = rt.execute(
        lambda r: {"computed": 42},
        mission_id="m-sel",
        objective="record selection",
        records={
            "selected": "selected fact",
            "rejected": "rejected fact",
            "stale": "stale fact",
            "missing": "missing fact",
            "conflicting": "conflicting fact",
        },
        evidence=_fact_evidence("1.2.3"),
        rendered_context="MISSION m-sel objective=record selection | {\"fact\": \"1.2.3\"}",
    )
    assert result["retrieved_counts"] == {
        "selected": 1, "rejected": 1, "stale": 1, "missing": 1, "conflicting": 1,
    }
    for kind in ("selected", "rejected", "stale", "missing", "conflicting"):
        assert kind in result["selection_ids"]


# --- governed execute -------------------------------------------------------

def _registered_verified_capability(rt, cap_id="cap_test_op"):
    rt.registry.register(cap_id, "does test op", "capt_solo", lifecycle="verified")
    rt.proof.record("test_pass", "pytest", "h1", "t", scope=cap_id)
    rt.proof.set_requirements(cap_id, [ProofRequirement("test_pass", 1, cap_id)])


def test_execute_governed_operation(rt, tmp_path):
    _registered_verified_capability(rt)
    result = rt.execute(
        lambda r: {"computed": 42},
        mission_id="m-run",
        objective="run deterministic op",
        capability_id="cap_test_op",
        records={"selected": "sel"},
        evidence=_fact_evidence("1.2.3"),
        rendered_context="MISSION m-run objective=run deterministic op | {\"fact\": \"1.2.3\"}",
    )
    assert result["ok"] is True
    assert result["receipt"]["status"] == "committed"
    assert result["claim_verdict"]["supported"] is True
    assert result["checkpoint_id"]
    assert result["contextpack"]["validation"] == "PASS"

    log = _event_log_text(rt)
    assert "mission.operation.started" in log
    assert "mission.checkpoint.written" in log
    assert "mission.operation.completed" in log

    # evidence + hash sidecar persisted
    ev_file = rt.config.evidence_dir / f"m-run_{result['tx_id']}.json"
    assert ev_file.exists()
    sidecar = ev_file.with_suffix(".sha256")
    assert sidecar.exists()
    recorded_digest = sidecar.read_text().strip().split()[0].split(":")[1]
    actual = hashlib.sha256(ev_file.read_bytes()).hexdigest()
    assert recorded_digest == actual

    # completion event does NOT contradict CTP state: receipt committed
    assert result["receipt"]["status"] == "committed"
    assert json.loads(
        [l for l in log.splitlines() if "mission.operation.completed" in l][-1]
    )["payload"]["receipt_status"] == "committed"


def test_execute_aborts_on_failure_no_completion_event(rt):
    with pytest.raises(RuntimeError, match="boom"):
        rt.execute(
            lambda r: (_ for _ in ()).throw(RuntimeError("boom")),
            mission_id="m-fail",
            objective="fail op",
            records={"selected": "sel"},
            evidence=_fact_evidence("1.2.3"),
            rendered_context="MISSION m-fail objective=fail op | {\"fact\": \"1.2.3\"}",
        )
    log = _event_log_text(rt)
    assert "mission.operation.completed" not in log
    assert "mission.operation.failed" in log

    # CTP state is aborted — read from a fresh journal on the same dir
    failed = [l for l in log.splitlines() if "mission.operation.failed" in l][-1]
    tx_id = json.loads(failed)["payload"]["tx_id"]
    ctp2 = CTPRuntime(journal_dir=rt.config.journal_dir)
    try:
        assert ctp2.get_receipt(tx_id).status == "aborted"
    finally:
        ctp2.close()


def test_execute_claim_unsupported_when_aggregate_unsatisfied(rt):
    # lifecycle=verified with a DECLARED requirement but ZERO proof records
    # -> aggregate unsatisfied -> ClaimGuard must downgrade
    rt.registry.register("cap_gap_op", "does gap op", "capt_solo", lifecycle="verified")
    rt.proof.set_requirements("cap_gap_op", [ProofRequirement("test_pass", 1, "cap_gap_op")])
    result = rt.execute(
        lambda r: {"computed": 7},
        mission_id="m-gap",
        objective="run gap op",
        capability_id="cap_gap_op",
        records={"selected": "sel"},
        evidence=_fact_evidence("1.2.3"),
        rendered_context="MISSION m-gap objective=run gap op | {\"fact\": \"1.2.3\"}",
    )
    assert result["ok"] is True
    assert result["claim_verdict"]["supported"] is False
    assert "proof aggregate unsatisfied" in result["claim_verdict"]["reason"]


# --- KHSB durable log: idempotent delivery ----------------------------------

def test_duplicate_khsb_delivery_idempotent(rt):
    msg_id = rt.bus.publish("mission.operation.started", {"a": 1})
    msg = [m for m in rt.bus._history if m.message_id == msg_id][0]
    before = rt.events.count
    rt.events._handle(msg)  # duplicate delivery of the SAME message
    rt.events._handle(msg)
    assert rt.events.count == before  # not appended twice


def test_khsb_log_dedupes_across_restart(rt, tmp_path):
    rt.bus.publish("mission.operation.started", {"restart": True})
    first_id = json.loads(_event_log_text(rt).splitlines()[0])["message_id"]

    rt2 = CAPTRuntime.load(rt.config)  # fresh process-equivalent on same log
    try:
        before = rt2.events.count
        fake = SimpleNamespace(
            message_id=first_id, topic="mission.operation.started",
            payload={}, correlation_id=None, type="event", ts=0,
        )
        rt2.events._handle(fake)  # duplicate of a pre-restart message
        assert rt2.events.count == before  # skipped (seen in prior process)
    finally:
        rt2.close()


# --- resume by session lookup -----------------------------------------------

def test_resume_from_session_lookup(rt):
    result = rt.execute(
        lambda r: {"computed": 1},
        mission_id="m-resume",
        objective="resume me",
        records={"selected": "sel"},
        evidence=_fact_evidence("1.2.3"),
        rendered_context="MISSION m-resume objective=resume me | {\"fact\": \"1.2.3\"}",
    )
    sid = result["session_id"]

    # fresh runtime on the same configuration — only session lookup is used
    rt2 = CAPTRuntime.load(rt.config)
    try:
        pkt = rt2.lifecycle.sessions.resume(sid)
        assert pkt.session_id == sid
        # CTP receipt visible across processes
        rcpt = rt2.ctp.get_receipt(result["tx_id"])
        assert rcpt.status == "committed"
    finally:
        rt2.close()
