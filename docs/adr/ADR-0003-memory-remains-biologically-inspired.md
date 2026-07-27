# ADR-0003 — Memory remains biologically inspired

- **Title:** Memory remains biologically inspired
- **Status:** Accepted
- **Date:** 2026-07-26
- **Context:** CAPT's memory architecture uses hippocampus/holographic/consolidation analogues (HMC, ECHO, ENGRAM, DREAM). A prior forensic audit called some of these "metaphorical" or "redundant" and recommended simplification.
- **Decision:** Biological/cognitive terminology is retained as CAPT's design language. Where a mapping is analogical, it is documented as analogical; where it is algorithmically faithful, it is implemented faithfully. Subsystems are not deleted or collapsed because an audit called them metaphorical.
- **Evidence:** Issue #5 architecture-preservation rules; CANONICAL_ARCHITECTURE conflict #8; CAPT_CANON I-14.
- **Consequences:** HMC/ECHO/ENGRAM/DREAM remain canonical Layer 3/10 subsystems. Research-grade modules (CONSC, FILT, FSR) keep biological names but are isolated as research/optional.
- **Alternatives considered:** Strip biological terminology (rejected: violates owner intent and issue preservation rules).
- **Related invariants:** I-14.
- **Supersedes:** none.
- **Superseded by:** none.
