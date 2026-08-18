# CAPT-UPG-008: Destructive / Ambiguous Effect Recovery — Evidence Manifest

- **Campaign ID**: `CAPT-UPG-008`
- **Issue**: https://github.com/knowurknottty/CAPT_core/issues/65
- **Branch**: `upgrade/capt-upg-008-effect-recovery`
- **Base SHA**: `d22ab15` (`upgrade/capt-upg-007-cross-model-restart`)
- **Status**: `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

---

## 1. Scope & Implementation

- Re-established strict fail-closed prompt-assembly approval enforcement in `desktop/capt_runtime_service.py` (`require_approved_prompt_assembly` requires non-empty `approvalRequestId` and rejects omissions with `MODEL_PROMPT_APPROVAL_RECEIPT_REQUIRED` / `AuthorityViolation`).
- Added discriminating negative test in `tests/capt_runtime/test_prompt_approval_binding.py` (`test_missing_approval_receipt_fails_closed`) proving that omitting `approvalRequestId` immediately rejects the dispatch with classification `authority` and code `MODEL_PROMPT_APPROVAL_RECEIPT_REQUIRED`.
- Preserved and verified the complete Ouroboros lifecycle crash recovery matrix across all 8 named failure points:
  - `reservation`
  - `dispatch`
  - `driver_completed`
  - `capability_finalized`
  - `evidence_recorded`
  - `verification_recorded`
  - `claim_decided`
  - `task_terminal`
- Aligned `capt_runtime/checkpoint.py` and `capt_runtime/replay.py` reducers for `HumanApprovalRequested` / `HumanApprovalDecided` stream events.
- Proved that crashes during ambiguous remote states result in `suspended` task states requiring governed reconciliation without automatic redispatch.

---

## 2. Test Evidence

```bash
pytest tests/capt_runtime/test_prompt_approval_binding.py tests/capt_runtime/test_ouroboros_lifecycle.py tests/capt_runtime/test_model_operator.py tests/capt_runtime/test_desktop_m0.py tests/capt_runtime/test_desktop_m1.py tests/capt_runtime/test_desktop_m1_security.py tests/capt_runtime/test_desktop_m1_adversarial.py
```

Output:
```
============================= 69 passed in 10.31s ==============================
```
