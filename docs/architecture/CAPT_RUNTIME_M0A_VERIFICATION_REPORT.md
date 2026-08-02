# CAPT Runtime M0-A — Verification Report

Generated: 2026-08-02
Branch: feat/capt-runtime-m0a-contract-state-proof
Base: origin/docs/capt-runtime-architecture-spec
Runtime: macOS, python3.12 (pytest), node 20 (tsc)

Every command below was executed and its exit code recorded. No environment
failure is reported as a product-code failure, and no product-code failure is
explained away as an environment limitation.

## Commands and results

| # | Command | Purpose | Exit | Notes |
|---|---------|---------|------|-------|
| 1 | `python3 contracts/tools/generate.py` | Regenerate TS + Python bindings | 0 | 11 files written |
| 2 | `python3 contracts/tools/check_drift.py` | CI-equivalent drift gate | 0 | "DRIFT CHECK: OK (11 generated files match the schema source)" |
| 3 | `python3 -m pytest tests/capt_runtime -q` | M0-A conformance suite | 0 | 51 passed |
| 4 | `python3 -m pytest -q` | Full regression | 0 | 412 passed, 44 skipped (pre-existing skips) |
| 5 | `cd contracts/generated/typescript && npm run build` | Build TS bindings | 0 | tsc emit |
| 6 | `tsc -p tsconfig.json --noEmit` | TS strict type-check | 0 | clean |
| 7 | `node contracts/tools/ts_parity.mjs` | Cross-language fixture parity | 0 | 20 cases, 0 failures |
| 8 | `python3 - <<'PY' ... generate twice, diff -r ...` | Reproducibility proof | 0 | byte-identical |

## Invariant coverage (mission items 1–10)

| ID | Invariant | Test | Result |
|----|-----------|------|--------|
| I1 | One neutral schema source | test_schema_is_single_source | PASS |
| I2 | Reproducible TS/Python bindings | test_generation_reproducible, test_drift_check_clean | PASS |
| I3 | Authority planes distinct | test_plane_separation | PASS |
| I4 | Explicit aggregate ownership | test_ownership_disjoint | PASS |
| I5 | Transactional commit | test_atomic_commit | PASS |
| I6 | Event after valid transition | test_event_after_state | PASS |
| I7 | Scope-bound auditable capabilities | test_scope_*, test_revocation_*, test_max_use_* | PASS |
| I8 | Checkpoint/restart/replay | test_two_process_restart, test_checkpoint_replay_equals_full | PASS |
| I9 | Replay no duplicate state | test_duplicate_command_idempotent, test_duplicate_event_tolerance | PASS |
| I10 | No claim without evidence | this report; every claim cites a command+exit | PASS |

## Required test categories (all present)

- Contracts: schema validation, TS/Python parity, invalid discriminants, missing fields, version incompatibility, extension-boundary. [test_contracts.py]
- Authority: cognition≠grant, execution≠governance, verification≠execution, claimguard≠verification. [test_authority.py]
- Aggregates: exclusive ownership, optimistic concurrency, illegal transition, terminal immutability. [test_aggregates.py]
- Capabilities: grant/lease, scope mismatch, revocation, expiration, max-use, reservation/finalization, duplicate consumption. [test_capability.py]
- Ledger/outbox: event+state commit, no pre-commit dispatch, monotonic versions, stale write fails, hash chain. [test_ledger.py]
- Replay/checkpoint: full replay, checkpoint replay, duplicate tolerance, corruption rejected, schema rejected, deterministic equivalence. [test_replay.py]
- Claim integrity: unverified rejected, verified accepted, observation persists, completion requires evidence, claimguard cannot fabricate. [test_claim.py]

## Two-process restart proof

`test_two_process_restart` runs `build_scenario` (steps 1–6) in one process,
then invokes `tests/capt_runtime/restart_process.py` in a SEPARATE process that
opens the same on-disk SQLite store, performs a full replay and a
checkpoint+tail replay, and asserts the two reconstructed states are
byte-identical by content digest. Result: equivalent=True, full_digest ==
replay_digest.

## Environment limitations

- No distributed event infrastructure (Kafka/Redis) available; the ledger is a
  single-node SQLite store. This is within M0-A scope (no distributed infra).
- TypeScript `dist/` is build output, gitignored; the committed source
  (`src/`) is the binding artifact. Drift check excludes `dist/`.
- 44 pre-existing skipped tests in the wider suite are unrelated to M0-A
  (pre-existing skips on the base branch) and were not modified.

## Status

M0_A_PROVEN — all M0-A invariants and required tests pass with recorded
evidence. See M0-A decision document for the formal disposition.
