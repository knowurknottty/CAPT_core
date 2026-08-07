# CAPT Core Architecture

CAPT Core is a model-agnostic cognitive infrastructure architecture. This repository contains **CAPT Solo**, the local-first reference implementation, and the packaged **CAPT Runtime Harness** used for governed execution and lifecycle control.

The architecture keeps persistent cognition outside any single model, vendor, or runtime. Models provide inference. CAPT owns durable memory, governed state, evidence, recovery, bounded execution, and human authority.

## Architectural principles

| Principle | Current v0.5 implementation |
|---|---|
| Model independence | External models are replaceable drivers or clients. |
| Local-first operation | No required cloud service or external database. |
| Stable in-process boundary | Integrators use `capt_solo.api`. |
| Governed execution boundary | Operators and clients use the authenticated `capt harness` service. |
| Authoritative runtime history | EventStore owns ordered runtime events and replay. |
| Operational transactions | CTP records transaction receipts and recovery state. |
| Bounded context | Runtime Memory Governor constructs and rotates ContextPack state. |
| Evidence before trust | Verification requires declared evidence and preserved outcomes. |
| Explicit governance | Consequential actions are attributed, bounded, and auditable. |
| Honest reachability | Packaged, importable, internal, API, and operator-facing states are distinguished. |

## Two public surfaces

### 1. CAPT Solo API

`capt_solo.api` is the supported in-process integration surface. It exposes local memory, CTP, KHSB, and proof-governed domain services without requiring callers to depend on internal implementation paths.

### 2. CAPT Runtime Harness

The installed `capt harness` CLI communicates with an authenticated local RuntimeService. The harness owns lifecycle control, EventStore persistence, TaskResolver, DriverHost, checkpoint/restart continuity, idempotency, and bounded external-driver execution.

These surfaces are complementary, not interchangeable.

## Runtime topology

```text
Application code
    |
    +--> capt_solo.api
    |       +--> Memory Engine
    |       +--> CTP
    |       +--> KHSB
    |       +--> Foundry / Proof / ClaimGuard
    |
Operator or external compatibility client
    |
    +--> capt harness CLI
            +--> authenticated RuntimeService
            +--> EventStore
            +--> Runtime Memory Governor
            +--> ContextPack
            +--> TaskResolver
            +--> DriverHost
            +--> Checkpoint / Recovery
            +--> bounded external drivers
```

Hermes is one possible external compatibility client. It is not the runtime, the system of record, or the owner of CAPT authority.

## Authority and responsibility

### EventStore

EventStore is the authoritative ordered runtime event ledger. It provides durable event persistence, sequence ordering, replay, and chain-integrity evidence for the standalone runtime.

### Cognitive Transaction Protocol

CTP records operational transaction boundaries and recovery state, including begin, validate, commit, abort, note, idempotency, correlation, and receipts.

CTP does **not** replace EventStore as the authoritative runtime event ledger.

### CAPT Solo Memory Engine

The CAPT Solo Memory Engine is a SQLite-backed API subsystem for persistent local knowledge. It supports namespaces, tags, provenance, confidence, metadata, import/export, backup, and integrity checks.

### Runtime Memory Governor

The Runtime Memory Governor is a separate subsystem. It owns trigger policy, token accounting, ContextPack construction, rotation, budget enforcement, stale-pack rejection, and runtime dispatch gating.

### ContextPack

ContextPack is bounded working context produced under runtime policy. External drivers receive only the authorized slice or reference defined by the runtime contract, not unrestricted access to durable memory.

### KHSB

KHSB is a local, in-process coordination bus supporting publish/subscribe and request/reply behavior. It is not durable and is not a cross-process or distributed transport.

### DriverHost

DriverHost executes bounded external-driver operations under CAPT authority. Driver output remains untrusted until recorded, verified, and accepted through the governed evidence path.

The currently proven Hermes action is bounded read-only inspection. General unrestricted model-driven repository engineering is not claimed.

## Proof-governed subsystems

### Proof and verification

Evidence is evaluated against declared requirements. Source presence, imports, generated prose, or a successful-looking output are not sufficient proof by themselves.

### Capability Registry

Capabilities move through explicit lifecycle states such as candidate, validated, proven, verified, degraded, deprecated, revoked, and experimental.

### ClaimGuard

ClaimGuard prevents unsupported completion or capability claims from being represented as verified. Degradation remains scoped so a local or platform-specific limitation does not become a false global failure.

### Skill Foundry

Skill Foundry supports explicit generation, validation, review, approval, publication, deprecation, and revocation states. A generated skill is not trusted merely because generation completed.

### Knowledge Bubbles

Imported Knowledge Bubbles are quarantined and validated manifest-first before approval or installation.

### Workflow Proof

A composed workflow carries independent proof. Verification is not inherited automatically from individually verified components.

## Lifecycle and recovery

The standalone runtime provides:

- authenticated local service access;
- idempotent command handling;
- checkpoint creation;
- restart continuity;
- resume without repeating completed execution;
- EventStore replay;
- bounded driver dispatch;
- persisted evidence and verification records.

CAPT Solo API subsystems also provide local integrity, backup, import/export, and CTP recovery features. These are separate layers and should not be conflated.

## Reachability vocabulary

Public documentation uses these classifications:

- `SOURCE_PRESENT`
- `PACKAGED_ONLY`
- `IMPORTABLE_API`
- `API_ONLY`
- `INTERNAL_RUNTIME_SERVICE`
- `OPERATOR_FACING`
- `LOCAL_REAL_PROCESS_PROVEN`
- `HOSTED_CI_PROVEN`
- `DEFERRED`
- `UNPROVEN`

A class that imports is not automatically an operator feature. A local real-process proof is not automatically hosted-CI proof.

## Security boundaries

The current runtime assumes one trusted local operating-system user. It does not claim:

- encryption at rest;
- multi-user authorization;
- protection from a compromised host account;
- cryptographically signed audit history;
- universal isolation of every external tool or model runtime.

Optional drivers may require provider credentials or network access. The base CAPT runtime does not.

## Extension seams

Future implementations may add alternate memory backends, distributed transports, additional model drivers, encrypted exports, signed receipts, or stronger authorization. These are extension seams, not current implementation claims.

## Naming

- **CAPT Core** — architecture and project.
- **CAPT Solo** — local-first reference implementation and API package.
- **CAPT Runtime Harness** — governed execution and lifecycle service shipped with CAPT Solo.
- **External compatibility skill or driver** — client integration that remains outside runtime authority.
