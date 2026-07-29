# ADR-0008 — Six-Pillar Public Architecture

- **Status:** Accepted
- **Date:** 2026-07-29
- **Supersedes:** none
- **Related:** ADR-0001, ADR-0002, ADR-0004, ADR-0006

## Context

The canonical registry contains 70 implementation and research subsystems across
the constitutional layer model. That inventory is valuable for governance but
is too large to serve as the public mental model. The v0.5 architecture review
found that CAPT's existing release value can be described by a smaller set of
durable concepts without deleting or physically reorganizing subsystems.

## Decision

CAPT's public conceptual architecture has six pillars:

1. **Identity & Scope**
2. **Evidence**
3. **Verification**
4. **Context**
5. **Transactions**
6. **Governance**

The public stack is presented as adapters over services over the CAPT
Verification Kernel over storage and cryptographic ports.

`architecture/registry.yaml` remains the machine-readable implementation and
research catalogue. The constitutional L0-L11 layer model remains the canonical
ownership map. Services such as Memory, Workspace, Knowledge, Foundry, KHSB,
Lifecycle, and domain engines use or implement pillar capabilities without
becoming additional public primitives.

This decision does not require six physical Python packages in v0.5.

## Evidence

- The reviewed tree already has concrete Evidence, VSI, ContextPack, CTP, and
  governance implementations.
- The architecture review at
  `docs/CAPT_CORE_V0.5_ARCHITECTURE_EVOLUTION_REVIEW.md` maps existing code to
  the six pillars.
- External adoption profiles can use current packages independently without a
  breaking repository reorganization.

## Consequences

- Public onboarding leads with verification rather than subsystem count or
  biological analogies.
- Internal registry and research terminology remain inspectable and governed.
- A future package reorganization requires a separate compatibility decision.

## Alternatives Considered

- Publishing the 70-subsystem catalogue as the primary architecture was
  rejected because it obscures the release's verification value.
- Performing an immediate six-package refactor was rejected as destabilizing.

## Related Invariants

I-02, I-06, I-08, I-10, I-11, I-15.
