# ADR-0012 — Future Record Convergence Without v0.5 Migration

- **Status:** Accepted
- **Date:** 2026-07-29
- **Supersedes:** none
- **Related:** ADR-0002, ADR-0004, ADR-0006, ADR-0009, ADR-0011

## Context

Identity, checkpoint, receipt, evidence, and verification records overlap, but a
release-hardening cycle is the wrong time to rewrite persisted schemas or public
imports.

## Decision

The post-v0.5 design direction includes:

- `SubjectRef`, `ActorRef`, `StateRef`, and `ScopeRef`;
- a versioned `CheckpointRecord` envelope with typed payloads;
- a versioned `ReceiptEnvelope` with typed payloads;
- narrow subject, verifier, policy-evaluation, and attestation-store interfaces;
- integrity-covered extension fields suitable for future CRP mapping.

These are design targets, not v0.5 public implementations. Existing
`MissionCheckpoint`, lifecycle `Checkpoint`, CTP `Receipt`,
`GovernanceReceipt`, continuity receipts, VSI, and verification records remain
the operative types.

No persisted record is migrated by this ADR. Any implementation requires:

1. a versioned schema;
2. compatibility adapters;
3. forward and rollback behavior;
4. installed-artifact tests;
5. a separate ADR if canonical ownership changes.

## Evidence

The architecture review identified overlapping types while the P0 mission
explicitly prohibits rushed record convergence and schema migration.

## Consequences

- CRP compatibility can evolve through stable references and envelopes.
- v0.5 remains backward-compatible.
- The roadmap is explicit without creating a speculative subsystem.

## Alternatives Considered

- Implementing a universal envelope immediately was rejected as high-risk,
  unnecessary for release integrity, and contrary to the P0 boundary.

## Related Invariants

I-03, I-06, I-08, I-11, I-12, I-15.
