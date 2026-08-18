# CAPT-UPG-009: Isolated Workspace Mutations + Governed Promotion Lifecycle — Evidence Manifest

- **Campaign ID**: `CAPT-UPG-009`
- **Issue**: https://github.com/knowurknottty/CAPT_core/issues/67
- **Branch**: `upgrade/capt-upg-009-workspace-promotion`
- **Base SHA**: `50ec613` (`upgrade/capt-upg-008-effect-recovery`)
- **Status**: `IMPLEMENTED_VERIFIED_READY_FOR_OWNER_REVIEW`

---

## 1. Scope & Implementation

- Implemented `promote_artifact_to_destination` in `capt_runtime/artifact_workspace.py` providing transactional promotion from staged candidate paths into destination paths only after verified ClaimGuard acceptance and exact content digest validation.
- Enforced strict fail-closed rejection (`IntegrityViolation`) if unverified or if the content digest does not match the expected digest.
- Added comprehensive unit tests in `tests/capt_runtime/test_artifact_workspace.py` covering:
  - Workspace descriptor validation
  - Path traversal rejection
  - Write outside lease rejection
  - Symlink escape rejection
  - Staging within lease
  - Fabricated authoritative rejection
  - Promotion requiring verification
  - Transactional promotion to final destination path

---

## 2. Test Evidence

```bash
pytest tests/capt_runtime/test_artifact_workspace.py
```

Output:
```
============================== 12 passed in 0.06s ==============================
```
