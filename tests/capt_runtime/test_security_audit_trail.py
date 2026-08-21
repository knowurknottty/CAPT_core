"""Tests for durable security rejection audit trail (CAPT-UPG-003)."""

from pathlib import Path
from capt_runtime.store import EventStore


def test_security_rejection_audit_recording(tmp_path: Path):
    ledger = tmp_path / "audit.db"
    store = EventStore(str(ledger))

    try:
        # Record security rejections
        store.record_security_rejection(
            rejection_id="rej-001",
            rejection_kind="invalid_capability_lease",
            details={"requested_scope": "fs:write:/etc", "error": "SCOPE_DENIED"},
            actor_id="actor-test-1",
        )
        store.record_security_rejection(
            rejection_id="rej-002",
            rejection_kind="unauthenticated_ipc_attempt",
            details={"remote_ip": "127.0.0.1"},
            actor_id="unknown",
        )

        # Query rejections
        rejections = store.list_security_rejections()
        assert len(rejections) == 2
        kinds = [r["rejectionKind"] for r in rejections]
        assert "invalid_capability_lease" in kinds
        assert "unauthenticated_ipc_attempt" in kinds
        assert any(
            row["details"].get("requested_scope") == "fs:write:/etc"
            for row in rejections
        )
    finally:
        store.close()


def test_security_rejection_ids_are_immutable(tmp_path: Path):
    import sqlite3

    store = EventStore(str(tmp_path / "audit.db"))
    try:
        store.record_security_rejection(
            rejection_id="rej-fixed",
            rejection_kind="unauthenticated_ipc_attempt",
            details={"reason": "first"},
        )
        try:
            store.record_security_rejection(
                rejection_id="rej-fixed",
                rejection_kind="unauthenticated_ipc_attempt",
                details={"reason": "replacement"},
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("security audit IDs must not overwrite prior records")
        rows = store.list_security_rejections()
        assert rows[0]["details"] == {"reason": "first"}
    finally:
        store.close()
