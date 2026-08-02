# ADR-0108 — Idempotency and replay semantics

**Status:** Accepted (M0-A)
**Date:** 2026-08-02
**Relates to:** spec §11, spec ADR-006, ledger Finding F, invariant 12

## Context

Spec §11 requires every consequential operation to carry an idempotency key, operation fingerprint, attempt number, replay policy, reservation identifier, and side-effect identity where available. Invariant 12: recovery must not blindly repeat an indeterminate side effect. Spec ADR-006: exactly-once external side effects cannot be guaranteed; CAPT targets **effectively-once**.

Baseline: `capt_solo/ctp/journal.py` has a partial idempotency concept — `_finalized_keys: Dict[str, str]` and `IdempotencyError` on reuse of a finalized key. But it *rejects* the duplicate rather than returning the original outcome, it has no operation fingerprint, and it has no replay policy. Rejection is the wrong behaviour for a retry: a client that did not receive the first response cannot distinguish "already done" from "failed".

## Decision

**Command-level idempotency with fingerprint conflict detection, and event-level replay idempotence, with no automatic retry of indeterminate operations.**

### Command idempotency

Every consequential command carries:

| Field | Purpose |
|---|---|
| `commandId` | unique per attempt (distinguishes retries from each other) |
| `idempotencyKey` | stable across retries of the *same logical operation* |
| `operationFingerprint` | `sha256(canonical_json(semantic parameters))` |
| `expectedVersion` | per aggregate (ADR-0106) |
| `replayPolicy` | `never` \| `safe` \| `verify-before-retry` |
| `attempt` | integer, informational |

Handling, inside the transaction (ADR-0104 step 1):

1. Look up `idempotencyKey` in `command_log`.
2. **Not found** → execute; record `(key, fingerprint, resulting event ids, outcome)`.
3. **Found, fingerprint matches** → return the recorded outcome. Do **not** re-execute, do **not** append events, do **not** enqueue outbox rows. State transition count stays at 1.
4. **Found, fingerprint differs** → `IdempotencyConflictError`. Same key, different meaning is a caller bug and must never silently execute.

The fingerprint check is what makes this safe. A key alone cannot distinguish "retry of the same operation" from "different operation, key accidentally reused".

### Event replay idempotence

Replay applies ledger events to a fresh aggregate in `globalSequence` order. `Aggregate.apply()` is idempotent with respect to `(streamId, streamVersion)`: applying an event whose `streamVersion <= self.version` is a no-op. A duplicated event in the ledger (which the primary key should prevent, but which a corrupted import could introduce) cannot double-apply.

### Replay policies

| Policy | Semantics |
|---|---|
| `never` | Never re-execute automatically. Human or explicit reconciliation only. |
| `safe` | The operation is provably idempotent externally (pure read, or write with a natural idempotency key). May re-execute. |
| `verify-before-retry` | Must observe external state first, then decide. Default for anything consequential. |

**An `indeterminate` reservation (ADR-0107) is never automatically retried under any policy.** It requires an explicit `reconcile()` with external evidence. This is enforced in code and tested: attempting to retry an `awaiting_reconciliation` reservation raises `ReconciliationRequiredError`.

### Effectively-once, stated precisely

CAPT claims: *for a given `idempotencyKey`, at most one committed set of CAPT state transitions exists.* This is provable and proven by test.

CAPT does **not** claim: exactly-once external side effects. Not achievable without transactional participation from the external system. Any documentation asserting exactly-once external effects is a false claim under ADR-0110.

### Determinism of replay

Replay must produce byte-identical state. Therefore aggregates: never call `time.time()`, never call `uuid4()`, never read the environment or filesystem, and never iterate an unordered set during state computation. All non-determinism enters through the command, is captured in the event, and is replayed from the event. A conformance test greps the aggregate module for `time.time`, `datetime.now`, `uuid4`, and `random.` and fails if found.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Reject duplicate keys (current CTP behaviour) | A client that lost the response cannot recover; it cannot distinguish "already succeeded" from "failed". Returning the recorded outcome is strictly safer. Rejected. |
| Key without fingerprint | Cannot detect accidental key reuse for a different operation; would silently return the wrong outcome. Rejected. |
| Fingerprint without key | Two legitimately identical operations (e.g. "grant read on file X" twice, intentionally) would be collapsed. Key expresses caller intent; fingerprint validates it. Both needed. |
| Automatic retry of indeterminate | Violates invariant 12; can duplicate an external effect. Rejected. |
| Dedupe at the event layer only | Too late: the command has already produced side effects by then. Rejected. |
| Time-based key expiry | A retry after expiry would re-execute. No TTL in M0-A; growth is bounded by mission count and is a known future concern. |

## Consequences

**Positive**
- Retry is safe and returns the original outcome.
- Key misuse is detected, not silently accepted.
- Replay is deterministic and testable by state comparison.
- Indeterminate effects cannot be silently repeated.

**Negative / costs**
- `command_log` grows unbounded in M0-A. Accepted; retention is a future concern with a real design cost (expiry reintroduces the retry-after-expiry hazard).
- Callers must generate stable keys — a hard requirement, documented in `contracts/invariants/idempotency.md`.
- The no-nondeterminism rule constrains aggregate implementation style.

## Reversal conditions

1. `command_log` growth becomes a storage problem → design a retention policy that provably cannot re-open the retry window (likely: retain keys for the lifetime of the mission plus a fixed margin).
2. A class of operations is proven idempotent at the external boundary with durable receipts → those may move to `safe`.

## Evidence from the current repository

- `capt_solo/ctp/journal.py:62` — `self._finalized_keys: Dict[str, str]`.
- `capt_solo/ctp/journal.py:138-139` — raises `IdempotencyError` on reuse rather than returning the prior outcome.
- `capt_solo/core/errors.py` — `IdempotencyError` docstring says "reused with conflicting payloads", but the implementation never compares payloads; there is no fingerprint. Documentation/implementation gap, recorded as evidence for the fingerprint requirement.
- No `operation_fingerprint`, `replay_policy`, or `attempt` field exists anywhere in the tree.
