# CAPT Core Architecture

CAPT Core is a model-agnostic cognitive infrastructure architecture. This
repository contains **CAPT Solo**, the local-first reference implementation for
individual developers.

The architecture keeps persistent cognition outside any single model, vendor, or
runtime. Models provide inference; CAPT Core provides durable memory, governed
state, transactional execution, proof, recovery, and human authority.

## Architectural principles

| Principle | Current implementation |
|---|---|
| Model independence | Models are external interchangeable components. |
| Local-first operation | No required cloud service or external database. |
| Stable public boundary | Integrators use `capt_solo.api`. |
| Deterministic execution | Storage and lifecycle transitions avoid hidden randomness. |
| Recoverable state | CTP journals support crash recovery and pending-transaction detection. |
| Evidence before trust | Verification requires declared evidence requirements. |
| Explicit governance | Consequential actions are attributed, bounded, and audited. |
| Portable state | SQLite and human-readable JSON exports remain inspectable. |
| Migration safety | Forward migrations are backup-gated and integrity-checked. |

## Runtime layers

```text
Hermes or local caller
        |
        v
capt_solo.plugin / CLI
        |
        v
capt_solo.api                     stable public surface
        |
        +--> memory               persistent knowledge and provenance
        +--> ctp                  transactions, receipts, idempotency, recovery
        +--> khsb                 in-process messaging
        +--> foundry              proof, registry, ClaimGuard, skills, bubbles
        +--> governance           audited consequential actions
```

## Public surface versus implementation

`capt_solo.api` is the sanctioned import boundary. It re-exports stable classes
and functions while hiding implementation details.

New capabilities should extend the public surface without forcing consumers to
import internal modules or depend on unstable paths. The package retains the
`capt_solo` namespace for compatibility even though the architecture is now
presented publicly as CAPT Core.

## Persistent memory

The Memory Engine uses SQLite and supports:

- namespaces and tags
- provenance and confidence
- metadata
- import/export
- backups
- integrity checks
- a semantic-search adapter seam

Memory is durable independently of any model session.

## Cognitive Transaction Protocol (CTP)

CTP provides append-only transactional execution with:

- begin, validate, commit, abort, and note events
- transaction and correlation IDs
- idempotency keys
- receipts
- replay and crash recovery
- pending-transaction detection

Journals are flushed on each write. `CTPRuntime.recover()` identifies transactions
without a final commit or abort event.

## KHSB

KHSB is the local in-process message bus. It supports publish/subscribe and
request/reply behavior with timeout and acknowledgement semantics.

The current public runtime does not claim a distributed KHSB transport.

## Proof-governed subsystems

### Skill Foundry

The Skill Foundry moves procedures through an explicit lifecycle:

```text
candidate -> generated -> validating -> validated -> reviewing
          -> approved -> published -> deprecated -> revoked
```

Approval and publication are distinct actions. Validation uses a 12-stage harness.

### Proof Engine

The Proof Engine stores evidence and aggregates it against declared requirements.
A capability, skill, or workflow is not reported verified without a satisfied
proof aggregate.

### Capability Registry

The registry is the source of truth for capability state. It distinguishes:

```text
candidate -> validated -> proven -> verified
```

It also represents degraded, deprecated, revoked, and experimental states.
Degradation records preserve reason, scope, triggering evidence, remediation, and
lifecycle transition history.

### ClaimGuard

ClaimGuard gates completion and capability claims. Unsupported claims are
downgraded rather than presented as verified. Degradation is scoped so a
platform-specific limitation is not misreported as a global failure.

### Knowledge Bubble Runtime

Knowledge Bubbles are portable governed packages. Imported bubbles are
quarantined by default and validated manifest-first before payload approval.

### Workflow Proof Engine

A composed workflow does not inherit verification from its components. It carries
independent proof for composition, compatibility, permissions, rollback behavior,
and execution boundaries.

### Governance layer

Consequential actions such as approval, publication, installation, deprecation,
and revocation run inside CTP transactions with a named actor and append-only
audit records. Anonymous governance actions are rejected.

## Data flow

```text
Hermes tool call
   -> CaptSoloPlugin tool wrapper
   -> capt_solo.api stable boundary
   -> proof-governed subsystem or core runtime
   -> Memory Engine / CTP / KHSB
   -> evidence, receipt, lifecycle, or audit record
```

## Recovery model

- CTP journals are append-only and flushed per write.
- Pending transactions are discoverable after interruption.
- SQLite integrity is checked with `PRAGMA integrity_check` plus referential checks.
- Schema migrations require a verified backup and receipt before applying.
- Failed backup or integrity validation aborts the migration.

## Thread safety

`MemoryEngine` uses a SQLite connection per instance. Callers should use one
engine per thread or provide external guarding. CTP and KHSB serialize mutations
with re-entrant locks within the process.

## Extension seams

The architecture reserves stable seams for future implementations, including:

- semantic/vector search adapters
- alternate memory backends
- distributed KHSB transports
- multi-agent federation using CTP correlation IDs
- additional model, audio, vision, and multimodal runtimes
- higher-trust cryptographic proof and signed audit layers

A reserved seam is not an implementation claim. See the repository and roadmap
for current capability status.

## Naming

- **CAPT Core** — the cognitive infrastructure architecture.
- **CAPT Solo** — the local-first reference implementation in this repository.
