# ADR-0111 — M0-A exclusions and deferred work

**Status:** Accepted (M0-A)
**Date:** 2026-08-02
**Relates to:** spec §19, §21, workflow §5, mission scope guard

## Context

M0-A is the *contract and state-transition proof*. The dominant delivery risk is scope creep: implementing M0-B or M0-C capability while calling it M0-A, then claiming a proof that was never gated. An explicit exclusion list makes over-delivery a detectable ADR violation rather than a judgement call.

## Decision

**The following are explicitly OUT of M0-A. Each is listed with the specific mechanism preventing it.**

| # | Excluded | Prevention mechanism (testable) |
|---|---|---|
| 1 | Real external ExecutionDriver integration | No `DriverHost`, no `subprocess`, no network module in `capt_runtime`. Conformance test greps for `subprocess`, `socket`, `http`, `requests`, `urllib` in `capt_runtime/` and fails on any hit. |
| 2 | Repository writes through a driver | Same as 1. No filesystem write outside the runtime store path and checkpoint directory. |
| 3 | M0-B (read-only driver proof) | `DriverRunAggregate` is a state model only; no `submit`/`inspect`/`cancel`/`resume`/`reconcile` transport. |
| 4 | M0-C (governed isolated write) | No worktree, no git operation, no diff capture in `capt_runtime`. |
| 5 | Distributed event infrastructure | Single SQLite file (ADR-0104). Grep test forbids network imports. |
| 6 | Kafka / Redis Streams | Zero third-party runtime dependencies; `pyproject.toml` `dependencies` stays absent. Test asserts it. |
| 7 | Multi-agent orchestration | No scheduler, no agent registry, no work distribution. |
| 8 | Generalized Knowledge Bubble execution | `capt_solo/foundry/bubble.py` untouched; `capt_runtime` does not import `capt_solo`. Test asserts the non-import. |
| 9 | Full scheduler optimization | `TaskAggregate` exposes transitions only; no scheduling policy, no priority, no queue. |
| 10 | Model routing | No model, LLM, or provider reference in `capt_runtime`. |
| 11 | Community plugin ecosystems | No plugin loading in `capt_runtime`. |
| 12 | Real verification strategy execution | `VerificationResult` is a contract; no verifier is executed in M0-A. |
| 13 | Human approval UI/flow | `HumanApprovalRequest`/`Decision` are out of the M0-A contract set (spec lists them under Gate 1's broader set; the mission's M0-A contract list omits them). Deferred to M0-B. |
| 14 | Per-event hash chaining | Deferred per ledger Finding K; ADR-0109 uses per-event digests + manifest fold instead. |
| 15 | Checkpoint signing / key management | No threat model in M0-A. Manifest digest field is signature-ready. |
| 16 | Context disclosure controls (spec §16) | A driver-boundary concern; no driver in M0-A. Deferred to M0-B. |
| 17 | Postgres backend | ADR-0104 defers. |
| 18 | Command-log retention/expiry | ADR-0108 records the unbounded-growth trade explicitly. |
| 19 | Dead-letter queue | ADR-0105 defers; `attempts`/`last_error` give visibility. |
| 20 | Modification of any existing `capt_solo` code | Baseline §6 do-not-touch list. `git diff --stat` against the base commit must show zero changes under `capt_solo/`, `tests/` (pre-existing modules), `capt_cli.py`, `verify_runtime.py`, or the shell scripts. Verified in the verification report. |

### Isolation rule

`capt_runtime` **must not import `capt_solo`**, and `capt_solo` **must not import `capt_runtime`**. Both directions are asserted by a conformance test. Rationale: M0-A must be provable independently, and the existing package must remain unaffected so its 361-test baseline stays a valid control.

### What M0-A *does* deliver

1. Canonical JSON Schema contract source, versioned from the first commit.
2. Reproducible generated TypeScript and Python bindings with drift detection.
3. Five aggregates with enforced exclusive ownership.
4. Transactional store: aggregate state + event ledger + outbox + command log + checkpoints in one transaction.
5. Post-commit outbox dispatch.
6. Capability grant → lease → reservation → consumption → revocation lifecycle with effect-boundary revalidation.
7. Idempotency with fingerprint conflict detection; deterministic replay.
8. Checkpoint manifest with integrity digest; checkpoint+tail ≡ full replay.
9. The eight-step runtime path: MissionCreated → PolicyEvaluated → CapabilityGranted → CapabilityLeaseActivated → TaskTransitioned → CheckpointCreated → ProcessRestarted → StateReplayed, with the restart being a **real separate OS process**.
10. Conformance tests for contracts, authority, aggregates, capabilities, ledger/outbox, replay/checkpoints, and claim integrity.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Implement M0-A and M0-B together | Failures become hard to localize (ledger Finding P). Gated proofs exist precisely to prevent this. Rejected. |
| Simulate a driver in-process to "prove" the boundary | A simulated driver proves nothing about an untrusted external process and would invite a false claim of driver capability. Rejected — the boundary is proven by *type structure and negative tests*, not by a fake. |
| Skip driver contracts entirely in M0-A | ADR-0110: retrofitting a trust boundary after code paths exist is how boundaries get bypassed. Contracts now, integration later. |
| Modify `capt_solo` to share the new store | Destroys the independent baseline and violates ADR-0103. Rejected. |
| Add ruff/mypy to satisfy "lint and type check" | Introduces tooling the repository has never had, producing a large unrelated diff and a first-run failure wave across 16,498 pre-existing lines. Rejected; substitutes documented in the verification report as an environment limitation. |

## Consequences

**Positive**
- Over-delivery is detectable, not a matter of opinion.
- The existing 361-test baseline remains a valid control.
- Each exclusion has a mechanism, so scope discipline does not depend on memory.

**Negative / costs**
- `capt_runtime` cannot reuse `capt_solo` utilities (config paths, error base classes) and must duplicate a small amount. Accepted: independence is worth more than ~50 lines.
- Two packages to maintain until a deliberate convergence ADR.

## Reversal conditions

1. M0-A passes and M0-B begins → items 3, 13, 16 are lifted by the M0-B ADR set, not by this one.
2. Convergence of `capt_runtime` and `capt_solo` requires an explicit ADR with a migration plan and re-verification of both baselines.

## Evidence from the current repository

- Baseline §6 do-not-touch list.
- Baseline §1: `361 passed, 44 skipped` — the control that must remain intact.
- `pyproject.toml`: no `dependencies` key — the zero-dependency property that exclusions 6 and 20 preserve.
- Spec §21 "Deferred work" and the mission scope guard, which this ADR operationalizes into testable mechanisms.
