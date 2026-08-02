# CAPT Runtime — Architecture Decision Records

Numbering starts at **0101** to avoid collision with `ADR-001`…`ADR-006`, which are embedded as sections inside `docs/architecture/CAPT_RUNTIME_ARCHITECTURE_SPEC.md` §22. Those remain the architecture-level decisions; the records here are the implementation-level decisions for the M0-A proof gate.

| ADR | Title | Status |
|---|---|---|
| [0101](ADR-0101-canonical-schema-language.md) | Canonical schema language and schema versioning | Accepted (M0-A) |
| [0102](ADR-0102-generated-binding-strategy.md) | Generated TypeScript and Python binding strategy | Accepted (M0-A) |
| [0103](ADR-0103-aggregate-ownership.md) | Aggregate ownership and mutation boundaries | Accepted (M0-A) |
| [0104](ADR-0104-transactional-store-and-ledger.md) | Transactional state store and event-ledger semantics | Accepted (M0-A) |
| [0105](ADR-0105-outbox-behavior.md) | Outbox behavior | Accepted (M0-A) |
| [0106](ADR-0106-ordering-and-concurrency.md) | Event ordering and optimistic concurrency | Accepted (M0-A) |
| [0107](ADR-0107-capability-lifecycle.md) | Capability grants, leases, reservations, revocation, consumption | Accepted (M0-A) |
| [0108](ADR-0108-idempotency-and-replay.md) | Idempotency and replay semantics | Accepted (M0-A) |
| [0109](ADR-0109-checkpoint-and-recovery.md) | Checkpoint manifest and recovery semantics | Accepted (M0-A) |
| [0110](ADR-0110-trusted-state-vs-untrusted-observations.md) | Trusted CAPT state versus untrusted external observations | Accepted (M0-A) |
| [0111](ADR-0111-m0a-exclusions.md) | M0-A exclusions and deferred work | Accepted (M0-A) |

Every record carries: status, context, decision, alternatives considered, consequences, reversal conditions, and evidence drawn from the current repository (file and line references, not documentation claims).

Related Gate 0 artifact: [`../CAPT_RUNTIME_BASELINE_MAP.md`](../CAPT_RUNTIME_BASELINE_MAP.md).
