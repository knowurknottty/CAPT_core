# ADR-0104 — Transactional state store and event-ledger semantics

**Status:** Accepted (M0-A)
**Date:** 2026-08-02
**Relates to:** spec §5, §14, spec ADR-005, workflow §7

## Context

Spec invariant 10: consequential state transitions are committed transactionally *before* authoritative events are dispatched. Spec §14: M0 uses **one** transactional store; SQLite is the default local-first candidate.

Baseline findings:

- `capt_solo/memory/engine.py` already uses SQLite with `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, a `schema_version` table, versioned migrations 1→4, and a **verified pre-migration backup gate** (`_backup_before_migration`, which uses SQLite's online backup API and runs `PRAGMA integrity_check` on the copy). This is a mature, defensible persistence convention.
- `capt_solo/ctp/journal.py` is an append-only JSONL journal with `fsync` per record. It is durable but has **no** stream version, no aggregate binding, no schema version, no payload digest, no global sequence, and — critically — **it is not in the same transaction as any state mutation**. A crash between a memory write and a journal append leaves them inconsistent.

## Decision

**One SQLite database, `runtime.db`, separate from `memory.db`, holding aggregate state, the event ledger, the outbox, the command log, and checkpoint manifests, with every consequential change committed in a single transaction.**

### Store choice
- SQLite, `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `PRAGMA synchronous=FULL` on the runtime store (durability over throughput; the runtime store is low-volume and governance-critical).
- Python's `sqlite3` with `isolation_level=None` (explicit transaction control) and `BEGIN IMMEDIATE` for every write transaction, so writer contention fails fast rather than at COMMIT.
- **Separate file from `memory.db`.** Justification: different authority owner, different lifecycle, different backup policy, and — decisively — sharing the file would let any of the five existing foundry subsystems mutate runtime state through the shared connection, defeating ADR-0103.

### Tables

| Table | Purpose | Key integrity constraint |
|---|---|---|
| `runtime_schema_version` | store schema version | single row |
| `aggregate` | current version + serialized state per stream | `PRIMARY KEY(stream_id)`; `version` monotonic |
| `event_ledger` | append-only durable events | `PRIMARY KEY(stream_id, stream_version)`; `UNIQUE(event_id)`; `global_sequence INTEGER` autoincrement |
| `outbox` | post-commit dispatch queue | `PRIMARY KEY(event_id)`; `status`, `attempts`, `dispatched_at` |
| `command_log` | idempotency keys → outcome | `PRIMARY KEY(idempotency_key)`; stores `operation_fingerprint` and result event ids |
| `checkpoint` | checkpoint manifests | `PRIMARY KEY(checkpoint_id)`; `integrity_digest` |

### The single transaction

Every consequential command executes exactly this sequence, and any failure aborts the whole thing:

```
BEGIN IMMEDIATE
  1. command_log lookup by idempotency_key      -- ADR-0108
  2. load aggregate rows with current versions
  3. check expected_version                     -- ADR-0106
  4. evaluate invariants on the aggregate
  5. produce events (pure function, no I/O)
  6. INSERT event_ledger rows                   -- fails on (stream_id, stream_version) conflict
  7. UPDATE aggregate rows to new versions
  8. INSERT outbox rows (status='pending')
  9. INSERT command_log row
COMMIT
-- only now:
 10. OutboxDispatcher delivers                  -- ADR-0105
```

Steps 6, 7, 8, 9 are in the **same** transaction. This is the property that makes "durable events are recorded only after valid state transitions" and "authoritative events are never published before commit" simultaneously true.

### Event ledger semantics
- **Append-only.** No `UPDATE` or `DELETE` statement targeting `event_ledger` exists in the codebase; a conformance test greps the runtime package to prove it.
- **Per-stream ordering** by `stream_version`, enforced by the composite primary key: a duplicate or out-of-order version is a database-level constraint violation, not a Python check that can be forgotten.
- **Global ordering** by `global_sequence` (SQLite `INTEGER PRIMARY KEY AUTOINCREMENT` semantics via a monotone counter inside the transaction). Used for deterministic dispatch order and replay order across streams.
- **Integrity.** Each event row stores `payload_digest = sha256(canonical_json(payload))`. Replay recomputes and compares; a mismatch raises `LedgerIntegrityError`. Per spec §14 and ledger Finding K, a synchronous per-event hash *chain* is deliberately **not** in the M0 critical path; the checkpoint manifest carries the aggregated integrity digest instead (ADR-0109).

### Relationship to existing subsystems
- `memory.db` (existing) — untouched.
- CTP journal (existing) — untouched, and explicitly **not** the runtime ledger. Documented in the baseline term map.
- KHSB (existing) — classified as the ephemeral signal bus; must not carry authoritative events (ADR-0105).

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Extend `memory.db` with runtime tables | Would place runtime state behind the same shared connection used by five foundry subsystems, defeating ADR-0103's ownership enforcement. Also couples two very different backup/retention policies. Rejected. |
| Reuse the CTP JSONL journal as the ledger | Cannot participate in a SQL transaction with the state write; no stream version; no concurrency control. The crash window it leaves is precisely what invariant 10 forbids. Rejected. |
| Postgres in M0 | Spec §14 permits it as a later target; requires a server process, breaking local-first/offline (invariant 15). Rejected for M0. |
| Two stores (state + ledger) with 2PC | Introduces distributed-commit failure modes before the constitutional invariants are proven. Directly contradicts spec §3.2. Rejected. |
| Event-sourcing with no aggregate snapshot table | Forces full replay on every command; makes optimistic concurrency awkward (version must be derived by scan). Snapshot + ledger is cheaper and makes ADR-0106 a single-row check. Rejected. |
| `synchronous=NORMAL` | Faster, but a power loss can lose the last transactions in WAL mode. For a governance ledger this is unacceptable. Rejected. |

## Consequences

**Positive**
- Atomicity of {state, event, outbox, command log} is provided by the database, not by application discipline.
- Duplicate stream versions are impossible by primary key, so the ordering invariant cannot be violated by a code path that forgot to check.
- Local-first and offline-capable; no server.

**Negative / costs**
- Single-writer. Concurrent writers serialize on `BEGIN IMMEDIATE`; a loser gets `SQLITE_BUSY` and must retry. Acceptable at M0 volume; measured limits are unknown and are recorded as residual uncertainty.
- A second database file to back up and migrate.
- `synchronous=FULL` costs an fsync per commit.

## Reversal conditions

1. Measured write throughput becomes a bottleneck (sustained > ~100 consequential commands/sec) → evaluate Postgres, which preserves the single-transaction property.
2. Multi-process concurrent writers become a requirement → SQLite `BEGIN IMMEDIATE` retry is insufficient; move to Postgres.
3. Tamper evidence requirements strengthen to per-event chaining → add a hash chain, accepting the migration cost identified in ledger Finding K.

## Evidence from the current repository

- `capt_solo/memory/engine.py:86-90` — existing SQLite + WAL + foreign_keys convention.
- `capt_solo/memory/engine.py:97-178` — `_backup_before_migration`, online backup API + `PRAGMA integrity_check`; the precedent for migration safety adopted here.
- `capt_solo/ctp/journal.py:116-129` — journal `fsync` append; note it takes `self._lock` (a thread lock), **not** a database transaction, and has no relationship to any state write.
- `grep -rni outbox capt_solo/` → no results. The outbox is new.
- `capt_solo/khsb/bus.py:165` `_dispatch` — synchronous in-process delivery inside `publish()`, with no commit relationship.
