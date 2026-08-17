# CAPT-UPG-002: Persistent State Permissions & At-Rest Protection — Evidence Manifest

- **Campaign ID**: `CAPT-UPG-002`
- **Issue**: https://github.com/knowurknottty/CAPT_core/issues/53
- **Branch**: `upgrade/capt-upg-002-state-permissions`
- **Base SHA**: `cf65e81` (`upgrade/capt-upg-001-ipc-framing`)
- **Status**: `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

---

## 1. Scope & Implementation

- Hardened `EventStore` in `capt_runtime/store.py` to enforce strict `0o700` parent directory permissions and `0o600` file permissions on SQLite database, WAL, and SHM files upon creation and re-open.
- Protects local persistent state against permission drift.

---

## 2. Test Evidence

```bash
pytest tests/capt_runtime/test_state_permissions.py
```

Output:
```
============================== 1 passed in 0.10s ===============================
```
