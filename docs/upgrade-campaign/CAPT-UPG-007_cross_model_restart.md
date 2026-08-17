# CAPT-UPG-007: True Cross-Model Process Restart Continuity — Evidence Manifest

- **Campaign ID**: `CAPT-UPG-007`
- **Issue**: https://github.com/knowurknottty/CAPT_core/issues/63
- **Branch**: `upgrade/capt-upg-007-cross-model-restart`
- **Base SHA**: `d097c91` (`upgrade/capt-upg-006-live-provider-acceptance`)
- **Status**: `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

---

## 1. Scope & Implementation

- Implemented `tests/capt_runtime/test_cross_model_process_continuity.py`.
- Verified real OS subprocess execution where Process 1 creates and seeds the runtime, terminates via `SIGTERM`, and Process 2 starts against the identical SQLite ledger.
- Proved that restart reconciliation safely marks running tasks as `suspended` for governed reconciliation rather than duplicating unverified executions or corrupting streams.

---

## 2. Test Evidence

```bash
pytest tests/capt_runtime/test_cross_model_process_continuity.py
```

Output:
```
============================== 1 passed in 0.28s ===============================
```
