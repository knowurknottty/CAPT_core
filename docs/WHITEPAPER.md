# CAPT Core

## Secure, Auditable, Model-Agnostic Cognitive Infrastructure

**Author:** Kirk Brown, Inversion Labs  
**Repository:** `knowurknottty/CAPT_core`  
**Status:** Public architecture and reference implementation whitepaper  
**Version:** Draft 1.0

---

## Abstract

Contemporary AI systems are commonly organized around a model endpoint. Memory, tool use, workflow state, verification, governance, and authority are often attached afterward as application-specific wrappers. This creates fragile systems whose continuity depends on one model, one vendor, one runtime, or one opaque session.

CAPT Core takes the opposite approach. It separates persistent cognition from transient inference. Models are treated as replaceable components inside a larger cognitive infrastructure that owns durable memory, state transitions, evidence, capability lifecycles, transactional execution, recovery, governance, and human authority.

This repository contains CAPT Solo, the local-first reference implementation of CAPT Core. The public runtime provides provenance-aware memory, an append-only Cognitive Transaction Protocol, in-process coordination, proof-governed capabilities, explicit skill and workflow lifecycles, claim verification, quarantine-first knowledge packages, migration safety, and inspectable audit history.

The core thesis is simple:

> The model is a component, not the system.

---

## 1. Problem Statement

Most AI products inherit their architecture from the model they call. The model becomes the apparent center of memory, identity, reasoning, tool authority, and continuity. This is convenient for prototypes but structurally weak for durable systems.

A model session is temporary. Context windows are bounded. Providers change. Tool interfaces drift. Runtimes fail. Hosted services can disappear or alter terms. A system that binds persistent cognition to one model or vendor cannot reliably preserve continuity, auditability, or user control.

The missing layer is not another model. It is persistent cognitive infrastructure that remains stable while inference components change.

CAPT Core addresses that missing layer by keeping the durable parts of cognition outside the model:

- persistent memory
- context and state management
- transactional execution
- capability lifecycles
- evidence and proof
- claim verification
- tool governance
- recovery and audit history
- human authority, consent, and revocation

---

## 2. Design Thesis

CAPT Core is based on five architectural claims.

### 2.1 Inference is transient

Models generate, classify, summarize, plan, and reason, but their internal state is not a dependable system of record. Model output is therefore treated as an input to governed infrastructure, not as authoritative state.

### 2.2 Memory must outlive the model

Persistent memory should remain usable when a model, vendor, or runtime is replaced. Memory must be inspectable, portable, provenance-aware, and governed independently of any inference call.

### 2.3 Consequential actions require transaction boundaries

Tool calls, capability changes, installation, publication, deprecation, and revocation are not ordinary text generation. They require explicit begin, validate, commit, abort, receipt, and recovery semantics.

### 2.4 Verification requires evidence

Code presence, model confidence, or a successful-looking message is not proof of capability. Verification must be supported by declared requirements and stored evidence.

### 2.5 Human authority must remain external to the model

Humans must retain authority to inspect, approve, revoke, export, migrate, and remove persistent state and capabilities. The system must earn trust through evidence and accountable behavior.

---

## 3. CAPT Core and CAPT Solo

**CAPT Core** is the architecture.

**CAPT Solo** is the local-first reference implementation contained in this repository.

The implementation package retains the `capt_solo` namespace for backward compatibility. The public architecture name reflects the broader purpose: persistent, governed cognitive infrastructure that is independent of any one harness or model.

CAPT Solo is deliberately constrained. It is designed for individual developers and local evaluation. It does not claim to be the entirety of the private CAPT research architecture, a distributed multi-user platform, or a cryptographic trust system.

---

## 4. Architecture Overview

```text
Hermes or local caller
        |
        v
capt_solo.plugin / CLI
        |
        v
capt_solo.api                     stable public surface
        |
        +--> Memory Engine        persistent knowledge and provenance
        +--> CTP Runtime          transactions, receipts, idempotency, recovery
        +--> KHSB                 in-process coordination
        +--> Foundry              proof, registry, ClaimGuard, skills, bubbles
        +--> Governance           audited consequential actions
```

The sanctioned integration surface is `capt_solo.api`. Internal modules may evolve while consumers continue to depend on a stable public boundary.

This separation is important. It prevents downstream users from coupling to implementation details and allows future capabilities to be added without breaking existing integrations.

---

## 5. Persistent Memory

The Memory Engine stores durable state in SQLite. Memory records support:

- namespaces
- tags
- provenance
- confidence
- metadata
- import and export
- backups
- integrity checks
- a semantic-search adapter seam

The purpose of this design is not merely storage. It turns memory into a first-class governed object.

A memory record can identify where it came from, how strongly it is trusted, which namespace owns it, and what metadata or tags apply. This makes memory portable and auditable rather than an accidental residue of a model context window.

Persistent memory remains independent of any model session. A model may read or propose memory, but the runtime owns the durable record.

---

## 6. Cognitive Transaction Protocol

The Cognitive Transaction Protocol, or CTP, provides append-only transactional execution.

CTP records:

- `begin`
- `validate`
- `commit`
- `abort`
- `note`

Each transaction can carry a transaction ID, correlation ID, idempotency key, metadata, receipts, and validation results.

The journal is append-only and flushed on each write. A transaction is finalized only when a commit or abort event exists. After interruption, recovery can identify incomplete transactions that never reached a final state.

This provides several guarantees:

- consequential actions have explicit boundaries
- duplicate application can be prevented through idempotency keys
- interrupted work can be detected
- execution history remains inspectable
- recovery does not depend on a model remembering what happened

CTP is the mechanism by which CAPT Core turns actions into governed state transitions rather than opaque side effects.

---

## 7. KHSB Coordination

KHSB is the current local, in-process message bus. It supports:

- publish and subscribe
- request and reply
- timeouts
- acknowledgements

In the public runtime, KHSB is intentionally not presented as a distributed transport. It provides local coordination while preserving a seam for future transports.

This is representative of CAPT Core's design discipline: reserve extension points without claiming implementations that do not yet exist.

---

## 8. Proof-Governed Capabilities

### 8.1 Proof Engine

The Proof Engine stores evidence and evaluates it against declared requirements.

Evidence can include type, producer, content hash, trust value, provenance, scope, and timestamp. Proof requirements define the evidence types, counts, and trust thresholds necessary for a scope.

A capability is not reported verified merely because code exists. Verification requires a satisfied proof aggregate.

### 8.2 Capability Registry

The Capability Registry is the source of truth for what CAPT Core can claim to do.

The primary lifecycle is:

```text
candidate -> validated -> proven -> verified
```

The registry also represents:

- experimental
- degraded
- deprecated
- revoked

Degradation records preserve reason, affected scope, triggering evidence, prior state, resulting state, remediation guidance, actor, timestamp, and transaction reference.

This prevents a vague pass/fail model and preserves the difference between local, platform-specific, and global failures.

### 8.3 ClaimGuard

ClaimGuard applies capability state and proof to completion claims.

Unsupported claims are downgraded rather than presented as verified. A platform-specific failure does not become a false global revocation. A partial result is not presented as complete.

ClaimGuard exists because language models are optimized to produce plausible answers, not to maintain release authority. CAPT Core therefore makes claim status a governed system function.

---

## 9. Skill Foundry

The Skill Foundry converts procedures into governed skill candidates and moves them through an explicit lifecycle:

```text
candidate -> generated -> validating -> validated -> reviewing
          -> approved -> published -> deprecated -> revoked
```

Approval and publication are distinct actions. Validation uses a 12-stage harness. Unsafe command patterns, secret patterns, disallowed permissions, and missing rollback strategies can block validation.

A skill is therefore not considered trustworthy because it was generated successfully. It must pass a controlled lifecycle with evidence, review, and explicit publication.

---

## 10. Knowledge Bubbles

Knowledge Bubbles are portable governed packages for claims, procedures, examples, provenance, permissions, and related metadata.

Imported bubbles are quarantined by default. Validation is manifest-first, before payload approval or installation.

This boundary exists because portable knowledge can include:

- unsafe permissions
- secret material
- malformed manifests
- dangerous instructions
- unsupported claims

A bubble moves through explicit lifecycle states such as imported, quarantined, validated, approved, and installed. Consequential transitions are governed and linked to CTP records.

---

## 11. Workflow Proof

A workflow composed from individually verified components is not automatically a verified workflow.

Composition introduces new risks:

- incompatible inputs and outputs
- permission union
- privilege escalation
- dependency failure
- rollback conflict
- environmental mismatch
- transaction-boundary mismatch

The Workflow Proof Engine therefore assigns independent evidence and lifecycle state to a composed workflow.

This prevents trust from being inherited blindly across composition boundaries.

---

## 12. Governance

Consequential actions such as approval, publication, installation, deprecation, and revocation run inside CTP transactions.

Governance requires:

- a named actor
- a target
- a reason
- a transaction boundary
- an append-only audit record

Anonymous governance actions are rejected.

This does not make the current runtime a complete authorization system. It does, however, make governance state explicit and auditable.

---

## 13. Security Model

CAPT Solo is local-first by design.

The base runtime:

- performs no required network egress
- requires no external database
- requires no Docker environment
- requires no API keys to operate
- stores state locally in SQLite and append-only journals

Integrity protections include:

- SQLite `PRAGMA integrity_check`
- referential checks
- append-only CTP journals
- idempotency enforcement
- backup-gated migrations
- proof-gated claims
- quarantine-first imports
- named-actor governance

The security model is intentionally explicit about its limitations.

The current public runtime does **not** provide:

- encryption at rest
- multi-user authentication or authorization
- cryptographic Knowledge Bubble signature verification
- cryptographically signed audit trails

Local-first reduces mandatory dependence on remote services, but it does not automatically make all data safe. Users must still apply appropriate filesystem permissions and avoid storing secrets in plaintext memory.

---

## 14. Migration and Recovery Safety

Forward migrations are backup-gated.

Before a schema bump, the runtime creates a backup using SQLite's backup mechanism, runs integrity checks, and records a receipt. If backup or integrity validation fails, the migration aborts rather than partially applying.

This is important because persistent cognitive systems accumulate state over time. Migration failure cannot be treated as a disposable application error. It must preserve recoverability and avoid silent corruption.

---

## 15. Data Model

The public data model includes persistent structures for:

- memories and tags
- schema versions
- proof evidence
- proof requirements
- capabilities
- degradation records
- skills
- workflow proofs
- governance audit entries
- knowledge bubbles
- CTP journal events

The data model is designed to make state transitions inspectable.

Evidence stores provenance and trust. Capabilities store lifecycle state and degradation. Governance records identify actors and linked transactions. Workflows preserve composition metadata and proof references. Bubbles retain validation reports and approval state.

This gives CAPT Core a durable substrate for accountability.

---

## 16. Human Authority and Data Sovereignty

CAPT Core is designed to increase human agency.

Humans retain authority to:

- approve
- revoke
- inspect
- export
- migrate
- delete
- deprecate
- repair
- refuse capability changes

Persistent state remains outside the model and under the user's control. The local-first reference implementation stores its state under a user-controlled directory and supports human-readable export.

The system should not demand trust because a model produced an answer. It should earn trust through inspectable state, explicit boundaries, evidence, and accountable behavior.

---

## 17. Model and Runtime Independence

CAPT Core does not define intelligence by a particular model.

Language, audio, vision, and future multimodal systems can be treated as interchangeable inference components. The durable architecture remains responsible for memory, governance, proof, transactions, and continuity.

This allows the system to survive:

- model replacement
- provider changes
- local or hosted runtime migration
- tool evolution
- interface changes

The architecture is intentionally harness-independent. Hermes is the current integration target in CAPT Solo, not a permanent architectural dependency of CAPT Core.

---

## 18. Non-Goals and Honest Boundaries

CAPT Core is not:

- a claim that one model can provide complete cognition
- a replacement for operating-system security
- a guarantee that every external tool is safe
- a cryptographic trust system in its current public form
- a distributed multi-user platform in CAPT Solo
- the entirety of the private CAPT research architecture

Reserved extension seams are not implementation claims.

Future-facing documentation should distinguish clearly between:

- implemented
- experimental
- reserved
- degraded
- deprecated
- revoked

This distinction is part of the architecture, not a documentation preference.

---

## 19. Current Public Implementation

The public runtime currently includes the v0.4 proof-governed architecture and v0.4.1 hardening work.

The repository includes:

- runtime implementation
- automated tests
- installer and uninstaller
- diagnostics
- one-command verification
- structured runtime checks
- architecture contracts
- machine-readable schemas
- security documentation
- data-model documentation
- extension and migration guides

The repository is under active public-release hardening. It is suitable for local evaluation and development, but users should review documented security limitations and verify the runtime in their own environment.

---

## 20. Future Direction

The architecture reserves seams for future work including:

- semantic and vector search adapters
- alternate memory backends
- distributed KHSB transports
- multi-agent federation using CTP correlation IDs
- additional model, audio, vision, and multimodal runtimes
- encrypted backup and export
- cryptographic package verification
- signed audit receipts
- higher-trust authorization layers

These are future directions, not current implementation claims.

---

## 21. Conclusion

The model-centric architecture of contemporary AI systems places too much durable responsibility inside a transient inference component.

CAPT Core separates those concerns.

The model generates.

CAPT remembers.

CAPT governs.

CAPT verifies.

CAPT records.

CAPT recovers.

Humans remain authoritative.

The result is a cognitive infrastructure designed to remain useful after the current model, vendor, runtime, and interface become obsolete.

> The model is a component, not the system.

---

## Appendix A: Public Documentation

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/DESIGN.md`
- `docs/SECURITY.md`
- `docs/DATA_MODEL.md`
- `docs/API.md`
- `docs/MIGRATIONS.md`
- `docs/PLUGIN_GUIDE.md`
- `docs/SKILL_GUIDE.md`
- `docs/EXTENDING.md`
- `docs/ROADMAP.md`

## Appendix B: Terminology

**CAPT Core** — the model-agnostic cognitive infrastructure architecture.  
**CAPT Solo** — the local-first reference implementation in this repository.  
**CTP** — Cognitive Transaction Protocol.  
**KHSB** — local in-process coordination bus in the current public runtime.  
**ClaimGuard** — evidence-aware claim gating and degradation layer.  
**Knowledge Bubble** — portable governed package with explicit validation and lifecycle state.  
**Proof Aggregate** — evaluation of stored evidence against declared requirements.  
**Capability Registry** — authoritative lifecycle state for runtime capabilities.
