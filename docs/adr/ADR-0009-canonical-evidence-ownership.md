# ADR-0009 — Canonical Evidence Ownership

- **Status:** Accepted
- **Date:** 2026-07-29
- **Supersedes:** none
- **Related:** ADR-0002, ADR-0004, ADR-0006

## Context

The tree contains multiple evidence-like records created for different
subsystems. Without explicit ownership, new integrations can select a
specialized record accidentally and create further semantic drift.

## Decision

`capt_solo.evidence.EvidenceRecord` is the canonical evidence record for new
public evidence workflows.

Existing evidence-like types remain supported and are classified as follows:

| Type | Classification | v0.5 treatment |
|---|---|---|
| `capt_solo.evidence.EvidenceRecord` | canonical, provisional public API | use for new cross-subsystem evidence |
| `capt_solo.verification.VerificationEvidence` | stable specialized type | verifier command/output payload |
| `capt_solo.foundry.proof.Evidence` | stable specialized compatibility type | Foundry proof-store record |
| `capt_solo.knowledge.evidence.EvidenceRecord` | provisional compatibility type | Knowledge-store view; no new general use |
| `capt_solo.continuity.runtime.ContinuityEvidence` | provisional specialized type | continuity-policy evidence |
| `capt_solo.evidence.providers.OperationalEvidence` | provisional adapter type | provider snapshot before canonicalization |
| `capt_solo.memory.interfaces.SourceEvidence` | internal protocol type | memory adapter boundary |

No type is removed or silently reinterpreted in v0.5. Conversion and migration
work requires a later ADR and compatibility tests.

## Evidence

The canonical type carries an explicit claim, evidence class, provenance-bearing
source, status, confidence, verification reference, invalidation links, scope,
and serialization contract. It is covered by core, workspace, CLI, integration,
and adversarial tests.

## Consequences

- Documentation can name one default evidence record without breaking Foundry,
  Knowledge, Continuity, or Memory.
- Specialized stores keep their persisted schemas.
- Future adapters have an explicit target for convergence.

## Alternatives Considered

- Immediate record unification was rejected because it would risk persisted
  state and compatibility.
- Treating Foundry Evidence as canonical was rejected because it is scoped to
  capability proof rather than general provenance and invalidation.

## Related Invariants

I-02, I-04, I-08, I-12, I-15.
