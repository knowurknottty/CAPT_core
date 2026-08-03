# M0-B Independent Review (Post–M0-B Pass)

Reviewer: lead runtime engineer, independent of the original M0-B implementation.
Scope: re-validate the prior `M0_B_PROVEN` claim against the actual branch state.
Branch: `feat/capt-runtime-m0b-readonly-driver-proof-hy3` @ `0d851c4535d2f93c3420f4c6d860f4ecd7285163`
PR: #23 (OPEN, DRAFT, base `feat/capt-runtime-m0a-contract-state-proof` @ `6665a6a`)

All commands were re-run fresh on 2026-08-03; counts are NOT carried forward.

## 1. Git and PR state (re-verified)

- Branch: `feat/capt-runtime-m0b-readonly-driver-proof-hy3` ✓
- HEAD: `0d851c4535d2f93c3420f4c6d860f4ecd7285163` ✓
- Base ancestry: `git merge-base --is-ancestor 6665a6a HEAD` → TRUE ✓
- Worktree clean: `git status --porcelain` empty ✓
- Commit list (M0-A..HEAD): 12 M0-B commits (ADRs, schema, bindings, capability
  model, drivers, host, tests, docs, evidence) + prior M0-A/M0-B forensic commits.
- PR #23: OPEN, DRAFT, MERGEABLE, base = proven M0-A branch (not `main`) ✓
- Absence of M0-C code: only a docstring reference in `reconciliation.py`
  ("same semantic discipline is established for M0-C"); no M0-C implementation ✓
- Absence of RuntimeAggregate implementation: no `class RuntimeAggregate`; only
  doc/comment references ✓

## 2. Driver classification (proven by source, not claim)

`OpenHarnessDriver` (`capt_runtime/drivers/openharness.py`):
- Imports/invokes external OpenHarness? **No.** `grep` for `import openharness`,
  `subprocess`, `requests`, `http`, `socket`, `os.system`, `popen` → none.
- What it does: real local read-only filesystem inspection (`Path.rglob`,
  `stat()`, reads file metadata) and writes ONE analysis artifact to the
  designated staging root via `write_text`.
- Classification: **locally-implemented CAPT reference driver inspired by
  OpenHarness**. NOT a genuine external OpenHarness integration; NOT an adapter
  invoking an installed OpenHarness runtime. (Honest label per ADR-0121 / skill
  Mode 27.5 / 28.)

## 3. Authority boundary (proven by interface + call paths)

The driver may only return observations / artifact candidates / receipt
candidates / progress / diagnostics. Verified:
- `ExecutionDriver` Protocol (`drivers/__init__.py`) exposes `describe`,
  `submit`, `inspect`, `cancel`, `resume`, `reconcile` returning untrusted data.
  The module doc explicitly states the driver never receives GovernanceKernel,
  PolicyEngine, ClaimGuard, CapabilityAggregate, EventLedger, etc.
- `drivers/` + `driver_host.py` contain NO imports of MissionAggregate,
  TaskAggregate, CapabilityAggregate, ClaimAggregate, or EventStore mutation APIs.
  The only `append(event)` calls are in `registry.py` for a **driver-registration
  audit log** (driver lifecycle, trust=registration_only) — not CAPT authoritative
  aggregate mutation.
- `driver_host.verify()` is CAPT-owned verification; the driver does not grant
  capabilities, verify claims, approve actions, or mark completion.

Conclusion: the driver CANNOT authoritatively mutate Mission/Task/Capability/
Claim aggregates, append EventLedger entries, issue CapabilityGrants, create
VerificationResults/ClaimGuard decisions, or mark tasks/missions complete. The
boundary holds at both interface and call-path level.

## 4. Read-only proof (reconfirmed)

Fresh scenario on a temp repo:
- Target repository unchanged: `tree_digest(before) == tree_digest(after)` → TRUE.
- Artifact creation confined to staging: artifact path under `staging_root` → TRUE.
- Path traversal denied: `validate_artifact_candidate` rejects paths outside
  staging root (`_realpath_within`).
- Symlink escape denied: same `_realpath_within` resolves symlinks.
- Git mutation denied: driver performs no git operations; no `.git` created.
- Shell mutation denied: no subprocess/shell invocation in driver.
- Context minimized: `build_context_slice` + over-disclosure guard rejects
  authority objects (e.g. `GovernanceKernel`).
- Leases validated: `verify_lease` re-validates identity/scope/status/operations/
  path/budget/expiry before every external call.
- Observations untrusted: `validate_observation` requires `trust=untrusted` and
  matches `observedBy` to the verified driver id (impersonation defense).
- Receipts/artifacts independently validated: `validate_artifact_candidate`
  checks existence + SHA-256 digest; `validate_receipt_candidate` checks run id.
- Replay/restart did not re-execute: ledger-driven replay; optimistic-concurrency
  guard (`store.commit_command` with explicit stale `expected_version`) prevents
  re-application (test `test_stale_version_rejection`).

## 5. Verification commands (re-run, exact results)

| # | Command | Result |
|---|---------|--------|
| 1 | `pytest tests/capt_runtime/test_m0b_driver.py -q` | 51 passed |
| 2 | `pytest tests/capt_runtime -q` | 108 passed |
| 3 | `pytest -q` (full repo) | 469 passed, 44 skipped |
| 4 | `contracts/tools/generate.py` | OK (exit 0) |
| 5 | `contracts/tools/check_drift.py` | DRIFT CHECK: OK (11 files) |
| 6 | TS build (`tsc` in generated/typescript) | OK |
| 7 | `ruff check` (M0-B files) | All checks passed |
| 8 | `ruff format --check` (M0-B files) | 3 files would be reformatted (non-blocking) |
| 9 | `mypy` | NOT installed (no static type gate run) |
| 10 | `pytest -k "replay or checkpoint or restart"` | 10 passed |
| 11 | `pytest -k "unauthor or write or mutation or read_only"` | 5 passed |

Environment: macOS, Python 3.9.6, pytest 8.4.2, ruff present, node at
`~/.local/bin/node` (discovered via `node_discovery.py`). Full logs in
`/tmp/post-m0b-review/20260803T035838Z/phase2_*.txt`.

## 6. Verdict

M0-B is independently re-proven. The prior `M0_B_PROVEN` claim is substantiated
by current branch state, source inspection, and fresh test execution.
