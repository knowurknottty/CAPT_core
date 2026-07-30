# CAPT Core Design Rationale

CAPT Core exists because the model is not the whole intelligence system.

A model can generate, classify, plan, or reason, but durable cognition requires
structure outside the model: memory, state, authority, proof, governance,
recovery, and continuity.

## The model is a component

CAPT Core treats models as interchangeable inference components. Persistent state
must survive model replacement, provider changes, runtime migration, and tool
evolution.

This avoids binding identity, memory, or authority to one opaque model session.

## Why local-first

Local-first operation reduces mandatory dependence on remote services and keeps
the user's persistent cognitive state under direct control.

Local-first does not mean universally isolated or automatically secure. It means
the base runtime can operate without a required cloud service, remote database,
or provider credential.

## Why memory is separate

Model context is temporary and bounded. CAPT memory is persistent, inspectable,
portable, and governed independently of any model invocation.

A memory record can carry provenance, confidence, namespace, tags, and metadata.
This makes memory a durable system object rather than an accidental residue of a
conversation window.

## Why CTP exists

Consequential actions need transaction boundaries.

The Cognitive Transaction Protocol provides explicit begin, validate, commit,
abort, and note events; idempotency; correlation; receipts; and recovery. This
creates inspectable execution history and prevents silent double-application.

## Why proof exists

A system should not claim a capability merely because code exists or a model says
it succeeded.

The Proof Engine evaluates evidence against declared requirements. Verification is
a lifecycle state supported by evidence, not a marketing adjective.

## Why ClaimGuard exists

AI systems often overstate completion or capability. ClaimGuard applies evidence
and lifecycle state to claims, downgrading unsupported assertions and preserving
the scope of failures.

A macOS-only failure, for example, should not become a false global-revocation
claim.

## Why governance exists

Publishing, installing, approving, deprecating, and revoking capabilities changes
what the system is permitted to do.

CAPT governance requires named actors, CTP transaction boundaries, and append-only
audit records for consequential actions.

## Why workflows need independent proof

A chain of individually verified components is not automatically a verified
workflow.

Composition introduces new risks: incompatible inputs, permission unions,
escalation, dependency failures, rollback conflicts, and environmental mismatch.
Therefore workflows carry independent proof.

## Why knowledge packages are quarantined

Portable knowledge and skill packages can contain unsafe permissions, secret
material, malformed manifests, or dangerous instructions.

Knowledge Bubbles are imported into quarantine and validated manifest-first before
approval or installation.

## Why deterministic history matters

Persistent systems must support post-event inspection and recovery. Append-only
transaction journals, explicit lifecycle states, evidence records, and audit
entries make state transitions explainable.

## Why humans remain authoritative

CAPT Core is designed to increase human agency, not replace it.

Humans retain the authority to approve, revoke, inspect, export, migrate, and
remove persistent state and capabilities. The runtime should earn trust through
evidence and accountable behavior rather than demand trust because a model
produced an answer.

## What CAPT Core is not

CAPT Core is not:

- a claim that one model can provide complete cognition
- a replacement for operating-system security
- a guarantee that every external tool is safe
- a cryptographic trust system in its current public form
- the entirety of the private CAPT research architecture

It is the public, inspectable foundation for building persistent, governed,
model-independent intelligence systems.
