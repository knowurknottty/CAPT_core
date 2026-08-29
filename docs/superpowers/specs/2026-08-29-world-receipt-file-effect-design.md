# THE WORLD RECEIPT — File Effect Vertical Slice

**Status:** implementation candidate, 2026-08-29

**Goal:** move durable truth about consequential execution toward the boundary where reality changes, without creating a second CAPT authority ledger or claiming atomicity the target cannot supply.

## Constitutional invariant

No irreversible effect is allowed to be called crash-safe unless its `WorldReceipt` is committed in the same real atomic domain as the effect. If a substrate cannot provide that property, the effect must instead be staged behind a real reversal/escrow mechanism or refused.

RuntimeService/EventStore remain authoritative for CAPT intent, authority, lifecycle, and settlement. A WorldReceipt is independent target-local evidence about the changed world. Neither substitutes for the other.

## This slice

`file.write` and `file.patch` are the first receipt-bearing operations. Ordinary filesystem files cannot atomically commit both arbitrary target bytes and an independent receipt sidecar. Therefore this implementation explicitly classifies them as:

- `coordinationMode = staged`
- `rollbackStrategy = escrow`
- `reconciliationStrategy = target_receipt`

It does **not** classify plain file + sidecar as `ATOMIC_WITNESSED`.

Before dispatch, ToolBroker persists a closed `EffectIntent` containing principal, operation, payload digest, basis version, grant/lease, target identity, lease-bound expiry, idempotency identity, coordination mode, rollback strategy, reversal handle, receipt specification, and intent digest.

## File staging protocol

For one mutation attempt, the adapter derives target-local, idempotency-stable hidden paths for:

1. a reversal preimage escrow;
2. a unique immutable WorldReceipt;
3. a per-target CAPT advisory writer lock.

A cooperating CAPT writer holds the target lock across:

1. basis-version revalidation;
2. reversal-preimage persistence and fsync;
3. target atomic replacement;
4. post-state digest validation;
5. WorldReceipt persistence and fsync;
6. target/receipt/reversal verification.

The advisory lock serializes CAPT writers only. It deliberately does not claim arbitrary external filesystem processes participate in CAPT's coordination domain.

## WorldReceipt proof

The file receipt binds:

- deterministic receipt ID;
- EffectIntent ID and digest;
- exact target identity;
- receipt kind and unique locator;
- observed target-state digest;
- `commitState = committed`;
- reversal handle.

Receipt verification requires schema validity, deterministic receipt identity, exact intent binding, exact locator binding, ordinary non-symlink target/proof files, current target digest agreement, and a valid reversal escrow matching the pre-effect basis.

Receipt kinds are closed to what is implemented. This slice advertises only `file_sidecar`; Git/API/database/MCP receipt kinds must not be added until a real target-side proof protocol exists for each one.

## Crash semantics

| Crash boundary | Recovery meaning |
| --- | --- |
| before EffectIntent persistence | no admitted effect exists |
| after EffectIntent, before capability reservation | prepared and safely resumable under the same idempotency identity |
| after capability reservation, before admitted transition | orphan pre-dispatch reservation is closed as failed; no use consumed |
| after admitted, before target mutation | no blind redispatch after crossed dispatch boundary |
| after reversal escrow, before target mutation | target remains at basis; escrow is harmless |
| after target mutation, before receipt | `indeterminate`; verified escrow proves the stage remains reversible, never success |
| after receipt, before broker settlement | target receipt is read-only reconciled; matching proof may settle success without redispatch |
| malformed/tampered receipt | `indeterminate / reconciliation_required` |
| deregistered tool during recovery | that execution becomes indeterminate; recovery continues for all other executions |

Missing proof never becomes success. A verified reversal handle is evidence of reversibility, not evidence that the intended commit happened.

## Pre-dispatch settlement atomicity

A denied or expired execution that already owns a capability reservation must not close that reservation in one command and terminate `ToolExecution` in another. Doing so creates a crash window where capability state says the reservation is finalized while execution state remains resumable.

`RuntimeService.settle_predispatch_tool_execution` therefore builds both `CapabilityUseFinalized` and `ToolExecutionTerminated` appends and submits them together through `EventStore.commit_command`. They share one SQLite transaction, one command idempotency record, and adjacent ledger positions. The method is restricted to `prepared`/`admitted`, `dispatchBoundary = not_started`, failed/no-effect consumption, and denied/failed results.

Fault injection covers three transaction boundaries: failure before commit leaves both aggregates unchanged; failure after the capability append is staged but before the ToolExecution append validates rolls the whole SQLite transaction back; failure after commit during outbox delivery leaves both aggregate snapshots durable and retry returns the terminal projection without adapter redispatch.

## Idempotency and replay

The idempotency key deterministically binds ToolExecution, EffectIntent, reservation identity, receipt location, and reversal location. Exact settled replay returns the already-recorded ToolResult without invoking the adapter again. `replayPolicy = never` prohibits automatic **re-execution**; it does not prohibit returning an already-settled idempotent result.

## Authority and expiry

EffectIntent expiry comes from the authoritative capability lease `validUntil`. Missing/mismatched lease state fails closed; production does not fabricate a fallback lifetime. Timestamp comparisons parse RFC3339 instants and normalize offsets before comparison.

The live capability lease is revalidated immediately before consequential dispatch. A revocation or expiry before dispatch cannot be overridden by an already-persisted EffectIntent.

## Explicit non-claims

This slice does not claim:

- global or distributed atomicity;
- arbitrary external writers honor the CAPT file lock;
- a completed receipt proves the target has never changed afterward;
- receipt possession proves human consent or voluntariness;
- file reversal is presently exposed as an operator-authorized command;
- terminal, code-execution, browser, Git, API, database, or MCP mutations are WorldReceipt-capable yet;
- the full Round-10 `EffectManifest`, `AuthorityEnvelope`, `UNMAPPED_EFFECT`, `NULL_ACTION`, and `NO_ATOMIC_DOMAIN` policy surface is complete.

`reverse_world_effect` is currently an adapter-internal primitive used to prove the staged file effect is physically reversible. Exposing reversal requires its own governed operation, lease, effect declaration, and receipt semantics.

## Acceptance gates

The implementation must keep these gates green:

- generated Python/TypeScript contracts match source schema;
- TypeScript parity fixtures pass;
- full Python runtime suite passes;
- power cut after target mutation but before receipt leaves no false success and preserves verified reversal escrow;
- crash after receipt but before settlement reconciles without redispatch;
- receipt tampering, receipt-ID forgery, basis drift, target mismatch, fake distributed atomicity, and expired intent all fail closed;
- crash after capability reservation but before ToolExecution admission closes the orphan reservation without consuming a use;
- pre-dispatch capability finalization + ToolExecution termination is one EventStore transaction, with pre-commit, mid-transaction, and post-commit fault injection proving rollback/replay semantics;
- one missing tool cannot abort reconciliation of other stranded executions;
- fresh native macOS build/signature/launch verification passes.

## Next protocol tranche

The next implementation tranche lifts the canonical Round-10 policy layer above this execution substrate: typed `EffectManifest`, effect-bound `AuthorityEnvelope`, `UNMAPPED_EFFECT`, reversible/escrow admission, `CONSENT_NOT_MACHINE_PROVABLE`, mandatory safe `NULL_ACTION`, `NO_ATOMIC_DOMAIN`, and runtime containment asserting actual effects remain a subset of the authorized manifest.
