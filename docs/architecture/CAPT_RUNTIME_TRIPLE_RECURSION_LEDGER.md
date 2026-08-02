# CAPT Runtime Architecture — Triple-Recursion Ledger

**Branch:** `docs/capt-runtime-architecture-spec`  
**Artifact under review:** `docs/architecture/CAPT_RUNTIME_ARCHITECTURE_SPEC.md`

This ledger records the three-pass process used to construct, challenge, and reconcile the CAPT Runtime Architecture Specification. It contains design decisions and revision evidence, not private chain-of-thought.

## Pass 1 — Construct

The initial architecture established these foundations:

- CAPT as a platform of constitutional, cognitive, execution, and event planes.
- Governance, cognition, execution, verification, and ClaimGuard as separate authority domains.
- A modular monolith for M0 rather than an internally distributed system.
- Direct typed command calls for inner-loop work.
- Durable events for consequential state transitions and external effects.
- External harnesses treated as replaceable Execution Drivers.
- Mission compilation into an operational MissionGraph and TaskGraph.
- Capability definitions, grants, leases, and consumption records.
- Independent verification before completion claims.
- A governed isolated repository-edit scenario as the first end-to-end proof.

### Constructed thesis

CAPT should own execution semantics, public contracts, governance, cognition, evidence, state transitions, and claim integrity while borrowing execution primitives behind narrow driver boundaries.

## Pass 2 — Adversarial Review

The constructed design was challenged for ambiguity, premature generalization, security gaps, and recovery defects.

### Finding A — Aggregate ownership was implicit

**Risk:** GovernanceKernel, TaskStateMachine, CapabilityGateway, and ExecutionKernel could mutate overlapping state.

**Correction:** Define Mission, Task, Capability, DriverRun, and Claim aggregates with exclusive mutation ownership.

### Finding B — Task edge semantics were underspecified

**Risk:** `parallel` as an edge type does not define deterministic workflow behavior.

**Correction:** Use predecessor conditions such as `completed`, `succeeded`, `failed`, `verified`, and `approved`. Parallelism emerges when multiple tasks become runnable.

### Finding C — Security-critical `unknown` fields were too permissive

**Risk:** Arbitrary payloads in constraints, scopes, conditions, and events could bypass compile-time and runtime validation.

**Correction:** Require language-neutral schemas and discriminated unions. Reserve extension envelopes for explicitly untrusted plugin data.

### Finding D — Capability revocation was absent

**Risk:** A long-running driver could use authority after approval withdrawal.

**Correction:** Add grant and lease revocation and require a final revocation check immediately before consequential effects.

### Finding E — Lease consumption timing was ambiguous

**Risk:** A crash between side effect and success recording could cause unsafe replay.

**Correction:** Introduce reservation and finalization states: succeeded, failed, or indeterminate. Indeterminate effects require reconciliation.

### Finding F — Idempotency was implied but not contracted

**Risk:** Restart could repeat external side effects.

**Correction:** Add idempotency keys, operation fingerprints, attempts, replay policy, reservations, and side-effect identity.

### Finding G — Driver interface was insufficient

**Risk:** A single `submit()` promise could not represent suspension, cancellation, partial results, crash recovery, or reconciliation.

**Correction:** Require driver methods for describe, submit, inspect, cancel, resume, and reconcile.

### Finding H — Driver events could be mistaken for authoritative events

**Risk:** An external harness could forge `TaskCompleted`, `EvidenceRecorded`, or similar CAPT outcomes.

**Correction:** Drivers emit only untrusted observations, candidates, progress signals, and claim proposals. CAPT alone creates authoritative events.

### Finding I — Policy decisions lacked binding identity

**Risk:** Grants could not be audited against the exact policy version that authorized them.

**Correction:** Bind grants to a PolicyDecision identifier and policy bundle digest.

### Finding J — Event ordering relied too heavily on timestamps

**Risk:** Concurrent tasks could race or replay out of order.

**Correction:** Add stream IDs, aggregate versions, schema versions, correlation IDs, causation IDs, and sequence values.

### Finding K — Hash chaining risked premature complexity

**Risk:** A synchronous per-event chain could complicate migration and recovery without proving the core runtime.

**Correction:** Begin with append-only events, event hashes, and signed or Merkle-rooted checkpoint manifests.

### Finding L — Checkpoints were too shallow

**Risk:** Mission state plus a worktree pointer would not capture leases, driver runs, policy versions, artifacts, or pending outbox entries.

**Correction:** Define a checkpoint manifest covering aggregate versions, authority state, artifacts, drivers, policy, context references, and recovery instructions.

### Finding M — Context disclosure controls were incomplete

**Risk:** Drivers could receive unrelated, stale, sensitive, or non-consented context.

**Correction:** Add provenance, sensitivity, consent, trust, freshness, redaction, and downstream-use metadata.

### Finding N — Human approval semantics were incomplete

**Risk:** Approval could be over-broad, stale, repeatable, or impossible to revoke.

**Correction:** Define scoped, expiring, revocable approval records that satisfy grant conditions but do not execute actions.

### Finding O — TypeScript as sole contract authority conflicted with CAPT’s Python base

**Risk:** Architecture could become implementation-language-owned.

**Correction:** Make language-neutral schemas normative and generate TypeScript and Python bindings.

### Finding P — Complete repo-edit automation was too large for the first proof

**Risk:** Failures would be difficult to localize.

**Correction:** Divide M0 into M0-A contract/state proof, M0-B read-only driver proof, and M0-C governed isolated write.

## Pass 3 — Reconcile

The final specification incorporates every accepted correction.

### Reconciled architecture

- **Deployment:** one `capt-runtime` process for M0.
- **Authority:** constitutional, cognitive, execution, verification, and claim-governance domains remain distinct.
- **State:** aggregates own mutation; one transactional store protects consistency.
- **Interaction:** direct typed commands handle inner-loop requests.
- **Events:** consequential outcomes are appended durably and dispatched post-commit through an outbox.
- **Drivers:** external harnesses are untrusted and narrowly scoped.
- **Capabilities:** grants, leases, reservations, consumption, expiration, and revocation are explicit.
- **Recovery:** idempotency and reconciliation provide effectively-once semantics.
- **Verification:** claim evidence is evaluated independently before ClaimGuard controls promotion.
- **Contracts:** language-neutral source generates TypeScript and Python packages.
- **Delivery:** M0-A, M0-B, and M0-C are gated proofs.

## Rejected alternatives

### Distributed event platform in M0

Rejected because it adds network and consistency failures before local constitutional invariants are proven.

### Event-only module interaction

Rejected because synchronous validation, policy predicates, state reads, and deterministic transformations are clearer and safer as typed commands.

### Existing harness as CAPT core

Rejected because framework ownership would couple governance and cognition to external execution semantics.

### Driver receives complete MissionGraph

Rejected because it overexposes context and authority. Drivers receive task-scoped work orders only.

### Exactly-once external side effects

Rejected as a universal guarantee. CAPT targets effectively-once operation using idempotency, reservations, receipts, reconciliation, and verify-before-retry.

### Full MissionGraph ontology in M0

Rejected to avoid semantic bloat. Only operational nodes that affect authorization, scheduling, execution, verification, or completion are canonical.

## Residual uncertainty

The following remain intentionally unresolved until implementation evidence exists:

- SQLite versus another local transactional store after measured workload testing.
- Exact schema technology for language-neutral contracts.
- Which existing harness should become the first driver.
- Whether some unsafe driver operations require mandatory process isolation in M0-B.
- The minimum useful ContextBroker and MemoryBroker integration for the first repository scenario.
- Performance cost of aggregate snapshots versus event replay.
- Operator approval UX and anti-fatigue policy.

## Final disposition

The reconciled specification is suitable as the architectural basis for the next workflow. It must not be treated as proof that the runtime exists. Implementation claims require conformance tests and the M0-A, M0-B, and M0-C acceptance evidence defined in the specification.
