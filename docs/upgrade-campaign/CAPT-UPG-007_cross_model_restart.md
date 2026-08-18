# CAPT-UPG-007: True Cross-Model Process Restart Continuity — Evidence Manifest

- **Campaign ID**: `CAPT-UPG-007`
- **Issue**: https://github.com/knowurknottty/CAPT_core/issues/63
- **Branch**: `upgrade/capt-upg-007-cross-model-restart`
- **Base SHA**: `fa02f1a` (`upgrade/capt-upg-006-live-provider-acceptance`)
- **Status**: `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

---

## 1. Scope & Implementation

- Implemented true end-to-end multi-process cross-model continuity test in `tests/capt_runtime/test_cross_model_process_continuity.py`.
- **Phase 1**: Subprocess 1 boots `capt_runtime_service.py`, dispatches Turn 1 with Model A (`ollama` / `llama3.2:latest`), persists authoritative state to SQLite ledger, and experiences unhandled termination (process death).
- **Phase 2**: Subprocess 2 boots against the identical SQLite ledger, confirms Model A's state is preserved, and dispatches Turn 2 with a distinct Model B (`openrouter` / `anthropic/claude-3-7-sonnet`).
- Proved that both distinct model identities and cognitive provenance envelopes are durably committed to the ledger with no duplicate inference, stream corruption, or lost events.

---

## 2. Test Evidence

```bash
pytest tests/capt_runtime/test_cross_model_process_continuity.py
```

Output:
```
============================== 1 passed in 0.56s ===============================
```
