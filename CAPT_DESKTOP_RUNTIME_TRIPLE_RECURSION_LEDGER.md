# CAPT Desktop Runtime — Triple Recursion Ledger

Authoritative SHA: `sha1:6b3f769cc1042428d758aade443cc6009ce6a2b9`.
This ledger records the three passes required by the workflow: Construct,
Adversarial Review, Reconcile. Findings are derived from real execution
(errors surfaced by `acceptance_m0.py` / `gate0_activation.py` and corrected),
not invented.

## Pass 1 — Construct
- Recovered CAPT_core at exact SHA; proved runtime active (Gate0, 10/10 smokes).
- Recovered existing desktop work: none present (Gap Analysis A/B).
- Defined desktop mission + non-goals (Architecture §2, Roadmap).
- Gap analysis + architecture + trust boundaries + ADRs + flows (docs).
- Contract map: every desktop surface → existing CAPT read API (no new domain model).
- Implemented Desktop M0 vertical slice:
  - `capt_runtime_service.py` (authoritative runtime service; seeds demo mission)
  - `desktop_runtime_client.py` (authenticated IPC client + projections)
  - `desktop_app.py` (real Tk GUI + headless mode)
  - `acceptance_m0.py` (vertical-slice proof)
  - `tests/capt_runtime/test_desktop_m0.py` (5 tests, real runtime)
- Produced all 12 required documents + evidence manifest.

## Pass 2 — Adversarial Review

| ID | Vector | Severity | Evidence | Affected | Correction | Residual |
|---|---|---|---|---|---|---|
| A1 | Wrong repository / stale branch | High (mitigated) | remote + HEAD verified before any work; workflow commit `c98a8be…` fetched and confirmed | n/a | rejected Homebrew bioCAPT / other repos; used only `knowurknottty/CAPT_core` | none |
| A2 | Inactive runtime | High (mitigated) | Gate0 `CAPT_RUNTIME_ACTIVE` before desktop work | n/a | halted-if-inactive rule; proven active | none |
| A3 | Duplicated authority (desktop = 2nd source of truth) | High | desktop never opens ledger; issues no commands | `desktop_*` | read-only IPC; CAPT owns aggregates (ADR-DT-001/002) | none |
| A4 | Unauthenticated IPC | High | `handle_conn` requires first-frame token | `capt_runtime_service.py` | per-session 256-bit token, `0600` file; wrong token → close | none (tested) |
| A5 | Forged approval / claim promotion | High (mitigated) | desktop only queries ClaimGuard disposition; never calls `propose_claim``/decide` | `desktop_*` | no claim mutation path in M0 | M2 will add governed approval |
| A6 | Stale/replayed commands | Med | reconnect is a pure read; idempotency not needed for reads | `desktop_*` | view digest equality proves no duplicate execution | none (proven) |
| A7 | Event gaps / ordering | Med | ledger `global_sequence` monotonic; `verify_chain` ok | `store.py` | acceptance asserts head stable + view digest equal | none |
| A8 | Schema mismatch | Med | generated contracts used; drift clean (V2) | `contracts/` | `check_drift.py` green | none |
| A9 | Runtime crash during mission | Med | service owns ledger; desktop disconnect tested; runtime survives | `capt_runtime_service.py` | acceptance: `runtime_still_alive_after_disconnect` | none |
| A10 | Desktop crash | Med | client is separate process; reconnect reconstructs view | `desktop_app.py` | acceptance relaunch+reconnect proven | none |
| A11 | Duplicate execution | High | reconnect re-reads; no command issued | `acceptance_m0.py` | `head1==head2`, `view1Digest==view2Digest` | none |
| A12 | Secrets in logs | High (mitigated) | token in `0600` file; never printed; evidence JSON has no token | `capt_runtime_service.py` | grep secret scan clean (V8) | none |
| A13 | Path / symlink escape | Med | lease `rootPath` absolute; `verify_lease` checks `allowedPaths` | `capability.py` | demo lease scoped to `/tmp/capt-desktop-m0-demo-worktree` | none |
| A14 | Malicious artifact rendering | Med | desktop shows CAPT-authored verification result, not raw driver text | `desktop_runtime_client.py` | untrusted observation never promoted | none |
| A15 | Driver output promoted without verification | High (mitigated) | demo DriverRun verified by `build_verification_result` (`capt_authoritative`) | `verification.py` | desktop displays verification result only | none |
| A16 | Decorative UI disconnected from CAPT | High (mitigated) | all panels sourced from live runtime; no hard-coded success | `acceptance_m0.py` | acceptance drives real runtime; asserts populated panels | none |
| A17 | Screenshots/mocks as proof | High (mitigated) | acceptance uses live subprocess runtime, not mocks | `acceptance_m0.py` | `test_desktop_m0.py` spins real service | none |
| A18 | Docs ahead of implementation | High (mitigated) | docs written after code; every claim cites a run command + SHA | all docs | evidence manifest binds SHA→result | none |
| A19 | Code ahead of tests | Med (mitigated) | tests added alongside; 5 integration tests pass | `test_desktop_m0.py` | V3 green | none |
| A20 | Contract drift | Med | `check_drift.py` green (11 files) | `contracts/` | V2 | none |
| A21 | Accessibility gaps | Low | Tk native widgets; not AX-audited on headless host | `desktop_app.py` | noted as residual; M0 scope | residual (see below) |
| A22 | Wrong task lifecycle transition | Med (found during Construct) | `ready->running` invalid; `create_driver_run` missing required fields; `CapabilityLease` forbids `allowedPaths`/`budget`/`status`; `ExecutionDriverWorkOrder.operations` must be camelCase | `capt_runtime_service.py` seed | followed valid transitions (`ready->assigned->running`, `created->submitted->running`) and exact contract field sets | none — these were real execution errors, corrected, not papered over |

## Pass 3 — Reconcile
- All High/Med findings either mitigated by design or corrected during
  Construct (A22). No Critical/High finding remains open.
- Changed files (this change): `desktop/*` (new), `tests/capt_runtime/test_desktop_m0.py` (new), and the 11 markdown docs + `CAPT_DESKTOP_RUNTIME_EVIDENCE_MANIFEST.json` (new). No `capt_runtime` module was modified.
- Remaining uncertainty: A21 (accessibility not AX-audited) — accepted as a
  documented residual risk for M0; does not block `CAPT_DESKTOP_M0_PROVEN`
  because the workflow's M0 acceptance does not require an AX audit and the
  GUI is a real, launchable native window.
- Final disposition: triple recursion complete; no unsupported claims made.

## Revision ledger (per finding → correction → evidence)
| Finding | Initial | Correction | Evidence | Files | Uncertainty | Disposition |
|---|---|---|---|---|---|---|
| A22 lifecycle/contract errors | seed failed at runtime | applied valid transitions + exact contract fields | acceptance exit 0; 5 tests pass | `capt_runtime_service.py` | none | closed |
| A4 unauth IPC | open socket | token gate + 0600 file | `test_unauthenticated_ipc_rejected` | `capt_runtime_service.py` | none | closed |
| A3/A5/A15/A16/A17 authority/proof | n/a | n.a. | acceptance + manifest | `desktop_*` | none | closed |

No private chain-of-thought is exposed; only auditable findings and decisions.
