# ADR-0006 — Evidence over implementation

- **Title:** Evidence over implementation
- **Status:** Accepted
- **Date:** 2026-07-26
- **Context:** When architecture, implementation, and historical documentation disagree, code was sometimes treated as self-justifying authority, or forensic claims as fact.
- **Decision:** Add invariant **I-15 — Evidence over implementation**: disagreements are resolved through explicit evidence and a recorded architectural decision. Existing code is never self-justifying architectural authority. A violation of any invariant requires cited ID, evidence of necessity, explicit owner approval, recorded exception, and canonical doc update.
- **Evidence:** Issue #5 Phase 3 directive; forensic corpus contradictions noted in BASELINE_EVIDENCE_REPORT (module counts, version divergence).
- **Consequences:** Registry/implementation drift fails fitness test I-15. Divergence must be represented by an ADR or tracked exception in ARCHITECTURAL_DEBT.
- **Alternatives considered:** Trust code as authority (rejected: enables silent redefinition); trust forensic doc as authority (rejected: I-14).
- **Related invariants:** I-10, I-11, I-14, I-15 (this ADR establishes I-15).
- **Supersedes:** none.
- **Superseded by:** none.
