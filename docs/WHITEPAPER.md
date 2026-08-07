# CAPT Core

## Local-First, Auditable, Model-Agnostic Cognitive Infrastructure

**Author:** Kirk Brown, Inversion Labs  
**Repository:** `knowurknottty/CAPT_core`  
**Status:** Public architecture and v0.5 reference implementation whitepaper  
**Version:** 2.0

---

## Abstract

Most AI systems are organized around a model endpoint. Memory, tools, workflow state, verification, and governance are then attached as wrappers around a temporary inference session. That design is useful for prototypes, but it makes durable continuity depend on one model, one vendor, one runtime, or one opaque transcript.

CAPT Core takes the opposite approach. It separates persistent cognition from transient inference. Models remain valuable reasoning components, but they do not own durable memory, execution authority, evidence, recovery state, or the system of record.

This repository ships two complementary public surfaces:

1. **CAPT Solo API** — the local-first in-process reference implementation for memory, CTP, KHSB, and proof-governed domain services.
2. **CAPT Runtime Harness** — the authenticated local lifecycle and execution service that owns EventStore persistence, checkpoint/restart continuity, Runtime Memory Governor policy, ContextPack construction, TaskResolver, DriverHost, and bounded external-driver execution.

The core thesis is simple:

> The model is a component, not the system.

---

## 1. The Architectural Problem

A model session is temporary. Context windows are bounded. Providers change. Tool interfaces drift. Hosted services can disappear or alter terms. A system that binds memory, identity, execution history, and authority to one inference session cannot reliably preserve continuity or accountability.

The missing layer is not another model. It is persistent cognitive infrastructure that remains stable while inference components change.

CAPT Core keeps durable responsibilities outside the model:

- persistent local memory;
- bounded working context;
- authoritative runtime events;
- operational transaction receipts;
- evidence and verification;
- capability lifecycle;
- checkpoint and recovery state;
- tool and driver boundaries;
- human approval, revocation, and final authority.

## 2. Design Principles

### 2.1 Inference is transient

Models generate, classify, summarize, plan, and reason. Their output is useful, but it is not authoritative system state merely because it is fluent or confident.

### 2.2 Durable state belongs outside the model

Memory, evidence, lifecycle state, and execution history must remain usable when a model, vendor, or runtime changes.

### 2.3 Consequential actions require bounded execution

State-changing work requires authenticated commands, transaction boundaries, idempotency, receipts, evidence, checkpointing, and recovery semantics.

### 2.4 Verification requires preserved evidence

Code presence, imports, generated prose, or a successful-looking response are not sufficient proof. Verification must identify the exact claim, evidence, execution environment, and limitation.

### 2.5 Human authority remains external

Humans retain authority to inspect, approve, revoke, export, migrate, repair, and remove persistent state and capabilities.

### 2.6 Reachability must be stated honestly

CAPT distinguishes source presence, packaging, importability, internal runtime use, API availability, operator availability, local real-process proof, and hosted-CI proof.

---

## 3. CAPT Core, CAPT Solo, and the Runtime Harness

**CAPT Core** is the architecture and project.

**CAPT Solo** is the local-first reference implementation and supported in-process API package.

**CAPT Runtime Harness** is the governed execution and lifecycle service shipped with CAPT Solo.

These names describe distinct responsibilities. CAPT Solo's API is not the same thing as the runtime harness, and an external compatibility client is not the runtime itself.

Hermes is one possible external caller. It remains outside CAPT authority and reaches CAPT through a bounded compatibility surface.

---

## 4. Architecture Overview

```text
Application code
    |
    +--> capt_solo.api
    |       +--> Memory Engine
    |       +--> CTP
    |       +--> KHSB
    |       +--> Proof / Capability Registry / ClaimGuard
    |       +--> Skill Foundry / Workflow Proof / Knowledge Bubbles
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

The architecture deliberately separates durable authority from inference. External model output enters as untrusted data until the runtime records, verifies, and accepts it through a governed path.

---

## 5. Persistent Memory and Bounded Context

### 5.1 CAPT Solo Memory Engine

The Memory Engine stores persistent local knowledge in SQLite. Records can include namespace, tags, provenance, confidence, metadata, import/export state, backup, and integrity information.

This subsystem is exposed through the CAPT Solo API and related memory surfaces.

### 5.2 Runtime Memory Governor

The Runtime Memory Governor is a separate subsystem. It owns token accounting, trigger policy, ContextPack construction, repeated rotation behavior, stale-pack rejection, budget enforcement, restart continuity, and dispatch gating.

Persistent memory and bounded working context are related, but they are not the same component.

### 5.3 ContextPack

ContextPack is the bounded working context authorized for runtime use. External drivers receive only the permitted slice or reference defined by the runtime contract, not unrestricted access to durable memory.

---

## 6. EventStore and CTP

### 6.1 EventStore

EventStore owns the authoritative ordered runtime event ledger. It provides durable event persistence, sequence ordering, replay, and integrity evidence for runtime lifecycle and verification state.

### 6.2 Cognitive Transaction Protocol

CTP records operational transaction boundaries and recovery state, including begin, validate, commit, abort, note, transaction and correlation identifiers, idempotency keys, receipts, and incomplete-transaction recovery.

CTP is not the authoritative runtime EventStore ledger. It is an operational transaction and recovery journal.

This distinction prevents one subsystem from being credited with guarantees supplied by another.

---

## 7. KHSB Coordination

KHSB is the current local, in-process coordination bus. It supports publish/subscribe and request/reply behavior with timeout and acknowledgement semantics.

KHSB is not currently durable, cross-process, or distributed. Those remain possible future extension seams rather than present implementation claims.

---

## 8. Governed Runtime Execution

The standalone harness provides a local authenticated service and installed CLI surface.

The runtime includes authenticated service access, command classification, idempotent command handling, TaskResolver, DriverHost, capability and scope enforcement, EventStore persistence, checkpoint creation, restart continuity, resume without repeating completed execution, evidence and VerificationResult persistence, ClaimGuard decisions, and bounded external drivers.

The currently proven Hermes-facing operator action is bounded read-only inspection. General unrestricted model-driven repository engineering is not claimed.

---

## 9. Proof-Governed Capabilities

Evidence is evaluated against declared requirements. A capability is not reported verified solely because code exists or a model says it succeeded.

Capabilities move through explicit lifecycle states such as candidate, validated, proven, verified, experimental, degraded, deprecated, and revoked.

ClaimGuard applies evidence and lifecycle state to completion and capability claims. Unsupported claims are downgraded rather than represented as verified.

Verification evidence must preserve process outcome, claim identity, supporting evidence identity, execution scope, environment, freshness, limitations, and failure state.

---

## 10. Skill Foundry, Workflows, and Knowledge Bubbles

Skill Foundry moves skills through explicit generation, validation, review, approval, publication, deprecation, and revocation states.

A workflow composed from individually verified components is not automatically verified. Composition creates new compatibility, permission, rollback, and environmental risks.

Imported Knowledge Bubbles enter quarantine and are validated manifest-first before approval or installation.

These systems make portable procedures and knowledge inspectable without treating portability as automatic trust.

---

## 11. Governance and Human Authority

Consequential actions require named actors, bounded commands or transactions, preserved evidence, and auditable outcomes.

Humans retain authority to approve, deny, revoke, inspect, export, migrate, repair, delete, and refuse capability changes.

CAPT is designed to increase human agency, not transfer final authority to an inference model.

---

## 12. Security Model

CAPT Core is local-first by design.

The base runtime requires no cloud service, external database, Docker deployment, or provider API key for core operation. Optional model drivers may require network access or provider credentials.

The current public runtime does **not** claim encryption at rest, multi-user authentication or authorization, protection from a compromised host account, cryptographically signed audit history, or universal isolation for every optional external tool or model runtime.

Hosted security CI explicitly reports a degraded optional-dependency state when the private anti-token-extraction package cannot be verified. A green workflow is therefore not represented as full optional-dependency provenance proof.

---

## 13. Recovery and Idempotency

The runtime is designed to make interruption and replay inspectable.

Current evidence covers ordered EventStore persistence, duplicate-command classification, unchanged ledger head on duplicate replay, checkpoint creation, restart and socket cleanup, resume without repeating prior execution, and preserved driver-run and verification identities.

CAPT claims effectively-once governed behavior where evidenced. It does not make a universal exactly-once claim for arbitrary external side effects.

---

## 14. Release Evidence and Truth Classes

CAPT v0.5 separates evidence into source-supported, automated-test-supported, installed-wheel-supported, local real-process-supported, hosted-CI-supported, and deferred or unproven classes.

The release evidence records exact wheel hashes, test matrices, skip reasons, runtime lifecycle evidence, requirement-to-evidence mappings, and limitations.

This distinction matters because a local external-model run and a hosted deterministic CI run prove different things.

---

## 15. Current v0.5 Implementation

The current release includes CAPT Solo API and local memory services; CTP and KHSB; proof-governed Foundry subsystems; authoritative EventStore runtime history; authenticated standalone harness lifecycle; Runtime Memory Governor and ContextPack rotation; DriverHost and bounded external-driver composition; checkpoint, restart, idempotency, and no-repeat resume behavior; installed-wheel verification; Python 3.10 and 3.12 hosted CI; explicit security degradation reporting; and versioned release evidence.

CAPT Core v0.5 is suitable for local evaluation and development within the documented boundaries. Higher-trust deployment requires additional host, identity, isolation, encryption, and cryptographic controls.

---

## 16. Non-Goals and Honest Boundaries

CAPT Core is not a claim that one model provides complete cognition, a replacement for operating-system security, a guarantee that every external tool is safe, a cryptographic trust system in its current public form, a distributed multi-user platform, a claim that every packaged subsystem is operator-facing, or a claim that Hermes is the CAPT runtime.

Reserved seams are not implementation claims.

---

## 17. Evaluation Principles

CAPT should be evaluated on system properties rather than model eloquence: memory integrity, provenance preservation, ContextPack boundary enforcement, transaction recoverability, EventStore integrity, idempotency, checkpoint and restart continuity, evidence sufficiency, claim downgrade correctness, capability-state correctness, authority attribution, and audit completeness.

A convincing output is not equivalent to a verified system state.

---

## 18. Future Direction

Future work may include encrypted backup and export, cryptographically signed receipts and attestations, stronger process isolation, multi-user authorization profiles, additional model and multimodal drivers, alternate durable stores, distributed coordination transports, and cross-model continuity demonstrations.

These are directions, not current implementation claims.

---

## 19. Conclusion

The model-centric architecture of contemporary AI systems places too much durable responsibility inside a transient inference component.

CAPT Core separates those concerns.

The model generates.

CAPT remembers.

CAPT governs.

CAPT verifies.

CAPT records.

CAPT recovers.

Humans remain authoritative.

> The model is a component, not the system.

---

## Public Documentation

- [Project overview](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Design rationale](DESIGN.md)
- [Security boundaries](SECURITY.md)
- [API reference](API.md)
- [Runtime and integration guide](PLUGIN_GUIDE.md)
- [Roadmap](ROADMAP.md)
- [v0.5 release evidence](../release_evidence/v0.5/release-readiness.md)
