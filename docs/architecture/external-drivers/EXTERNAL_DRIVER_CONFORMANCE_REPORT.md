# External Driver Conformance Report (Gate A — OpenHarness)

## Result: M0_EXTERNAL_DRIVER_CONFORMANCE_PROVEN (pending final PR)

## Genuine execution evidence

- External harness: OpenHarness `oh` 0.1.9 (openharness-ai wheel).
- Invocation: `oh -p "<read-only analysis prompt>" --output-format text
  --max-turns 6 --permission-mode default`, run as a subprocess from
  `OpenHarnessExternalDriver.submit`.
- Local model: Ollama `ornith-1.0-9b` at `http://127.0.0.1:11434/v1`.
- Ollama server log confirms `POST /v1/chat/completions` to 127.0.0.1:11434 with
  model `ornith-1.0-9b`. No hosted provider contacted.
- Live test `test_genuine_openharness_executes_read_only_task` PASSED: the harness
  read the fixture repo and identified the SQL injection at `pkg/core.py:7` (the
  intentional defect) plus the bare `except:` at line 12.

## Frozen contract compliance

- The adapter implements the frozen `ExecutionDriver` Protocol (describe, submit,
  inspect, cancel, resume, reconcile).
- Work orders are validated with `require("ExecutionDriverWorkOrder", ...)` before
  dispatch (frozen schema 1.0.0).
- The 51-test frozen M0-B conformance suite passes UNCHANGED (51 passed).
- No contract field, enum, or semantic was modified.

## Authority boundary

- CAPT retains exclusive authority. The harness returns only untrusted
  `DriverObservation` + `DriverArtifactCandidate` + `DriverReceiptCandidate`.
- CAPT ingestion validates identity, run id, paths, digests; CAPT verification and
  ClaimGuard promote to evidence/claims. The harness cannot create authoritative
  state (enforced by `reject_fabricated_authoritative` + schema trust=untrusted).

## Read-only proof

- Target fixture repo digest before execution:
  `880a5f1b4dac6638047671a9821d2b8010e9e4089f3cc5e0f217e451693ede06`
- Target fixture repo digest after execution: IDENTICAL.
- Fixture tree unchanged (4 files; no writes, no new artifacts in target).
- Only localhost Ollama network contact observed.

## Restart / reconciliation

- `test_genuine_openharness_reconcile_after_completion` PASSED: after a completed
  run, `reconcile` returns `reconciled_completed`.
- The one-shot process model means reconciliation maps process exit state to CAPT
  reconciliation outcomes honestly (no fake restart).

## Removal / swap

- `test_base_runtime_imports_without_openharness_package` PASSED: base CAPT imports
  without the openharness Python package (adapter shells out; no import at
  base-import time).
- `test_reference_driver_still_works_independently` PASSED: the CAPT reference
  driver still works; same work order runs through it with equivalent CAPT-level
  semantics.
- Frozen M0-B 51-test suite passes unchanged with the external adapter present.

## Unsupported lifecycle features

- `resume`: not supported by one-shot `oh -p`; descriptor declares
  `resumeSupported: false`; `resume()` raises `OpenHarnessLifecycleError`.

## Test counts

- Gate A suite: 22 passed (non-slow) + 2 passed (slow live) + 1 xfailed (documented
  max-use gap).
- Frozen M0-B: 51 passed (unchanged).
- M0-A targeted: 48 passed. All capt_runtime: 130 passed, 1 xfailed.

## Residual risks

- `verify_lease` max-use exhaustion not enforced (frozen M0-B gap; documented).
- Third-party harness binary not line-audited; mitigated by isolation.
- Local Ollama model quality is environment-specific; not a CAPT intelligence claim.
