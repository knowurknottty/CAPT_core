# CAPT Runtime M0-A — Decision Document

## Disposition

**M0_A_PROVEN**

All ten M0-A invariants and all required test categories pass with recorded
evidence (see CAPT_RUNTIME_M0A_VERIFICATION_REPORT.md). The proof was produced
by real execution, not by assertion.

## What was built

1. Repository forensic baseline (Gate 0) — `CAPT_RUNTIME_BASELINE_MAP.md`.
2. Eleven ADRs (0101–0111) — `docs/architecture/decisions/`.
3. Canonical JSON Schema contract source (12 files) — `contracts/schema/`.
4. Deterministic generator emitting TypeScript + Python bindings — `contracts/tools/`, `contracts/generated/`.
5. Contract fixtures (cross-language parity) — `contracts/fixtures/`.
6. Runtime: transactional store, five aggregates, capability lifecycle, checkpoint, replay — `capt_runtime/`.
7. Conformance suite (51 tests) + two-process restart proof.
8. CI drift/build/parity workflow — `.github/workflows/m0a-contract-runtime.yml`.
9. Triple-recursion ledger + verification report.

## Proof sequence demonstrated

MissionCreated → PolicyEvaluated → CapabilityGranted → CapabilityLeaseActivated
→ TaskTransitioned → CheckpointCreated → ProcessRestarted → StateReplayed

The restart and replay steps execute in a separate OS process against the same
on-disk store; full replay and checkpoint+tail replay produce byte-identical
state digests.

## Authority separation (invariant 3)

Governance, cognition, execution, verification, and claim authority are
enforced by a deny-by-default act/actor-kind matrix (`authority.py`). A
cognition actor cannot issue a CapabilityGrant; execution cannot evaluate
policy; verification cannot mutate execution artifacts; ClaimGuard cannot
fabricate verification evidence.

## Aggregate ownership (invariant 4)

Mission, Task, Capability, DriverRun, and Claim each own a disjoint set of
state fields (`OWNED_FIELDS`), qualified to avoid naming coincidence. The
disjointness test asserts zero overlap. Cross-aggregate changes occur only
through explicit application services (`services.py`), making coupling
enumerable.

## Transactional integrity (invariants 5, 6, 10)

A command commits aggregate snapshot, durable event, outbox row, and idempotency
record in ONE SQLite transaction. The event is validated against the generated
contract and hash-chained before it becomes durable. Dispatch to subscribers
runs strictly after commit returns.

## Capability lifecycle (invariant 7)

Grant, lease, reservation, finalization, revocation, expiration, max-use, and
audit are all modeled and tested. A lease lives inside its grant aggregate so a
revocation invalidates both atomically. The lease is revalidated immediately
before any consequential side effect. Indeterminate outcomes leave the
reservation awaiting reconciliation and do NOT free the use.

## Replay (invariants 8, 9)

Reducers are pure and idempotent at the (stream, version) level: a duplicate or
overlapping event is skipped, never double-counted. Checkpoint replay trusts a
verified checkpoint then folds only the tail; it equals full replay by content
digest.

## What is explicitly NOT claimed

- Exactly-once external effects (spec invariant 12). The proof covers
  effectively-once via idempotency, durable receipts, and reconciliation.
- Real external ExecutionDriver integration (out of scope for M0-A).
- M0-B, M0-C, distributed event infrastructure, multi-agent orchestration
  (scope guard, ADR-0111).

## Recommendation

Promote `feat/capt-runtime-m0a-contract-state-proof` for review and merge to
`docs/capt-runtime-architecture-spec`. Proceed to M0-B only after this gate is
accepted.

## Files changed (summary)

- `docs/architecture/CAPT_RUNTIME_BASELINE_MAP.md` (new)
- `docs/architecture/decisions/ADR-0101..0111*.md` (new)
- `contracts/schema/*.schema.json` (new, 12 files)
- `contracts/tools/*` (new generator, emitters, drift, parity)
- `contracts/generated/{typescript,python}/*` (generated, committed)
- `contracts/fixtures/*.json` (new)
- `capt_runtime/*` (new runtime package)
- `tests/capt_runtime/*` (new conformance suite)
- `.github/workflows/m0a-contract-runtime.yml` (new)
- `docs/architecture/CAPT_RUNTIME_M0A_*.md` (new ledger + report)

## Verification commands (re-run any time)

```
python3 contracts/tools/generate.py
python3 contracts/tools/check_drift.py
python3 -m pytest tests/capt_runtime -q
python3 -m pytest -q
cd contracts/generated/typescript && npm run build && tsc -p tsconfig.json --noEmit
node contracts/tools/ts_parity.mjs
```
