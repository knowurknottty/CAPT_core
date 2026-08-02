# CAPT Runtime Architecture Specification

**Status:** Proposed M0 architecture  
**Scope:** CAPT Agent Runtime modular monolith, authority domains, event-sourced boundaries, execution-driver integration  
**Revision method:** Construct → adversarial review → reconcile  

## 1. Thesis

CAPT must ship first as a **modular monolith with hard authority boundaries, CAPT-owned contracts, one transactional state store, an append-only event ledger for consequential transitions, independent verification, and replaceable execution drivers**.

CAPT is not an agent framework wrapper. It is the constitutional and cognitive platform that defines the laws, contracts, state transitions, evidence semantics, and completion rules under which external harnesses may execute work.

External harnesses are treated as untrusted, replaceable **Execution Drivers**. They receive narrow work orders and return observations, artifact candidates, receipt candidates, and claim proposals. They never emit authoritative CAPT state.

## 2. Architectural invariants

1. Cognition may propose.
2. Governance may authorize or deny.
3. Execution may perform only authorized work.
4. Verification may establish whether claimed outcomes occurred.
5. ClaimGuard may accept, qualify, reject, escalate, persist, or suppress claims according to policy.
6. No kernel may impersonate another kernel’s authority.
7. No consequential side effect may execute without a valid capability lease.
8. No completion claim may be accepted without the required evidence and verification state.
9. Drivers are untrusted integration components, not CAPT authorities.
10. Consequential state transitions are committed transactionally before authoritative events are dispatched.
11. Deterministic work must not be delegated to a probabilistic model when a deterministic mechanism exists.
12. Recovery must not blindly repeat an indeterminate side effect.
13. State mutation has one authoritative aggregate owner.
14. Contracts are language-neutral at the source and generated for TypeScript and Python.
15. Local-first execution and degraded offline operation are mandatory architectural properties.

## 3. Deployment model

### 3.1 M0 deployment

A single `capt-runtime` process contains the control and state-transition logic:

```text
capt-runtime
│
├── Mission Application Service
├── Constitutional Domain
├── Cognitive Domain
├── Execution Domain
├── Verification Domain
├── Persistence Layer
└── External Boundary
```

Unsafe plugins, shell execution, sandboxes, and external harnesses may run out of process. Governance, state ownership, verification decisions, and authoritative event creation remain CAPT-owned.

### 3.2 Why not distributed first

A distributed-first design would introduce ordering, duplication, network partitions, consensus, multi-database consistency, and operational failure modes before the constitutional invariants are proven. M0 therefore uses direct typed commands for inner-loop operations and durable events only for consequential transitions and external effects.

## 4. Planes and authority domains

### 4.1 Constitutional Plane

**Authority:** authorize, deny, constrain, revoke, escalate, and control claim promotion.

Modules:

- `GovernanceKernel`
- `PolicyEngine`
- `RiskEngine`
- `CapabilityAggregate`
- `CapabilityGateway`
- `ClaimGuard`

The Constitutional Plane does not execute tools and does not claim work succeeded.

### 4.2 Cognitive Plane

**Authority:** interpret, plan, retrieve context, propose actions, and construct reasoning artifacts.

Modules:

- `MissionCompiler`
- `InputNormalizer`
- `DeterministicConstraintExtractor`
- `AmbiguityDetector`
- optional model-assisted semantic parser
- `MissionGraphBuilder`
- `Planner`
- `ContextBroker`
- `MemoryBroker`
- optional counterargument strategy

The Cognitive Plane cannot grant capabilities or perform side effects.

### 4.3 Execution Plane

**Authority:** perform only work covered by valid grants and leases.

Modules:

- `TaskAggregate`
- `TaskStateMachine`
- `RuntimeScheduler`
- `ExecutionKernel`
- `ToolDispatcher`
- `SandboxManager`
- `CheckpointManager`
- `DriverHost`
- `ExecutionDriver` implementations

### 4.4 Event Plane

**Authority:** record and disseminate committed events. It does not independently decide domain outcomes.

Modules:

- `EventLedger`
- `OutboxDispatcher`
- `EphemeralSignalBus`
- `ProvenanceIndex`
- `AuditStream`

## 5. Command, state transition, and event model

CAPT uses the following pattern:

```text
Command
  ↓
Synchronous validation
  ↓
Authorization
  ↓
Transactional aggregate mutation
  ↓
Durable event appended
  ↓
Outbox record committed
  ↓
Post-commit dispatch
```

### 5.1 Commands

Commands are typed requests handled within the modular monolith. Examples:

- `CreateMission`
- `AuthorizeAction`
- `IssueCapabilityGrant`
- `ActivateCapabilityLease`
- `DispatchDriverWorkOrder`
- `RecordDriverObservation`
- `VerifyClaim`
- `CreateCheckpoint`
- `ResumeMission`

### 5.2 Durable events

Examples:

- `MissionCreated`
- `PolicyEvaluated`
- `CapabilityGranted`
- `CapabilityLeaseActivated`
- `CapabilityLeaseRevoked`
- `ToolExecutionReserved`
- `ToolExecutionRequested`
- `ToolExecutionFinalized`
- `DriverObservationAccepted`
- `EvidenceRecorded`
- `ClaimCreated`
- `ClaimVerified`
- `ClaimAccepted`
- `ClaimRejected`
- `CheckpointCreated`
- `MissionResumed`

### 5.3 Ephemeral signals

Examples:

- streaming token fragments
- transient progress indicators
- UI animation hints
- high-frequency resource samples before aggregation

Ephemeral signals are never the source of truth.

## 6. Aggregate ownership

### 6.1 MissionAggregate

Owns:

- mission identity
- normalized request
- objectives and constraints
- lifecycle state
- success and termination criteria
- TaskGraph reference
- terminal decision

### 6.2 TaskAggregate

Owns:

- task lifecycle
- dependencies
- attempts
- assigned driver
- retry, cancellation, suspension, and recovery state
- current execution status

### 6.3 CapabilityAggregate

Owns:

- capability definitions
- grants
- leases
- reservations
- consumption
- revocation
- expiration

### 6.4 DriverRunAggregate

Owns:

- work-order version
- driver identity
- external run identifier
- lifecycle state
- observations
- cancellation
- reconciliation status

### 6.5 ClaimAggregate

Owns:

- claim proposal
- evidence links
- verification results
- ClaimGuard decisions
- promotion and persistence state

No other module may directly mutate an aggregate’s owned state.

## 7. Mission model

### 7.1 Minimal MissionGraph core

M0 supports only operational node classes:

- Mission
- Objective
- Constraint
- Task
- Dependency
- EvidenceRequirement
- VerificationRequirement
- ApprovalRequirement
- SuccessCriterion
- TerminationCriterion

A node belongs in the canonical MissionGraph only if it affects authorization, scheduling, execution, verification, or completion.

### 7.2 Intent compilation pipeline

```text
Raw request
  ↓
InputNormalizer
  ↓
DeterministicConstraintExtractor
  ↓
AmbiguityDetector
  ↓
Optional model-assisted semantic parser
  ↓
Policy annotation
  ↓
MissionSpecValidator
```

The compiled mission preserves:

- raw input
- normalized input
- explicit user constraints
- inferred constraints
- policy-added constraints
- unresolved ambiguity
- confidence and provenance for inferred fields

## 8. Task and dependency semantics

M0 does not model `parallel` as a dependency edge. Tasks become parallel when their predecessor conditions are simultaneously satisfied.

Dependency conditions:

- `completed`
- `succeeded`
- `failed`
- `verified`
- `approved`

Compensation and rollback are modeled as explicit tasks and dependency conditions, not implicit control flow.

## 9. Capability lifecycle

### 9.1 Capability definition

Defines what an operation permits and which capabilities it depends on.

### 9.2 Capability requirement

Defines what a task or tool requires for a particular resource and scope.

### 9.3 Capability grant

A scoped, conditioned, versioned authorization issued to a subject.

Required properties include:

- subject
- capability
- resource
- operations
- typed scope
- policy decision reference
- policy bundle digest
- conditions
- use limit
- validity window
- issuing authority

### 9.4 Capability lease

Binds a grant to a mission, task, and execution context.

### 9.5 Reservation and consumption

Consequential execution uses two phases:

```text
lease use reserved
  ↓
tool invoked
  ↓
use finalized as succeeded / failed / indeterminate
```

Indeterminate operations require reconciliation before retry.

### 9.6 Revocation

Grants and leases may be revoked. Execution checks revocation immediately before a consequential side effect, not only when a work order is issued.

## 10. Execution-driver boundary

### 10.1 Trust model

Execution Drivers are untrusted. They may propose claims and return observations, but they cannot create authoritative CAPT events.

### 10.2 Work-order contents

A driver receives only the minimum delegated package:

- one task
- permitted tools
- context slice
- capability lease identifiers
- filesystem policy
- network policy
- budgets
- expected artifacts
- required receipts
- termination conditions
- idempotency key
- operation fingerprint
- replay policy

Drivers do not receive unrestricted credentials, global policy state, unrelated memory, or authority to redefine completion.

### 10.3 Driver interface

A production-capable driver contract must support:

- `describe`
- `submit`
- `inspect`
- `cancel`
- `resume`
- `reconcile`

Driver output types are explicitly untrusted:

- `DriverObservation`
- `DriverArtifactCandidate`
- `DriverReceiptCandidate`
- `DriverClaimProposal`
- `DriverProgressSignal`

CAPT validates and converts accepted driver output into evidence, claims, and authoritative events.

## 11. Idempotency and recovery

Every consequential operation carries:

- idempotency key
- operation fingerprint
- attempt number
- replay policy
- reservation identifier
- side-effect identity where available

Replay policies:

- `never`
- `safe`
- `verify-before-retry`

The runtime never repeats an indeterminate side effect until reconciliation determines whether the external effect occurred.

## 12. Verification and ClaimGuard

### 12.1 VerificationPipeline

Answers whether evidence supports a claim.

Strategies may include:

- direct observation
- deterministic schema validation
- artifact hashing
- test exit-status verification
- invariant checks
- independent reproduction
- source triangulation
- counterargument generation
- human review

Strategy selection is claim-type and consequence-aware.

### 12.2 ClaimGuard

Controls whether a claim may be emitted, persisted, promoted, or acted upon.

Possible decisions:

- accept
- qualify
- reject
- escalate

A technically verified claim may still be blocked or qualified by privacy or policy. An unverified observation may be preserved as an explicitly unverified lead.

Completion claims require strict evidence, verification, and capability-consumption requirements.

## 13. Event ordering and concurrency

Durable events include:

- stream identifier
- aggregate version
- schema version
- correlation identifier
- causation identifier
- local sequence
- optional global sequence

The transactional store uses optimistic concurrency or equivalent aggregate-version checks. Timestamps are descriptive and are not used as the sole ordering mechanism.

## 14. Persistence

M0 uses one transactional store. SQLite is the default local-first candidate; Postgres is a compatible deployment target once interfaces are stable.

Persistence responsibilities:

- aggregate snapshots or current state
- append-only event ledger
- outbox
- checkpoint manifests
- artifact and evidence indexes
- policy bundle references

Tamper evidence should begin with per-event hashes and signed or Merkle-rooted checkpoint manifests. A synchronous per-event hash chain is not required in the M0 critical path.

## 15. Checkpoint manifest

A checkpoint records:

- mission aggregate version
- task aggregate versions
- capability grants, leases, reservations, and revocations
- driver-run states
- policy bundle version and digest
- artifact hashes
- context references
- pending outbox entries
- recovery instructions

A checkpoint is not considered valid until its referenced state and artifacts are internally consistent.

## 16. Context disclosure controls

Every context item includes:

- source provenance
- sensitivity classification
- consent scope
- trust level
- freshness
- redaction state
- downstream-use restrictions

A driver receives only the context items cleared for that driver and task.

## 17. Human approval

Approval contracts must capture:

- request identity
- requested scope
- approver identity
- decision
- modifications
- validity window
- use count
- revocation
- policy basis

Approval does not itself perform an action; it satisfies a condition for a grant or lease.

## 18. Language-neutral contracts

The canonical source of truth is language-neutral, such as JSON Schema with explicit semantic invariants. Generated packages provide TypeScript and Python bindings.

Proposed layout:

```text
contracts/
├── schema/
├── generated/typescript/
├── generated/python/
├── invariants/
└── conformance-tests/
```

TypeScript interfaces are reference views, not the sole normative definition.

## 19. M0 phased proof

### M0-A — Contract and state proof

Demonstrate:

- mission creation
- policy decision
- grant issuance
- lease activation
- task transition
- durable ledger commit
- checkpoint
- restart and replay

No external driver is required.

### M0-B — Read-only driver proof

Demonstrate:

- narrow work order
- repository inspection
- untrusted observation ingestion
- evidence recording
- no write authority
- cancellation and reconciliation

### M0-C — Governed isolated write

Scenario:

> Inspect a repository, modify one file in an isolated worktree, run verification, and prepare—but do not push—a commit.

Required flow:

1. Receive mission.
2. Compile MissionSpec.
3. Classify repository write as consequential.
4. Issue repository-read and isolated-worktree-write grants.
5. Build TaskGraph: inspect → propose → authorize → edit → test → verify → report.
6. Issue a narrow driver work order.
7. Reserve lease consumption before the write.
8. Apply the edit only in the isolated worktree.
9. Capture diff, command, exit status, and artifact hashes.
10. Independently verify the diff and test result.
11. Accept only the claim “change verified locally in isolated worktree.”
12. Reject claims of push, merge, deployment, or release.
13. Create a checkpoint.
14. Restart the process.
15. Resume without repeating the write.

## 20. M0 acceptance gates

M0 is not complete until all of the following are proven:

1. A model or driver can be replaced without changing governance semantics.
2. No tool executes without a valid lease.
3. Revoked authority cannot be used.
4. Indeterminate side effects are reconciled before retry.
5. Durable events dispatch only after commit.
6. A restart resumes without duplicate side effects.
7. Driver output cannot forge authoritative CAPT events.
8. Verification is independent of the executor for consequential claims.
9. Completion claims are constrained by evidence and ClaimGuard policy.
10. Context disclosure is task- and driver-scoped.
11. Aggregate version conflicts are detected.
12. Contracts round-trip across generated TypeScript and Python bindings.

## 21. Deferred work

The following are explicitly deferred until M0 invariants are proven:

- distributed event infrastructure
- multi-database runtime
- generalized multi-agent markets
- cross-node consensus
- executable Knowledge Bubbles
- multiple workflow engines
- broad driver marketplace
- model ensembles
- highly generic MissionGraph ontology
- distributed capability negotiation
- autonomous policy rewriting

## 22. Architectural decisions

### ADR-001: Modular monolith first

Chosen because it preserves authority boundaries without premature distributed-system complexity.

### ADR-002: Commands plus durable events

Chosen over event-only choreography. Commands own intent; aggregates own state transitions; events record accepted outcomes.

### ADR-003: External harnesses as untrusted drivers

Chosen to preserve CAPT sovereignty and prevent framework ownership.

### ADR-004: Language-neutral contract source

Chosen to support the current Python codebase and future TypeScript or Rust components without making one implementation language the architecture.

### ADR-005: One transactional store in M0

Chosen to make aggregate mutation, ledger append, and outbox insertion atomic.

### ADR-006: Effectively-once execution

Exactly-once external side effects cannot be guaranteed universally. CAPT therefore uses idempotency, reservation, receipts, reconciliation, and verify-before-retry semantics.

## 23. Risks

Primary implementation risks:

- unclear aggregate ownership
- over-generalized schemas
- driver leakage of authority
- policy and capability drift
- incomplete recovery semantics
- context over-disclosure
- approval fatigue
- excessive planning overhead
- treating model output as execution evidence
- premature distribution

Each risk requires an executable conformance test before the corresponding feature is considered production-ready.

## 24. Final recommendation

Build CAPT M0 as a CAPT-owned modular monolith with explicit authority domains, aggregate ownership, scoped capability leases, one transactional state store, an append-only event ledger, post-commit outbox dispatch, independent verification, and one narrow Execution Driver.

Implement M0-A, M0-B, and M0-C as separate gated proofs. Do not generalize into distributed agents, multiple drivers, executable knowledge systems, or a public ecosystem until the governed isolated-write scenario survives restart, replay, revocation, driver failure, and false completion-claim tests.
