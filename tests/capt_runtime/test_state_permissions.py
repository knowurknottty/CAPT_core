"""Tests for persistent state permissions and at-rest file hardening (CAPT-UPG-002)."""

import os
import stat
from pathlib import Path
from capt_runtime.store import EventStore


def test_event_store_permissions_hardening(tmp_path: Path):
    ledger_dir = tmp_path / "sub_store"
    ledger_file = ledger_dir / "ledger.db"

    # 1. Fresh store initialization
    store = EventStore(str(ledger_file))
    try:
        # Directory must be 0o700
        dir_mode = stat.S_IMODE(os.stat(ledger_dir).st_mode)
        assert dir_mode == 0o700, f"Expected 0o700 for directory, got {oct(dir_mode)}"

        # Database file must be 0o600
        file_mode = stat.S_IMODE(os.stat(ledger_file).st_mode)
        assert file_mode == 0o600, f"Expected 0o600 for file, got {oct(file_mode)}"

        store._harden_permissions()

        # Check WAL/SHM permissions if they exist
        wal_file = ledger_file.with_name(ledger_file.name + "-wal")
        if wal_file.exists():
            wal_mode = stat.S_IMODE(os.stat(wal_file).st_mode)
            assert wal_mode == 0o600, f"Expected 0o600 for wal, got {oct(wal_mode)}"
    finally:
        store.close()

    # 3. Existing file permission repair on re-open
    # Simulate permission drift
    os.chmod(ledger_file, 0o644)
    assert stat.S_IMODE(os.stat(ledger_file).st_mode) == 0o644

    store2 = EventStore(str(ledger_file))
    try:
        repaired_mode = stat.S_IMODE(os.stat(ledger_file).st_mode)
        assert repaired_mode == 0o600, f"Expected 0o600 after repair, got {oct(repaired_mode)}"
    finally:
        store2.close()
