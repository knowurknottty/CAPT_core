# ARCHITECTURAL DEBT REGISTER

**Phase:** 3A.5 — companion to CANONICAL_ARCHITECTURE and registry
**Branch:** integration/full-public-architecture
**Date:** 2026-07-26
**Issue:** #5

This register records architectural debt derived from the accepted implementation
matrix (commit 33cc37a) and baseline evidence (commit 33cc37a / a2f0630). It is
NOT a substitute for fixing work that can be completed now. Items with no owner
gate are fixed in later phases; gated items wait for the four approved gate types.

Machine-readable companion: `architecture/debt.yaml`.

## Debt items

| ID | Subsystem | Layer | Problem | Evidence | Impact | Severity | Maturity gap | Blocked capability | Remediation | Deps | Owner gate | Status | Target phase | Verification |
|----|-----------|-------|---------|----------|--------|----------|--------------|-------------------|------------|------|-----------|--------|-------------|-------------|
| DEBT-001 | CTP | L6 | `capt_solo/ctp/` gitignored + absent from tree; fresh clone cannot import | BASELINE_EVIDENCE_REPORT B1; `git ls-files capt_solo/ctp/` empty | verify_runtime + pytest fail on clean clone | critical | disconnected→Beta | transaction journal unavailable | Restore verified wheel source into tree (Phase 3B.1) | none | none (capt-solo own code) | open | 3B | import succeeds; ctp.* checks pass |
| DEBT-002 | Version identity | all | pyproject 0.1.0 vs wheel/docs 0.4.1 vs tag v0.4.0 | BASELINE B2 | ambiguous release identity | high | n/a | reproducible builds | Resolve to v0.4.1 via evidence (Phase 3B.2) | none | [C] if two equally authoritative histories | open | 3B | single version across metadata/docs/tag |
| DEBT-003 | Episodic/ECHO | L3 | SessionStore is current episodic impl; ECHO canonical interface not adopted | MATRIX M2; CANONICAL L3.3 | episodic semantics incomplete (ring buffer/retention) | medium | partial→Beta | canonical ECHO API | Canonicalize ECHO, merge SessionStore (Phase 3D) | DEBT-001 | none | open | 3D | ECHO API tests pass |
| DEBT-004 | Proof Ledger | L5 | Approximated by ProofEngine+governance; no explicit ledger | MATRIX M9; CANONICAL L5.6 | ledger integrity not explicit | medium | Beta→Production | tamper-evident ledger | Merge explicit ledger (Phase 3G) | none | none | open | 3G | ledger append/verify tests |
| DEBT-005 | Autobiographical | L3 | No implementation anywhere | MATRIX M6 | autobiographical layer absent | medium | Concept→Beta | narrative self | Implement integration layer (Phase 3F) | DEBT-003 | none | open | 3F | autobiographical tests |
| DEBT-006 | Replay | L3 | Only skill/docs references; no module | MATRIX P4 | replay not first-class | medium | Concept→Beta | deterministic replay | Canonicalize replay API (Phase 3E) | none | none | open | 3E | replay fixtures |
| DEBT-007 | Consent | L3 | No implementation | MATRIX M7 | sensitive ops lack consent gate | medium | Concept→Beta | local consent ledger | Implement consent model (Phase 3E) | none | [S] privacy review at integration | open | 3E | consent tests |
| DEBT-008 | Synchronization | L3 | No implementation; abstraction canonical | MATRIX Synchronization | cross-instance reconcile absent | medium | Planned→Beta | local FS/export sync | Implement transport-neutral contract + local transports (Phase 3E) | none | abstraction un-gated; transports [S] | open | 3E | sync round-trip tests |
| DEBT-009 | HMC | L3 | Absent from capt-solo; external only | MATRIX M1 | holographic memory absent | high | Research→Beta | VSA compression | Canonicalize HMC (Phase 3I) | none | none (clean impl) | open | 3I | HMC round-trip benchmark |
| DEBT-010 | ENGRAM | L3 | Absent from capt-solo; external only | MATRIX M3 | durable encode absent | high | Research→Beta | engram records | Canonicalize ENGRAM (Phase 3I) | none | none | open | 3I | engram tests |
| DEBT-011 | DREAM | L3/L10 | Absent; external only | MATRIX M4 | consolidation loop absent | high | Research→Beta | consolidation | Canonicalize DREAM (Phase 3I) | DEBT-009,DEBT-010 | none | open | 3I | DREAM cycle tests |
| DEBT-012 | IMMU | L5 | Absent; external only | MATRIX X3 | immune verification absent | medium | Research→Beta | bubble quarantine verify | Adopt IMMU (Phase 3G/3K) | none | none | open | 3G/3K | immu tests |
| DEBT-013 | Continuous Learning | L10 | Absent; external candidate | MATRIX X14 | governed learning absent | medium | Research→Beta | feedback→proposal loop | Establish foundation (Phase 3J) | none | none (no longer orphan) | open | 3J | learning proposal tests |
| DEBT-014 | Research adapters | L2/L10 | CIG/HDR/META/NEDA/PLAST/ALLO/FILT/FSR/OUROBOROS not integrated | MATRIX X1–X14 | optional cognition absent | low | Research→Experimental | bounded adapters | Add optional adapters (Phase 3K) | none | [B] for FILT/FSR/NEDA/ALLO/OUROBOROS | open | 3K | adapter smoke tests |
| DEBT-015 | PULSE/RYS/cloud-sync | L7/L11 | Network capabilities not in baseline | MATRIX X6/X11 | external gateways absent | low | Research→opt-in | LLM/bridge/cloud | Safe abstract contracts + mocks (Phase 3L) | none | [S]+[B] for PULSE/RYS | open | 3L | boundary tests, disabled by default |
| DEBT-016 | Memory coherence | L3 | No cross-module memory coherence check (forensic gap) | BASELINE P5 | incoherent memory possible | low | partial→Beta | coherence check | Add coherence check (Phase 3C) | none | none | open | 3C | coherence tests |
| DEBT-017 | Identity explicitness | L0 | Identity only implicit in semantic.py | CANONICAL L0.1 | identity scoping weak | low | Beta→Production | explicit identity store | Make Identity explicit (Phase 3C) | none | none | open | 3C | identity tests |

## Severity summary
- critical: DEBT-001 (CTP)
- high: DEBT-002, DEBT-009, DEBT-010, DEBT-011
- medium: DEBT-003, DEBT-004, DEBT-005, DEBT-006, DEBT-007, DEBT-008, DEBT-012, DEBT-013
- low: DEBT-014, DEBT-015, DEBT-016, DEBT-017

## Owner-gated debt (only the four approved types)
- [C]: DEBT-002 (if two equally authoritative release histories)
- [S]: DEBT-007 (consent privacy), DEBT-008 transports (LAN/P2P/cloud), DEBT-015 (PULSE/RYS)
- [B]: DEBT-014 (FILT/FSR/NEDA/ALLO/OUROBOROS), DEBT-015 (PULSE/RYS boundary)
- [L]: none currently (CTP is capt-solo own code; HMC/ENGRAM/DREAM to be clean-implemented, not copied)

All other debt is resolved autonomously in Phases 3B–3M.
