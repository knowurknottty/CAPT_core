# CAPT Core Design Rationale

**Why CAPT exists, in plain language first.**

CAPT Core treats an AI model as one replaceable component inside a larger system. The model can generate and reason, but CAPT owns the durable parts: memory, state, authority, evidence, recovery, and continuity.

## In one minute

Most AI systems keep too much important state inside a temporary model session. That makes memory fragile, execution hard to inspect, and claims difficult to verify.

CAPT Core moves those durable responsibilities outside the model:

- memory persists locally
- consequential actions use transaction boundaries
- capabilities move through explicit lifecycle states
- claims require evidence
- humans retain approval and revocation authority

The result is a system that can survive model changes without losing its operating history.

## The design in three principles

### 1. Durable state belongs outside the model

Model context is temporary and bounded. CAPT memory is persistent, inspectable, portable, and governed independently of any model invocation.

A memory record can carry provenance, confidence, namespace, tags, and metadata. That makes memory a durable system object rather than residue from a conversation window.

### 2. Consequential actions need evidence and boundaries

Actions such as publishing, installing, approving, deprecating, and revoking are not ordinary text generation.

The Cognitive Transaction Protocol provides explicit begin, validate, commit, abort, and note events, along with idempotency, correlation, receipts, and recovery.

The Proof Engine evaluates evidence against declared requirements. Verification is a lifecycle state supported by evidence, not a marketing adjective.

### 3. Humans remain authoritative

CAPT Core is designed to increase human agency, not replace it.

Humans retain the authority to approve, revoke, inspect, export, migrate, and remove persistent state and capabilities. The runtime should earn trust through evidence and accountable behavior rather than demand trust because a model produced an answer.

## Why local-first

Local-first operation reduces mandatory dependence on remote services and keeps persistent cognitive state under direct control.

It does **not** mean universally isolated or automatically secure. It means the base runtime can operate without a required cloud service, remote database, or provider credential.

## Why memory is separate

Persistent memory must survive model replacement, provider changes, runtime migration, and tool evolution.

This avoids binding identity, continuity, or authority to one opaque model session.

## Why CTP exists

The Cognitive Transaction Protocol makes state-changing work inspectable and recoverable.

It provides:

- explicit transaction boundaries
- idempotency protection
- correlation identifiers
- append-only receipts
- crash recovery
- audit history

This prevents silent double-application and makes interrupted work discoverable.

## Why proof exists

A system should not claim a capability merely because code exists or a model says it succeeded.

The Proof Engine evaluates evidence against declared requirements. Capabilities move through explicit states such as candidate, validated, proven, verified, degraded, deprecated, and revoked.

## Why ClaimGuard exists

AI systems can overstate completion or capability. ClaimGuard applies evidence and lifecycle state to claims, downgrading unsupported assertions and preserving the scope of failures.

A platform-specific failure, for example, should not become a false global-revocation claim.

## Why governance exists

Publishing, installing, approving, deprecating, and revoking capabilities changes what the system is permitted to do.

CAPT governance requires named actors, CTP transaction boundaries, and append-only audit records for consequential actions.

## Why workflows need independent proof

A chain of individually verified components is not automatically a verified workflow.

Composition introduces new risks:

- incompatible inputs and outputs
- permission unions
- privilege escalation
- dependency failures
- rollback conflicts
- environmental mismatch

Therefore workflows carry independent proof.

## Why knowledge packages are quarantined

Portable knowledge and skill packages can contain unsafe permissions, secret material, malformed manifests, or dangerous instructions.

Knowledge Bubbles are imported into quarantine and validated manifest-first before approval or installation.

## What CAPT Core is not

CAPT Core is not:

- a claim that one model can provide complete cognition
- a replacement for operating-system security
- a guarantee that every external tool is safe
- a cryptographic trust system in its current public form
- the entirety of the private CAPT research architecture

It is the public, inspectable foundation for building persistent, governed, model-independent intelligence systems.

## Go deeper

- [Architecture](ARCHITECTURE.md)
- [Security boundaries](SECURITY.md)
- [API reference](API.md)
- [Whitepaper](WHITEPAPER.md)
