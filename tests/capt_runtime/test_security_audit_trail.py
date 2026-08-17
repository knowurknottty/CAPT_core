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
        assert rejections[0]["details"]["requested_scope"] == "fs:write:/etc" or rejections[1]["details"]["requested_scope"] == "fs:write:/etc"
    finally:
        store.close()
