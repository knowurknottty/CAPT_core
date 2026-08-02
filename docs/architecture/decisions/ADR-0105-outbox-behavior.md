# ADR-0105 — Outbox behavior

**Status:** Accepted (M0-A)
**Date:** 2026-08-02
**Relates to:** spec §5, invariant 10, spec §4.4, workflow Gate 3

## Context

Spec invariant 10 and §5 require that authoritative events be dispatched only after the state transition commits. The baseline established that no outbox exists (`grep -rni outbox` → 0 hits) and that the existing `KHSB` bus dispatches **synchronously inside `publish()`** (`capt_solo/khsb/bus.py:165`) with no relationship to any commit. Using KHSB for authoritative events would publish before — or without — a commit.

The failure mode being designed against: a subscriber observes `CapabilityGranted`, acts on it, and the granting transaction then rolls back. The subscriber has acted on authority that never existed.

## Decision

**Transactional outbox with at-least-once post-commit dispatch and subscriber-side idempotent handling.**

1. **Enqueue inside the transaction.** `INSERT INTO outbox(event_id, status='pending', attempts=0)` occurs in the same transaction as the event-ledger append and the aggregate update (ADR-0104 step 8). If the transaction rolls back, the outbox row disappears with it — so an uncommitted event can never be dispatched.

2. **Dispatch strictly after commit.** `OutboxDispatcher.dispatch_pending()` runs only outside a write transaction. It reads `pending` rows ordered by `global_sequence` (never by timestamp — ADR-0106), invokes subscribers, and marks `dispatched`.

3. **Enforcement, not convention.** `RuntimeStore` sets an internal `_in_transaction` flag. `OutboxDispatcher.dispatch_pending()` raises `OutboxDispatchError` if called while that flag is set. A conformance test drives a transaction that raises mid-way and asserts (a) zero subscriber invocations, (b) zero outbox rows, (c) zero ledger rows.

4. **At-least-once, never at-most-once.** A crash between subscriber invocation and the `dispatched` mark redelivers on restart. This is deliberate: losing a governance event is worse than repeating one. CAPT therefore does **not** claim exactly-once delivery.

5. **Duplicate suppression is the subscriber's contract.** Every subscriber receives the event's `eventId`. The dispatcher maintains a delivered-set keyed by `(subscriber_name, event_id)` persisted in the outbox table's `delivered_to` column, so a retry does not re-invoke a subscriber that already succeeded. A conformance test crashes the dispatcher between invocation and mark, restarts, and asserts the subscriber's *effect count* is 1 while the *delivery attempt count* is 2.

6. **Failure isolation.** A raising subscriber does not block other subscribers or other events. The row's `attempts` increments and `last_error` is recorded; the row remains `pending`. There is no automatic dead-letter in M0-A; `attempts` is observable and a stuck row is a visible operational fact rather than a silently dropped event.

7. **Ordering guarantee.** Per-stream ordering is guaranteed (dispatch follows `global_sequence`, and per-stream `stream_version` is monotonic by primary key). Cross-stream *causal* ordering is guaranteed only through `causationId`; the dispatcher does not attempt cross-stream causal sorting.

8. **KHSB stays ephemeral.** The existing bus is explicitly classified as the spec's `EphemeralSignalBus` (§4.4). A conformance test asserts the runtime package does not import `capt_solo.khsb`.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Publish inside the transaction | Subscribers act on state that may roll back. Directly violates invariant 10. This is the specific bug the outbox exists to prevent. |
| Publish immediately after `COMMIT` with no outbox row | A crash between COMMIT and publish loses the event permanently, with no record that dispatch was owed. Rejected. |
| Two-phase commit with subscribers | Distributed-commit complexity before constitutional invariants are proven; contradicts spec §3.2. Rejected. |
| Exactly-once delivery | Not achievable across a process boundary without subscriber-side transactional participation. Claiming it would be a false claim — which M0-A exists to prevent. Rejected explicitly; see spec ADR-006. |
| Reuse KHSB for authoritative events | Synchronous, in-process, no durability, no commit relationship (`bus.py:165`). Rejected; retained for ephemeral signals only. |
| Dead-letter queue in M0-A | Additional state machine with no proof requirement attached. Deferred; `attempts`/`last_error` give visibility without the machinery. |

## Consequences

**Positive**
- An uncommitted event is structurally undispatchable.
- Redelivery after crash is guaranteed, so governance events cannot be silently lost.
- Subscriber effect-idempotence is testable and tested.

**Negative / costs**
- Dispatch is not instantaneous; it happens when `dispatch_pending()` is called (explicitly, in M0-A — no background thread, keeping the proof deterministic).
- Subscribers must be idempotent. This is a contract obligation, documented in `contracts/invariants/`.
- At-least-once means duplicates are normal, not exceptional; downstream design must assume them.

## Reversal conditions

1. A subscriber genuinely cannot be made idempotent → requires either a distributed transaction (new ADR) or a redesign of that subscriber.
2. Dispatch latency becomes a product requirement → add a background dispatcher thread, which requires revisiting the determinism guarantees of the M0-A proof.
3. Stuck outbox rows become an operational problem → add a dead-letter state with a new ADR.

## Evidence from the current repository

- `capt_solo/khsb/bus.py:80-84` — `publish()` calls `_dispatch()` synchronously; no commit relationship, no durability.
- `capt_solo/khsb/bus.py:131-136` — `ack()`/`is_acked()` are in-memory only; a restart loses acknowledgement state.
- `grep -rni outbox` across the tree → 0 results before this change.
- `capt_solo/ctp/journal.py` — durable, but a journal of transaction *intent*, with no subscriber dispatch concept at all.
