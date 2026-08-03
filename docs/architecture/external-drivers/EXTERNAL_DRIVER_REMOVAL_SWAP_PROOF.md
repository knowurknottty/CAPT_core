# External Driver Removal & Swap Proof (Gate A — OpenHarness)

## Goal

Prove CAPT is not owned by the external harness: it must remain fully functional
if OpenHarness is removed or swapped for the CAPT reference driver.

## Removal proof

Test: `test_base_runtime_imports_without_openharness_package`

- The external adapter (`capt_runtime.external_drivers.openharness`) imports only
  frozen CAPT contracts (`...drivers.require`) and stdlib. It does NOT import the
  `openharness` Python package at base-runtime import time.
- Base CAPT runtime imports succeed without the openharness Python package on
  `sys.path`.
- The CAPT reference driver (`capt_runtime.drivers.openharness.OpenHarnessDriver`)
  remains importable and functional.
- Frozen M0-A and M0-B tests pass unchanged with the external adapter present.
- Frozen contracts remain unchanged (no schema edit).

Result: **PASS** — CAPT runtime does not depend on the external harness.

## Swap proof

Test: `test_reference_driver_still_works_independently` + frozen M0-B suite

Same bounded work order executed through:

1. **Genuine external driver** (`OpenHarnessExternalDriver` → real `oh` subprocess
   → local Ollama). Returns untrusted observation + artifact candidate + receipt.
2. **CAPT reference driver** (`OpenHarnessDriver`, M0-B). Returns the same record
   shapes from its own read-only inspection.

Equivalent CAPT-level semantics verified:
- same `ExecutionDriverWorkOrder` contract (no schema change),
- same capability lease validation (`verify_lease`),
- same untrusted-ingestion path (`ingestion.py`),
- same evidence/verification requirements (`verification.py`),
- same ClaimGuard constraints (`guard_claim`),
- same checkpoint/replay semantics (DriverHost).

Differences (allowed, not contract changes):
- The external driver delegates analysis to a real LLM via OpenHarness; the
  reference driver computes a structural observation directly. Prose content
  differs; CAPT-level semantics are equivalent.
- The external driver's `resumeSupported=false` (one-shot); the reference driver
  also does not implement real resume.

Result: **PASS** — swapping the driver does not alter CAPT contracts or authority.

## Conclusion

CAPT is framework-independent. The external OpenHarness integration is an isolated
adapter; removing or swapping it leaves CAPT runtime, frozen contracts, and the
reference driver fully intact.
