# ADR-0106 — Event ordering and optimistic concurrency

**Status:** Accepted (M0-A)
**Date:** 2026-08-02
**Relates to:** spec §13, ledger Finding J, workflow Gate 3

## Context

Ledger Finding J: event ordering relied too heavily on timestamps, so concurrent tasks could race or replay out of order. Spec §13 requires stream identifier, aggregate version, schema version, correlation identifier, causation identifier, local sequence, and optional global sequence — and states explicitly that *timestamps are descriptive and are not used as the sole ordering mechanism*.

Baseline evidence that the existing code has exactly this defect:

- `capt_solo/ctp/journal.py` orders purely by file append order and stamps `time.time()`; `_load()` replay depends on line order alone.
- `capt_solo/foundry/governance.py:136` — `ORDER BY timestamp DESC` on the audit trail. Two governance actions in the same clock tick have undefined order.
- `capt_solo/khsb/bus.py` — messages carry `ts` (float) with no sequence.
- No `expected_version` concept exists anywhere in the tree.

`time.time()` on macOS is not guaranteed monotonic across NTP adjustments and has sub-microsecond collision risk under load; two events *can* share a timestamp.

## Decision

**Ordering is by integer sequence; concurrency is controlled by explicit aggregate versions. Timestamps are descriptive metadata only.**

### Ordering

1. **Per-stream:** `streamVersion`, a 1-based integer, strictly incrementing by exactly 1 per event on that stream. Enforced by `PRIMARY KEY(stream_id, stream_version)` in `event_ledger` — a gap or duplicate is a database constraint violation.
2. **Global:** `globalSequence`, a strictly increasing integer assigned inside the write transaction from a single counter row. Used for cross-stream replay order and outbox dispatch order.
3. **Causal:** `causationId` (the event/command that directly caused this event) and `correlationId` (the originating mission-scoped workflow id). These express causality where sequence numbers cannot.
4. **`occurredAt`** is an RFC 3339 UTC timestamp present on every event. It is **never** used for ordering, comparison, or conflict resolution. A conformance test greps the runtime package for `ORDER BY occurred_at` / sorts on the timestamp field and fails if found.

### Optimistic concurrency

1. Every consequential command carries `expectedVersion: int` for each aggregate it mutates.
2. The store loads the aggregate row and compares. Mismatch → `ConcurrencyConflictError` carrying `(stream_id, expected, actual)`. The transaction rolls back; no event, no state change, no outbox row.
3. `expectedVersion = 0` means "expect this stream not to exist" (creation).
4. There is **no** automatic retry inside the store. A retry would silently re-apply a command against state the caller never inspected. The caller must reload and re-decide. This is an explicit safety choice, not an omission.
5. Even if a caller passed a stale version that happened to match, `PRIMARY KEY(stream_id, stream_version)` provides a second, independent barrier: the insert fails.

### Two independent barriers, deliberately

The version check is application-level and could in principle be bypassed; the primary key is database-level and cannot. A conformance test exercises the database barrier directly by attempting a duplicate `(stream_id, stream_version)` insert with the application check disabled.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Timestamp ordering | Collision-prone, non-monotonic under NTP, and explicitly forbidden by spec §13. This is the current defect. Rejected. |
| Hybrid logical clocks | Solves cross-node ordering, which M0 does not have (single process, single store). Complexity with no M0 benefit. Deferred to any future distributed ADR. |
| UUIDv7 / ULID as the order key | Time-derived and therefore inherits clock skew; also gives no `expected_version` semantics. Rejected as the ordering mechanism; UUIDs remain fine as *identifiers*. |
| Pessimistic locking (`SELECT ... FOR UPDATE`) | Not available in SQLite in the required form; `BEGIN IMMEDIATE` already gives write serialization. Optimistic versioning additionally detects *logical* staleness — a caller that read old state — which locking alone does not. |
| Automatic retry on conflict | Silently re-applies intent against unseen state. Can convert a safe rejection into an unsafe duplicate. Rejected. |
| Vector clocks | Multi-writer concurrency resolution; no M0 requirement. Rejected. |

## Consequences

**Positive**
- Ordering is total, deterministic, and independent of the clock. Replay in `globalSequence` order reproduces the same state on any machine.
- Stale writes are detected and rejected with a specific, testable error.
- Two independent barriers mean a single coding mistake cannot corrupt stream ordering.

**Negative / costs**
- Callers must handle `ConcurrencyConflictError` and implement their own reload-and-retry policy.
- The global counter is a serialization point (accepted; `BEGIN IMMEDIATE` already serializes writers).
- `expectedVersion` must be threaded through every command signature.

## Reversal conditions

1. Multi-node deployment → global sequence from a single row no longer works; requires hybrid logical clocks or a sequencer service, and a new ADR.
2. Conflict rate becomes high enough that manual retry is impractical → introduce a *typed, explicitly-safe* retry policy per command class, never a blanket retry.

## Evidence from the current repository

- `capt_solo/foundry/governance.py:135` — `q += " ORDER BY timestamp DESC"`; ties are undefined.
- `capt_solo/ctp/journal.py:144,154,159,163,168` — `time.time()` on every record; ordering is file-append order.
- `capt_solo/khsb/bus.py` `Message.ts` — float timestamp, no sequence field.
- Baseline §3 row 8 — no aggregate-version or `expected_version` concept exists in 16,498 lines of Python.
