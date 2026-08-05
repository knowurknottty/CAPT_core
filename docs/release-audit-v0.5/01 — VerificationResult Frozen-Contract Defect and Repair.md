# VerificationResult Frozen-Contract Defect and Repair

## Defect
The shipped `build_verification_result()` in `capt_runtime/verification.py` violated the frozen `verification.schema.json` VerificationResult contract in 5 ways:

1. Missing required `claimId` field
2. Missing required `strategy` field
3. Missing required `verifiedAt` field
4. `status.supportingEvidenceIds` was `[]` (violates `minItems: 1`)
5. Contained forbidden `observedBy`, `checks`, `trust` (`additionalProperties: false`)

## Runtime Consequence
`RuntimeService.record_verification()` (`services.py` line 848) already accessed `verification['claimId']` — it expected the frozen contract but `build_verification_result()` never produced it. The end-to-end path would crash at `require('VerificationResult', ...)` if ever called with a `build_verification_result` output. The shipped runtime never persisted verification/evidence events through the claim lifecycle via this builder.

## Repair (commit b79c4f05784d001268e3fef523755365b1f5888e)
- `build_verification_result` now returns contract-conforming record with `claimId`, `strategy='artifact_hashing'`, `verifiedAt` (timestamp), `>=1` supporting evidence id
- View-level annotations (`trust`, `checks`, `observedBy`) preserved under `_view` key
- `strip_view()` function added to remove `_view` before `require()` or EventStore commit
- `DriverHost.verify()` accepts `claim_id` + `supporting_evidence_ids` + `verified_at` params
- `RuntimeService.record_verification()` calls `strip_view` before `require()` and uses the stripped record for the event payload
- Desktop `verification()` query flattens `_view` to top-level for GUI consumers (so `vr['trust']` and `vr['checks']` still work in the view layer)
- Added `build_artifact_hash_evidence()` and `build_command_exit_evidence()` helpers (frozen `evidence.schema.json` already permits these kinds)
- Tests updated: `vr['checks']` -> `vr['_view']['checks']`, `vr['trust']` -> `vr['_view']['trust']` in `test_m0b_driver.py`, `test_hermes_driver.py`, `hermes_e2e_proof.py`

## Contract Status
- Frozen schema changed: **NO**
- Runtime changed to conform: **YES**
- `contracts/` directory modified: **NO** (verified via `git diff --name-only contracts/` = empty)

## Caveat: _view Architectural Risk
The `_view` mechanism is a transitional design. Any persistence path that forgets `strip_view()` could reintroduce contract failure by committing a record with forbidden `additionalProperties` to the EventStore. Future work should implement an explicit separation between the contract record type and the presentation view type (e.g. a `VerificationResult` dataclass + a `VerificationView` dataclass), eliminating the `_view` dict key entirely.

## Evidence
- **Commit SHA:** `b79c4f05784d001268e3fef523755365b1f5888e`
- **Commit message:** `fix(verification): conform to frozen VerificationResult contract`
- **Files changed: 7** (`capt_runtime/verification.py`, `capt_runtime/driver_host.py`, `capt_runtime/services.py`, `desktop/capt_runtime_service.py`, `tests/capt_runtime/hermes_e2e_proof.py`, `tests/capt_runtime/test_hermes_driver.py`, `tests/capt_runtime/test_m0b_driver.py`)
- **Test result:** 766 passed, 12 deselected, exit 0 (log: `/tmp/capt-verify-verification-fix.log`)
- **Conformance probe:** `build_verification_result` output passes `require('VerificationResult', ...)` after `strip_view()`; `build_artifact_hash_evidence` and `build_command_exit_evidence` both pass `require('EvidenceRecord', ...)`
- **contracts/ unmodified:** `git diff --name-only contracts/` returns empty
