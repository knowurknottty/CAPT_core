"""Phase 3E — Replay, Consent, Local Synchronization tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from capt_solo.memory.replay import (
    ReplayEngine, ReplayEvent, ReplayMode, ReplayStatus,
)
from capt_solo.memory.consent import ConsentStore, ConsentDecision
from capt_solo.memory.sync import (
    FilesystemTransport, ExportImportTransport, RemovableMediaTransport,
    LanTransport, SyncManifest, VersionVector, merge_manifests, Transport,
)


# ---------------- Replay ----------------
def test_e_replay_reconstruct_no_side_effects():
    eng = ReplayEngine()
    events = [
        ReplayEvent("e1", "observation", {"x": 1}, 1.0),
        ReplayEvent("e2", "inference", {"x": 2}, 2.0),
    ]
    res = eng.replay(events, mode=ReplayMode.RECONSTRUCT)
    assert res.status == ReplayStatus.COMPLETED.value
    assert res.events_replayed == 2
    assert res.reconstructed_state["event_e1"] == {"x": 1}


def test_e_replay_dry_run_is_simulation():
    eng = ReplayEngine()
    res = eng.dry_run([ReplayEvent("e1", "action", {}, 1.0)])
    assert res.mode == "dry_run"
    assert res.status == ReplayStatus.COMPLETED.value


def test_e_replay_refuses_auto_side_effects():
    eng = ReplayEngine()
    events = [ReplayEvent("e1", "external", {"cmd": "rm"}, 1.0, side_effect=True)]
    # EXECUTE without authorize -> refused
    with pytest.raises(ValueError):
        eng.replay(events, mode=ReplayMode.EXECUTE)
    # EXECUTE with authorize but event.side_effect True -> still refused
    # (replay engine never auto-executes unsafe external actions)
    with pytest.raises(RuntimeError):
        eng.replay(events, mode=ReplayMode.EXECUTE, authorize_execute=True)


def test_e_replay_execute_with_safe_apply():
    eng = ReplayEngine()
    applied = []
    events = [ReplayEvent("e1", "safe", {"v": 1}, 1.0, side_effect=False)]
    res = eng.replay(events, mode=ReplayMode.EXECUTE, authorize_execute=True,
                     apply_fn=lambda e: applied.append(e.payload))
    assert res.status == ReplayStatus.COMPLETED.value
    assert applied == [{"v": 1}]


def test_e_replay_partial_failure_reported():
    eng = ReplayEngine()
    events = [
        ReplayEvent("e1", "safe", {}, 1.0, side_effect=False),
        ReplayEvent("e2", "boom", {}, 2.0, side_effect=False),
    ]
    res = eng.replay(events, mode=ReplayMode.EXECUTE, authorize_execute=True,
                     partial=True,
                     apply_fn=lambda e: (_ for _ in ()).throw(RuntimeError("x")) if e.kind == "boom" else None)
    assert res.status == ReplayStatus.COMPLETED.value
    assert len(res.failures) == 1


def test_e_replay_cancel():
    eng = ReplayEngine()
    events = [ReplayEvent("e1", "safe", {}, 1.0), ReplayEvent("e2", "safe", {}, 2.0)]
    res = eng.replay(events, mode=ReplayMode.RECONSTRUCT)
    # cancel after start not possible (synchronous); test cancel idempotency
    eng.cancel(res.replay_id)
    assert eng._cancelled[res.replay_id] is True


# ---------------- Consent ----------------
def test_e_consent_default_deny():
    cs = ConsentStore()
    assert cs.check("agent-1", "memory:store:sensitive", "store") is False


def test_e_consent_grant_and_check():
    cs = ConsentStore()
    cs.grant("agent-1", "memory:store:sensitive", ["store", "read"])
    assert cs.check("agent-1", "memory:store:sensitive", "store") is True
    assert cs.check("agent-1", "memory:store:sensitive", "delete") is False


def test_e_consent_explicit_deny_wins():
    cs = ConsentStore()
    cs.grant("agent-1", "memory:export", ["*"])
    cs.deny("agent-1", "memory:export", ["*"])
    assert cs.check("agent-1", "memory:export", "export") is False


def test_e_consent_expiry_and_revoke():
    cs = ConsentStore()
    cs.grant("agent-1", "scope", ["op"], expires_at=1.0)  # already expired
    assert cs.check("agent-1", "scope", "op", now=100.0) is False
    rec = cs.grant("agent-2", "scope", ["op"])
    cs.revoke(rec.consent_id)
    assert cs.check("agent-2", "scope", "op") is False


def test_e_consent_audit_trail():
    cs = ConsentStore()
    cs.grant("a", "s", ["op"])
    cs.check("a", "s", "op")
    cs.check("a", "s", "other")
    trail = cs.audit_trail(subject="a")
    assert len(trail) == 2
    assert trail[0]["allowed"] is True
    assert trail[1]["allowed"] is False


def test_e_consent_export_import():
    cs = ConsentStore()
    cs.grant("a", "s", ["op"])
    data = cs.export()
    cs2 = ConsentStore()
    n = cs2.import_records(data)
    assert n == 1
    assert cs2.check("a", "s", "op") is True


# ---------------- Synchronization ----------------
def _manifest():
    return SyncManifest(
        bundle_id="b1", replica_id="r1",
        version=VersionVector(vectors={"r1": 1}),
        records=[{"memory_id": "m1", "content": "x"}],
        tombstones=[],
    )


def test_e_sync_filesystem_roundtrip(tmp_path):
    t = FilesystemTransport()
    m = _manifest()
    p = t.export_bundle(m, tmp_path / "sync.json")
    m2 = t.import_bundle(p)
    assert m2.replica_id == "r1"
    assert m2.records[0]["memory_id"] == "m1"


def test_e_sync_removable_media_namespaced(tmp_path):
    t = RemovableMediaTransport()
    p = t.export_bundle(_manifest(), tmp_path / "media.json")
    m = t.import_bundle(p)
    assert m.provenance.get("media") == "removable"


def test_e_sync_lan_disabled_by_default(tmp_path):
    t = LanTransport()  # not enabled
    with pytest.raises(RuntimeError):
        t.export_bundle(_manifest(), tmp_path / "lan.json")
    # enabled with auth+encrypt works
    t2 = LanTransport(enabled=True, authenticate=True, encrypt=True)
    p = t2.export_bundle(_manifest(), tmp_path / "lan2.json")
    assert p.exists()


def test_e_sync_merge_union_and_tombstone():
    local = SyncManifest("l", "r1", VersionVector(vectors={"r1": 1}),
                         records=[{"memory_id": "m1", "content": "local"}],
                         tombstones=[])
    remote = SyncManifest("r", "r2", VersionVector(vectors={"r2": 1}),
                          records=[{"memory_id": "m2", "content": "remote"}],
                          tombstones=["m1"])
    merged = merge_manifests(local, remote)
    ids = {r["memory_id"] for r in merged.records}
    assert ids == {"m2"}  # m1 tombstoned
    assert "r1" in merged.version.vectors and "r2" in merged.version.vectors


def test_e_sync_version_vector_dominates():
    a = VersionVector(vectors={"r1": 2, "r2": 1})
    b = VersionVector(vectors={"r1": 1, "r2": 1})
    assert a.dominates(b)
    assert not b.dominates(a)
