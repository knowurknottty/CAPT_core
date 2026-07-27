# ADR-0004 — Canonical, reference, and current implementations are distinct

- **Title:** Canonical, reference, and current implementations are distinct
- **Status:** Accepted
- **Date:** 2026-07-26
- **Context:** "Current code" and "external code" were being conflated with architectural authority. Current code is not automatically the reference implementation; external code is not automatically permanently external.
- **Decision:** Three distinct concepts are tracked:
  - **Canonical Definition** — permanent architectural responsibility/contract.
  - **Reference Implementation** — currently accepted authoritative realization.
  - **Current Implementation** — code that exists now (complete/partial/obsolete/disconnected/divergent).
  Repository location does not determine canonical ownership. The registry (`architecture/registry.yaml`) records all three per subsystem.
- **Evidence:** Issue #5 terminology section; CANONICAL_OWNERSHIP_MATRIX columns (Current Repo/Path, Reference Implementation, Planned Public Repo).
- **Consequences:** Restoring CTP from the wheel makes the wheel source the current/reference implementation, but its canonical home (L6) is unchanged. Adopting HMC from biocapt-ecosystem requires a clean canonical implementation, not a blind copy.
- **Alternatives considered:** Treat current code as reference by default (rejected: enables silent redefinition).
- **Related invariants:** I-10, I-11, I-13.
- **Supersedes:** none.
- **Superseded by:** none.
