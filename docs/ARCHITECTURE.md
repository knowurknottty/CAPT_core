# ARCHITECTURE — CAPT Core

Status: RECOVERED + consolidated (knowledge archaeology pass, 2026-07-30)
This document is the implementation-and-intellectual map entry point. It does NOT
replace `docs/CAPT_CANON.md` (constitution) or `architecture/registry.yaml`
(capability catalog). It summarizes both for contributors.

## Layered model (from CAPT_CANON)
- **Layer 3 — Memory**: MemoryEngine, CSG, Episodic/Semantic/Procedural/Prospective
  memory, Context Builder, Search, Deduplicate, Normalize, Trust, Secrets, AntiToken.
- **Layer 4 — Knowledge**: Knowledge Bubbles, KHSB, Curator.
- **Layer 5 — Trust**: Trust Engine, Evidence Engine, Provenance, ClaimGuard,
  Proof Engine, Proof Ledger, IMMU.
- **Layer 6 — Execution**: Lifecycle Manager, Session Store, Procedure Store,
  Manager, CTP, CLI, Runtime SDK.
- **Layer 8 — Governance**: Governance layer (CTP-wrapped audited actions).
- **Layer 9 — Skills**: Skill Foundry, Plugin SDK, Bundled Skills.
- **Layer 10 — Learning**: core learning, Consolidation-as-Learning, Continuous
  Learning, OUROBOROS.
- **Layer 11 — Hermes Plugin**: plugin interface.

## Public surface (six-pillar, ADR-0008)
The public API is organized as six pillars; internal layers need not map 1:1 to
packages. Stable packages (PUBLIC_API_MANIFEST_V0.5.json): capt_solo, contextpack,
core, ctp, khsb, lifecycle, memory, plugin. Experimental: engines, learning,
research.

## Implementation status (from architecture/registry.yaml + matrix)
SHIPPED in v0.5 baseline (`be4b0da`):
- MemoryEngine (complete), CSG (complete, in memory/csg.py), Semantic/Procedural/
  Prospective memory (complete), Context/Search/Dedupe/Normalize/Trust/Secrets/
  AntiToken (complete), Evidence Engine (capt_solo.evidence, complete), VSI
  (capt_solo.verification, complete), CTP (capt_solo.ctp, complete), KHSB
  (capt_solo.khsb, complete), Foundry/Proof (capt_solo.foundry, complete),
  CLI (capt_cli.py, complete), Plugin (capt_solo.plugin, complete).

CONCEPTUAL (documented, not in code):
- ClaimGuard, Knowledge Bubbles (wrapper), Governance (wrapper), Proof Ledger,
  IMMU, Autobiographical Memory, Synchronization.

MISSING / RESEARCH (registry "missing", owner PORT-or-exclude):
- Reasoning Core sub-lobes: CIG, HDR, META, CONSC, QIPC, RYS Bridge, NEDA,
  Cognitive Loop, HMC, ENGRAM, DREAM, FILT, FSR, PLAST, ALLO, OUROBOROS, +30.
- CAPTLANG compiler (external package), PULSE LLM gateway (optional plugin).

## Conceptual vs implemented (the two maps)
1. **Implementation map**: what exists in code today (above, SHIPPED list).
2. **Intellectual map**: every idea developed during the project — see
   `TREASURE_CHEST.md`, `CONCEPT_EVOLUTION.md`, `ARCHITECTURAL_PATTERNS.md`.

## Design patterns (reusable, not isolated)
See `ARCHITECTURAL_PATTERNS.md`: validator gates, governance transactions,
capability registry, receipt systems, provenance tracking, VSI state-binding,
plugin boundaries, degradation-aware language.

## Related documents
- `docs/CAPT_CANON.md` — constitution (highest authority).
- `docs/CANONICAL_ARCHITECTURE.md` — ownership matrix.
- `architecture/registry.yaml` — capability catalog with status.
- `docs/PUBLIC_ARCHITECTURE.md` — six-pillar public model.
- `docs/PUBLIC_API_STABILITY.md` — stability tiers.
- `docs/release/BRANCH_CENSUS.md`, `ARCHITECTURE_INVENTORY.md` — v0.5 census.
- `docs/TREASURE_CHEST.md` — recovered intellectual assets.
