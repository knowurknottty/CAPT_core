# ADR-0001 — Architecture governs implementation

- **Title:** Architecture governs implementation
- **Status:** Accepted
- **Date:** 2026-07-26
- **Context:** CAPT has accumulated code across many repositories (capt-solo, biocapt-ecosystem, frankencapt, capt-rys). Repository layout is an implementation snapshot, not the architecture. Without a governing rule, code changes silently redefine the system.
- **Decision:** The canonical architecture (`docs/CAPT_CANON.md`, `docs/CANONICAL_ARCHITECTURE.md`) is the source of truth. Implementation converges toward it. When code and architecture conflict, the code changes — not the architecture. Exceptions require cited invariant ID, evidence, owner approval, and a recorded exception.
- **Evidence:** Issue #5 governing directive; `docs/CAPT_CANON.md` I-10/I-11; Phase 1–2.5 accepted inventory and architecture commits (33cc37a, a2f0630, 8057f03).
- **Consequences:** Subsystem canonical homes are permanent unless re-canonicalized via an ADR. Repo location does not determine ownership.
- **Alternatives considered:** Treat current repo layout as canonical (rejected: contradicts owner intent and issue #5).
- **Related invariants:** I-10, I-11, I-13, I-14.
- **Supersedes:** none.
- **Superseded by:** none.
