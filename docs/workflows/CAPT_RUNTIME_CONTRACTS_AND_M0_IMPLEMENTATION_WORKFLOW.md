# CAPT Runtime Contracts and M0 Implementation Workflow

**Status:** Proposed implementation workflow  
**Target branch:** `docs/capt-runtime-architecture-spec`  
**Architecture dependency:** `docs/architecture/CAPT_RUNTIME_ARCHITECTURE_SPEC.md`  
**Revision method:** Construct → adversarial review → reconcile  

## 1. Purpose

This workflow converts the CAPT Runtime Architecture Specification into a language-neutral contract source, generated TypeScript and Python bindings, executable invariants, conformance tests, and the gated M0-A/M0-B/M0-C proofs.

It does not authorize implementation shortcuts, framework ownership, placeholder integrations, or claims of completion without evidence.

## 2. Non-negotiable constraints

1. CAPT contracts are the source of truth; external harness types are adapters only.
2. The canonical schema source must be language-neutral.
3. Generated TypeScript and Python bindings must be reproducible and checked for drift.
4. Aggregate ownership must be explicit before persistence code is written.
5. Every consequential operation must define idempotency and recovery semantics.
6. External drivers return untrusted observations, artifacts, receipts, and claim proposals only.
7. Capability grants must support issuance, lease activation, reservation, consumption, revocation, expiration, and reconciliation.
8. Authoritative state transitions must be committed before durable event dispatch.
9. M0 must remain a modular monolith; no distributed broker or multi-database architecture is permitted without an accepted ADR.
10. No runtime-complete, verified, or production-ready claim may be made until the corresponding proof gate passes.

## 3. Required repository shape

```text
contracts/
├── README.md
├── schema/
│   ├── common/
│   ├── mission/
│   ├── task/
│   ├── capability/
│   ├── event/
│   ├── driver/
│   ├── evidence/
│   ├── claim/
│   ├── verification/
│   ├── checkpoint/
│   ├── approval/
│   └── index.json
├── generated/
│   ├── typescript/
│   └── python/
├── invariants/
│   ├── authority.md
│   ├── aggregate-ownership.md
│   ├── idempotency.md
│   ├── capability-lifecycle.md
│   ├── driver-trust-boundary.md
│   └── claim-integrity.md
└── conformance-tests/
    ├── fixtures/
    ├── schema/
    ├── authority/
    ├── replay/
    ├── capability/
    ├── driver/
    └── claims/
```

The exact generator and schema technology must be selected through an ADR before implementation. JSON Schema 2020-12 is the default candidate because it is language-neutral, widely supported, and can generate validation artifacts for TypeScript and Python. Protobuf, CUE, Smithy, or another system may replace it only with an evidence-backed ADR.

## 4. Deliverable sequence

### Gate 0 — Repository and baseline inspection

Before creating runtime code:

- map current CAPT modules related to lifecycle, memory, ContextPack, ClaimGuard, checkpoints, verification, bridge ownership, events, plugins, and tool execution;
- identify existing schemas and duplicate contract definitions;
- identify current test runners, linting, type checking, packaging, and CI conventions;
- identify Python/TypeScript interoperability requirements;
- record current test status without masking pre-existing failures;
- create a dependency and migration map.

**Required artifact:** `docs/architecture/CAPT_RUNTIME_BASELINE_MAP.md`

**Exit criteria:** No proposed contract duplicates an existing canonical CAPT contract without an explicit migration decision.

### Gate 1 — Contract source and ADRs

Create ADRs for:

1. language-neutral schema source;
2. generated binding strategy;
3. aggregate boundaries;
4. event ledger and outbox persistence;
5. idempotency and indeterminate-effect recovery;
6. capability grant/lease lifecycle;
7. driver trust boundary;
8. checkpoint manifest semantics.

Create the initial schema source for:

- identifiers and timestamps;
- MissionSpec and minimal MissionGraph;
- TaskGraph and TaskDependency;
- EventEnvelope;
- PolicyDecision;
- Capability, Requirement, Grant, Lease, Reservation, Consumption, Revocation;
- ToolRequest and ToolResult;
- DriverDescriptor, DriverWorkOrder, DriverObservation, DriverRunState;
- ClaimRecord, EvidenceRecord, VerificationResult, ClaimGuardDecision;
- CheckpointManifest;
- HumanApprovalRequest and HumanApprovalDecision;
- ErrorEnvelope and Budget.

**Exit criteria:**

- schemas validate;
- no security-critical field uses an unconstrained arbitrary object where a discriminated union can be defined;
- every versioned contract contains `schemaVersion`;
- every state-changing command carries correlation, causation, actor, aggregate, and idempotency metadata as applicable.

### Gate 2 — Generated TypeScript and Python bindings

Build deterministic generators or generation wrappers.

Required properties:

- generated files include a non-editable header;
- generation is reproducible from a clean checkout;
- TypeScript and Python validation behavior is equivalent for shared fixtures;
- CI fails when generated bindings drift from the schema source;
- generated bindings expose typed discriminated unions rather than pervasive `unknown`/`Any` values;
- external extension payloads are isolated under explicit extension namespaces.

**Exit criteria:** Schema fixtures pass in both languages and generated trees are byte-stable across repeated generation.

### Gate 3 — Invariant specifications and conformance harness

Encode at least these invariants:

#### Authority

- cognition cannot issue capability grants;
- execution cannot bypass a denied or revoked grant;
- verification cannot mutate the artifact being verified;
- drivers cannot emit authoritative CAPT events;
- ClaimGuard cannot mark evidence as verified.

#### Aggregate ownership

- MissionAggregate owns mission lifecycle and terminal state;
- TaskAggregate owns task state and attempts;
- CapabilityAggregate owns grant/lease/reservation/consumption/revocation state;
- DriverRunAggregate owns external-run reconciliation;
- ClaimAggregate owns claim, evidence-link, verification, and promotion state.

#### Idempotency and recovery

- consequential requests include an idempotency key and operation fingerprint;
- duplicate committed requests do not duplicate effects;
- indeterminate effects enter reconciliation instead of automatic retry;
- restart replay reconstructs the same aggregate state from the same event stream.

#### Capability lifecycle

- leases cannot exceed parent grant scope or validity;
- child/delegated authority can narrow but never widen parent authority;
- revoked or expired authority fails closed;
- lease use is reserved before dispatch and finalized after reconciliation;
- every side effect links to a consumption record.

#### Claim integrity

- completion claims require configured evidence and verification;
- local verification cannot produce merged, deployed, pushed, or published claims;
- contradicted claims cannot be promoted;
- unverified observations remain explicitly unverified.

**Exit criteria:** Conformance tests fail against deliberately invalid fixtures and pass against valid fixtures.

## 5. M0 proof gates

### M0-A — Contract and state proof

No external execution driver is required.

Implement and prove:

1. mission creation;
2. deterministic MissionSpec validation;
3. policy decision recording;
4. capability grant issuance;
5. lease activation;
6. lease-use reservation;
7. task state transition;
8. transactional event ledger append;
9. outbox dispatch after commit;
10. checkpoint creation;
11. process restart;
12. aggregate state replay.

**Acceptance evidence:**

- database/event snapshots;
- replay hash or normalized state comparison;
- tests proving failed transactions dispatch no authoritative event;
- tests proving revoked leases fail immediately before effect dispatch;
- test proving duplicate idempotency keys do not duplicate state transitions.

### M0-B — Read-only driver proof

Add exactly one driver with no write authority.

The driver receives a narrow work order containing:

- one repository-inspection task;
- repository-read lease;
- read-only filesystem policy;
- no network unless explicitly required;
- context slice with provenance/disclosure metadata;
- expected inspection artifacts;
- token/time budgets;
- termination conditions.

The driver may return only:

- DriverObservation;
- DriverArtifactCandidate;
- DriverReceiptCandidate;
- DriverProgressSignal;
- DriverClaimProposal.

CAPT validates and converts accepted candidates into EvidenceRecords and ClaimRecords.

**Acceptance evidence:**

- attempted authoritative CAPT event injection is rejected;
- attempted write is denied;
- driver cancellation and inspection work;
- restart reconciles driver-run state;
- read-only findings remain attributable to the driver and source files.

### M0-C — Governed isolated repository write

Implement the canonical scenario:

> Inspect a repository, modify one file in an isolated worktree, run verification, and prepare—but do not push—a commit.

Required sequence:

1. receive and normalize mission;
2. establish explicit no-push/no-deploy constraints;
3. create read and isolated-worktree-write grants;
4. compile `inspect → propose → authorize → apply → test → verify → report` tasks;
5. issue a narrow driver work order;
6. run static command/tool analysis before write execution;
7. reserve capability use;
8. apply one isolated write;
9. record effect receipt and finalize lease use;
10. capture diff, hashes, command, exit status, and test output as evidence;
11. independently verify diff target, hashes, and test status;
12. allow only `change verified locally in isolated worktree`;
13. reject `pushed`, `merged`, `deployed`, and `published` claims;
14. checkpoint state;
15. restart and resume without repeating the write;
16. reconcile any indeterminate operation before retry.

**Acceptance evidence:**

- complete event stream;
- worktree diff and hashes;
- capability grant, lease, reservation, consumption, and finalization records;
- verification results;
- ClaimGuard decision;
- restart/recovery test;
- no remote side effect.

## 6. ExecutionDriver interface requirements

The driver interface must support at least:

```text
describe
submit
inspect
cancel
resume
reconcile
```

`submit()` returning a single final result is insufficient for long-running or recoverable execution.

The driver host must:

- validate driver descriptors and version compatibility;
- issue only narrow context and authority;
- isolate driver credentials and environment;
- translate driver output into untrusted candidate types;
- enforce run correlation and operation fingerprints;
- persist external run identifiers;
- reconcile after restart or lost connection;
- reject unknown authoritative event names from drivers.

## 7. Persistence requirements

For M0, use one transactional store unless a repository constraint requires otherwise.

The store must support:

- aggregate optimistic concurrency;
- ordered per-stream event versions;
- global sequence or deterministic dispatch ordering;
- command deduplication by idempotency key;
- transactional outbox;
- checkpoint manifests;
- artifact/evidence references;
- schema migration/version tracking.

Do not claim exactly-once external effects. Target **effectively-once behavior** through idempotency, reservation/finalization, receipts, and reconciliation.

## 8. Security review requirements

Before M0-C is accepted, test:

- revoked lease race;
- expired lease at dispatch;
- scope widening attempt;
- driver event forgery;
- command injection;
- filesystem escape;
- symlink/path traversal;
- environment/credential leakage;
- duplicate dispatch;
- crash after side effect but before receipt commit;
- malicious artifact/evidence path;
- context disclosure violation;
- false test-success claim;
- forbidden push/network attempt.

## 9. Verification rules

Every completion statement must be classified as one of:

- verified fact;
- observed but unverified;
- inference;
- contradicted;
- inconclusive;
- not tested.

Implementation agents must not claim:

- tests passed without test output and exit status;
- replay is deterministic without a repeated-state comparison;
- an external side effect did not occur without inspecting receipts/state;
- a driver is replaceable until a second conformance-compatible driver or a driver substitution test exists;
- production readiness from M0 proof gates.

## 10. Triple-recursion review applied to this workflow

### Pass 1 — Construct

The initial workflow translated the architecture into schemas, generated bindings, invariants, conformance tests, and M0-A/M0-B/M0-C proof gates.

### Pass 2 — Adversarial review

The workflow was challenged for these likely failure modes:

- generating types before mapping existing CAPT contracts;
- freezing TypeScript as the canonical source despite the Python runtime;
- building the full repo-write flow before proving replay and aggregate ownership;
- treating driver output as trusted runtime events;
- claiming exactly-once semantics across external tools;
- omitting revocation races and indeterminate-effect recovery;
- using broad arbitrary-object fields in security-critical schemas;
- coupling M0 to a distributed event broker;
- asserting driver replaceability after integrating only one driver.

### Pass 3 — Reconcile

Corrections incorporated:

- Gate 0 baseline mapping is mandatory;
- language-neutral schemas precede generated TS/Python bindings;
- implementation is staged through M0-A, M0-B, and M0-C;
- candidate driver outputs are distinct from authoritative CAPT records;
- effectively-once semantics replace unverifiable exactly-once claims;
- capability revocation, reservation/finalization, and reconciliation are explicit;
- security-critical payloads require discriminated unions;
- one transactional local runtime is the M0 topology;
- replaceability remains unproven until substitution evidence exists.

## 11. Definition of done

This workflow is complete only when:

- baseline mapping exists;
- required ADRs are accepted;
- language-neutral schemas validate;
- TypeScript and Python bindings generate reproducibly;
- cross-language fixtures agree;
- conformance tests cover authority, replay, capability lifecycle, driver distrust, and claim integrity;
- M0-A passes with restart/replay evidence;
- M0-B passes with a read-only untrusted driver;
- M0-C passes the isolated repository-edit scenario;
- failures and residual risks are documented;
- no unsupported production claim is made.
