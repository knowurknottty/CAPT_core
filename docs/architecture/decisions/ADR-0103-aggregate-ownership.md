# ADR-0103 — Aggregate ownership and mutation boundaries

**Status:** Accepted (M0-A)
**Date:** 2026-08-02
**Relates to:** spec §6, ledger Finding A, workflow Gate 3

## Context

Ledger Finding A: aggregate ownership was implicit in the constructed architecture, so `GovernanceKernel`, `TaskStateMachine`, `CapabilityGateway`, and `ExecutionKernel` could mutate overlapping state.

The baseline confirms this risk is real in the existing codebase, not hypothetical. `capt_solo/foundry/governance.py:64` defines:

```python
def _act(self, action, actor, target, reason, fn) -> GovernanceReceipt:
    tx_id = self._ctp.begin(...)
    result = fn(tx_id)          # arbitrary callable, arbitrary tables
```

`fn` is an arbitrary callable that mutates arbitrary tables through a **shared** `sqlite3` connection. There is no ownership check anywhere in the tree. This is the concrete failure mode the spec forbids.

## Decision

**Five aggregates, each with exactly one authoritative mutator, enforced structurally rather than by convention.**

| Aggregate | Stream prefix | Owns | Explicitly does NOT own |
|---|---|---|---|
| `MissionAggregate` | `mission-` | mission lifecycle state, objectives, constraints, success criteria, termination criteria, TaskGraph *reference*, terminal decision | task state, capability state, claim state |
| `TaskAggregate` | `task-` | task lifecycle state, dependency declarations, attempt count, assignment, retry state, cancellation, recovery state | mission terminal state, lease state, its own authorization |
| `CapabilityAggregate` | `capability-` | grants, leases, reservations, consumption records, revocations, expiry evaluation | task state, mission state, policy decisions |
| `DriverRunAggregate` | `driverrun-` | work-order version, driver identity, external run id, run lifecycle state, observations, cancellation, reconciliation status | **M0-A: contract and state model only; no driver integration** |
| `ClaimAggregate` | `claim-` | claim proposal, evidence links, verification results, ClaimGuard decision, promotion state | evidence content, verification execution |

### Enforcement mechanism

Ownership is enforced at three layers, not one:

1. **Type layer.** Each aggregate class declares `STREAM_PREFIX` and `EVENT_TYPES` (a frozen set). `Aggregate.apply(event)` raises `AggregateOwnershipError` if `event.eventType` is not in its own `EVENT_TYPES`.
2. **Store layer.** `RuntimeStore.append()` derives the owning aggregate from `EVENT_TYPE_OWNER` (a single module-level registry) and raises `AggregateOwnershipError` if the target `streamId` prefix does not match that owner. **This is the load-bearing check**: it holds even if a caller bypasses the aggregate object entirely and writes to the store directly.
3. **Registry-completeness test.** A conformance test asserts `EVENT_TYPE_OWNER` covers every event type in the generated `EventType` enum and that the owner sets are pairwise disjoint. A new event type with no owner, or with two owners, fails CI.

### Cross-aggregate change rule

A single command may touch more than one aggregate **only** through an application service (`capt_runtime/services.py`) that:

- executes all appends inside **one** store transaction (ADR-0104);
- passes an explicit `expected_version` per aggregate (ADR-0106);
- records the causal chain via `causationId` so the multi-aggregate change is auditable as one unit.

No aggregate may call another aggregate's mutator. Aggregates are pure state machines over events; they hold no store reference.

### Read/write asymmetry

Aggregates may *read* projections of other aggregates (e.g. a service reads capability state to decide whether a task may transition). Only the owner may *write*. Reads carry no version guarantee and must not be cached across a transaction boundary.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Convention + code review | This is exactly what the existing `Governance._act` does, and it provides no guarantee. Unenforceable claims are the failure mode M0-A exists to eliminate. |
| One "RuntimeAggregate" owning all state | Trivially satisfies "one owner" while destroying the authority separation that is invariant 6. Serializes all concurrency. Rejected. |
| Ownership enforced only in the aggregate class | Bypassable by writing to the store directly. Insufficient — hence the store-layer check. |
| Database-level per-table permissions | SQLite has no per-connection table grants. Not available. |
| Runtime introspection of the call stack | Fragile, defeatable, and untestable. Rejected. |

## Consequences

**Positive**
- A cross-aggregate mutation is impossible to write accidentally; it fails with a specific, tested exception.
- Adding an event type without declaring an owner is a CI failure, so the invariant cannot rot.

**Negative / costs**
- Cross-aggregate workflows need explicit services, which is more code than direct mutation.
- Multi-aggregate transactions serialize on the single store write lock (accepted for M0; ADR-0104 covers the store choice).
- The `EVENT_TYPE_OWNER` registry is a second place to update when adding an event type. Mitigated by the completeness test failing loudly.

## Reversal conditions

1. Aggregate boundaries prove wrong under M0-B/M0-C load (e.g. `DriverRunAggregate` and `TaskAggregate` are shown to require a single transactional identity) → re-partition with a new ADR and a migration.
2. Multi-aggregate transaction contention becomes a measured bottleneck → consider per-aggregate stores with a saga, which requires abandoning ADR-0104's single-transaction guarantee and therefore a new ADR.

## Evidence from the current repository

- `capt_solo/foundry/governance.py:64-87` — `_act(fn)` executes an arbitrary callable inside a CTP transaction; no ownership constraint.
- `capt_solo/foundry/registry.py:102` — `CapabilityRegistry.__init__(conn, ...)` receives the shared connection; so do `ProofEngine`, `SkillFoundry`, `KnowledgeBubbleRuntime`, `WorkflowProofEngine`. Five subsystems, one connection, no boundary.
- Baseline §3 row 9: no `expected_version` or aggregate-version concept exists anywhere in the tree.
