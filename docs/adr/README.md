# Architecture Decision Records — CAPT

This directory holds accepted Architecture Decision Records (ADRs) for CAPT.
ADRs are the durable record of architectural decisions. They are referenced by
`architecture/registry.yaml` (field `owning_adrs`) and by `docs/CAPT_CANON.md`
invariants.

## Format

Every ADR uses a stable structure:

- Title
- Status (Accepted / Deprecated / Superseded)
- Date
- Context
- Decision
- Evidence
- Consequences
- Alternatives considered
- Related invariants
- Supersedes
- Superseded by

## Index

| ADR | Title | Status |
|-----|-------|--------|
| ADR-0001 | Architecture governs implementation | Accepted |
| ADR-0002 | Ontology precedes knowledge, memory, trust, governance | Accepted |
| ADR-0003 | Memory remains biologically inspired | Accepted |
| ADR-0004 | Canonical, reference, and current implementations are distinct | Accepted |
| ADR-0005 | Local-first; optional network transports | Accepted |
| ADR-0006 | Evidence over implementation | Accepted |
| ADR-0007 | Owner release decisions for the public boundary | Accepted |
| ADR-0008 | Six-pillar public architecture | Accepted |
| ADR-0009 | Canonical evidence ownership | Accepted |
| ADR-0010 | Public API stability tiers | Accepted |
| ADR-0011 | Public verification record terminology | Accepted |
| ADR-0012 | Future record convergence without v0.5 migration | Accepted |

## Rules

- ADRs are not changed once Accepted except by a new ADR that supersedes them.
- Implementation that would violate an ADR must cite the ADR ID, provide evidence
  of necessity, obtain explicit owner approval, and record the exception here.
- ADRs are evidence-based; they do not invent historical claims.
