# CAPT-UPG-008: Destructive / Ambiguous Effect Recovery — Evidence Manifest

- **Campaign ID**: `CAPT-UPG-008`
- **Issue**: https://github.com/knowurknottty/CAPT_core/issues/65
- **Branch**: `upgrade/capt-upg-008-effect-recovery`
- **Base SHA**: `d22ab15` (`upgrade/capt-upg-007-cross-model-restart`)
- **Status**: `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

---

## 1. Scope & Implementation

- Verified the complete Ouroboros lifecycle crash recovery matrix across all 8 named failure points:
  - `reservation`
  - `dispatch`
  - `driver_completed`
  - `capability_finalized`
  - `evidence_recorded`
  - `verification_recorded`
  - `claim_decided`
  - `task_terminal`
- Aligned `desktop/capt_runtime_service.py` to handle both `promptAssemblyDigest` and `assemblyDigest` keys when verifying prompt approvals.
- Proved that crashes during ambiguous remote states result in `suspended` task states requiring governed reconciliation without automatic redispatch.

---

## 2. Test Evidence

```bash
pytest tests/capt_runtime/test_ouroboros_lifecycle.py
```

Output:
```
============================== 18 passed in 5.89s ==============================
```
