# ADR-0002 — Ontology precedes knowledge, memory, trust, governance

- **Title:** Ontology precedes knowledge, memory, trust, governance
- **Status:** Accepted
- **Date:** 2026-07-26
- **Context:** Memory, Knowledge, Trust, and Governance each historically defined their own notions of claim/evidence/provenance/confidence. This produced incompatible duplicates and integration friction.
- **Decision:** A single shared ontology (Layer 0.5) defines these terms once (`docs/CAPT_CANON.md §4`). Memory/Knowledge/Trust/Governance consume ontology types; they do not independently redefine reality.
- **Evidence:** Phase 2.5 architecture refinement (commit 8057f03) adding Layer 0.5; CAPT_CANON I-12.
- **Consequences:** New subsystem types must reuse ontology definitions where a canonical type exists. Divergent local definitions fail fitness test I-12.
- **Alternatives considered:** Per-layer ontologies (rejected: caused duplication); no ontology (rejected: undefined vocabulary).
- **Related invariants:** I-12.
- **Supersedes:** none.
- **Superseded by:** none.
