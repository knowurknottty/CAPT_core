# M0-B Triple Recursion Ledger (Part 17)

Three passes over every substantial M0-B artifact: Construct → Adversarial Review
→ Reconcile. Findings are auditable; hidden chain-of-thought is excluded.

## Pass 1 — Construct

Created:
- ADRs 0120–0127 (driver trust boundary, selection, read-only capability types,
  lifecycle, reconciliation, context minimization, observation validation, M0-B
  exclusions).
- `contracts/schema/driver.schema.json` — 22 M0-B contract types, generated
  TS+Py bindings (no hand-maintained divergence).
- `capt_runtime/drivers/__init__.py` — `ExecutionDriver` Protocol (narrow; no
  GovernanceKernel/PolicyEngine/ClaimGuard/Capability/EventLedger/Mission/Task
  mutation, no raw DB handles, no credentials).
- `capt_runtime/drivers/registry.py` — `DriverRegistry` (duplicate-ID rejection,
  immutable descriptor identity, version compat, capability declarations,
  registration audit event, disable, health, trust classification, digest).
- `capt_runtime/drivers/openharness.py` — `OpenHarnessDriver`, a REAL read-only
  repository inspector (no mocks; actually reads the filesystem, writes one
  artifact to staging).
- `capt_runtime/driver_run.py` — `DriverRunAggregate` state machine (created,
  queued, running, suspended, completed, cancelled, failed, lost, reconciled) with
  legal-transition table and terminal immutability.
- `capt_runtime/context_slice.py` — `build_context_slice` with over-disclosure
  guard (rejects governance/cognition/policy/ledger/credential objects by type).
- `capt_runtime/ingestion.py` — untrusted observation/artifact/receipt validation
  (schema, identity, run ID, seq, size, path, checksum, duplicate, capability
  scope, mission/task; rejects fabricated authoritative events/verification/claims).
- `capt_runtime/verification.py` — independent verification (repo read, artifact
  exists, checksum matches, observation corresponds to source, no unauthorized
  writes, no git mutation, leases cover actions, driver emitted no authoritative
  state) + ClaimGuard bounded-claim gate.
- `capt_runtime/reconciliation.py` — 10-case reconciliation with the 6 result
  enums.
- `capt_runtime/capability.py` — read-only capability model (allow/deny lists,
  lease re-validation before every external call, work-order blocklist).
- `capt_runtime/driver_host.py` — orchestration wiring the trust boundary.
- `tests/capt_runtime/test_m0b_driver.py` — 42 conformance tests.

## Pass 2 — Adversarial Review (attempted defeats)

| # | Attack attempted | Result | Defense |
|---|---|---|---|
| 1 | Driver emits authoritative `EventEnvelope`/`VerificationResult` | REJECTED | `reject_fabricated_authoritative` (ingestion.py) |
| 2 | Forged receipt (artifact missing) | REJECTED | `validate_artifact_candidate` checks path exists |
| 3 | Duplicate observation | DEDUPED | `seen` map keyed by observationId |
| 4 | Conflicting duplicate (same id, diff payload) | REJECTED | payload hash compare |
| 5 | Stale lease (now > validUntil) | REJECTED | `verify_lease` time check |
| 6 | Revoked lease | REJECTED | `verify_lease` revoked flag |
| 7 | Wrong driver identity in lease | REJECTED | `verify_lease` driverId match |
| 8 | Path escape (resource outside scope) | REJECTED | `verify_lease` allowedPaths prefix check |
| 9 | Context leakage (governance object in ContextSlice) | REJECTED | `_scan_forbidden` type-name guard |
| 10 | Symlink/path escape in artifact | REJECTED | artifact path must be under staging root |
| 11 | Unauthorized file write (RepositoryWrite in WO) | REJECTED | `check_work_order_operations` blocklist |
| 12 | Git mutation in WO | REJECTED | blocklist |
| 13 | Hidden git mutation by driver | DETECTED | `verify_repository_unchanged` (tree digest diff) |
| 14 | Driver crash after artifact creation | HANDLED | reconciliation: artifact present + lease valid → reconciled_completed |
| 15 | Runtime crash before final event | HANDLED | replay from ledger; terminal state immutable |
| 16 | Mismatched artifact checksum | REJECTED | `build_verification_result` checksum compare |
| 17 | Driver version substitution | REJECTED | registry `verify_identity` digest compare |
| 18 | Overclaim ("The issue was fixed.") | REJECTED | ClaimGuard allowlist |
| 19 | Cross-mission observation | REJECTED | `validate_observation` missionId/taskId match |
| 20 | Stale aggregate version replay | REJECTED | store optimistic-concurrency guard |

## Pass 3 — Reconcile

| Finding | Affected files | Correction | Verification evidence | Residual uncertainty |
|---|---|---|---|---|
| Operation vocabulary mismatch between contract enum (`RepositoryRead`) and capability model (`repository.read`) | capability.py, driver_host.py | Added `_OPERATION_ALIASES` + `canonical_operation`; `verify_lease` canonicalizes both WO and lease ops | test_capability_* (8 tests) pass | None |
| `dispatch` accepted write ops before schema validation | driver_host.py | Replaced inline check with `check_work_order_operations` (CapabilityViolation) + `verify_lease` | test_write_operation_rejected_before_dispatch passes | None |
| Lease scope used placeholder `/r`, broke real-repo path check | test_m0b_driver.py | `_lease(root=...)`; call sites pass `env["repo"]` | test_repository_hashes_unchanged, test_artifact_writing_allowed_only_in_staging, acceptance pass | None |
| `test_stale_version_rejection` used service layer that auto-bumped version (no conflict) | test_m0b_driver.py | Rewrote to exercise store `commit_command` with explicit stale expected_version=0 | test_stale_version_rejection passes | None |
| `CapabilityViolation` missing from errors.py | errors.py | Added class (kept `CapabilityDenied` for compat) | import + tests pass | None |
| Over-disclosure test used `FakeGovernance` not in forbidden set | test_m0b_driver.py | Use `GovernanceKernel` (matches forbidden type name) | test_context_over_disclosure_rejected passes | None |
| `command()` requires `sha256:` fingerprint pattern | test_m0b_driver.py | Pass valid 64-hex fingerprints | replay/stale tests pass | None |
| ruff E702 semicolons in test setup | test_m0b_driver.py | Split statements; `ruff --fix` | ruff clean on M0-B files | 88 pre-existing ruff errors in M0-A files left untouched (out of M0-B scope) |
| `validate_observation` checked `observedBy` against type names (dead check; can never match a driver identity) | ingestion.py, driver_host.py, test_m0b_driver.py | Replaced with `expected_observed_by` identity equality (driver impersonation defense); added `test_driver_impersonation_rejected` | test_driver_impersonation_rejected + all observation tests pass | None |
| `driver_run.py` docstring listed `reconciliation_required` but code uses `lost` | driver_run.py | Aligned docstring to actual state machine | doc/code consistent | None |
| Security-review gaps (replay-after-cancel, replay-after-reconcile, artifact substitution, symlink traversal, forged completion, capability escalation, authority confusion, context leakage) | test_m0b_driver.py | Added 9 adversarial tests covering the mission's security checklist | 51 M0-B tests pass; full suite 469 passed / 44 skipped | None |

## Residual uncertainty (honest)

- mypy not installed in this environment → no static type gate run (environmental,
  not a product defect). Runtime uses generated bindings + runtime contract
  validation as the type-enforcement mechanism.
- OpenHarness is integrated as a REAL read-only inspector (no mock), but it is a
  CAPT reference adapter labeled honestly; no external network call is made.
- The 44 skipped tests are the optional anti-token-extraction package (absent in
  this environment), masking no failure.
