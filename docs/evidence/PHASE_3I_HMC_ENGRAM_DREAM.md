# Phase 3I — HMC / ENGRAM / DREAM Canonicalization

**Branch:** integration/full-public-architecture
**Date:** 2026-07-26
**Issue:** #5
**Preceded by:** Phase 3H (commit e2c59d4)

## Objective
Canonicalize HMC, ENGRAM, DREAM in CAPT_core. Per the directive: "lawful source
evaluation, clean implementation where required."

## Licensing gate [L] — resolved by clean implementation
The registry lists `current_path: modules/hmc_mobile.py`, `engram_mobile.py`,
`dream_consolidator_mobile.py` — these files do NOT exist in CAPT_core. External
implementations exist in the separate `biocapt-ecosystem` repo. Per the licensing
gate [L] and the directive, external source was **NOT copied**. Clean canonical
implementations were written in CAPT_core from the architecture definitions.

## Implementations (all backed by MemoryEngine; reuse canonical fields; I-12)
- `capt_solo/memory/hmc.py` — `HolographicMemoryCompressor`: deterministic
  holographic compression of memory content into a fixed-dimension vector via a
  stable token-hash projection (superposition/interference). Deterministic
  (same content -> same vector), supports cosine similarity + nearest-neighbor
  search. Compression is LOSSY by design (bounded, I-07) and documented; no
  exact reconstruction claim. No network, no hidden state.
- `capt_solo/memory/engram.py` — `EngramStore`: durable memory traces with
  explicit consolidation lifecycle (RAW -> CONSOLIDATING -> CONSOLIDATED ->
  PRUNED). Links to source episodes/evidence. State transitions are auditable
  (no silent change). Backed by MemoryEngine (namespace `engram`).
- `capt_solo/learning/dream.py` — `DreamConsolidator`: offline consolidation that
  turns RAW/CONSOLIDATING engrams into durable knowledge. Produces SUPPORTED
  knowledge ONLY when corroborating evidence exists; never silently VERIFIED
  (I-02 enforced, reusing Phase 3G KnowledgeStore/EvidenceStore). Deterministic,
  auditable, local. `capt_solo/learning/__init__.py` exposes it.

## Tests added
`tests/test_phase3i_hmc_engram_dream.py` (7):
- HMC deterministic compression
- HMC similarity (related > unrelated)
- HMC nearest-neighbor
- Engram store + consolidate lifecycle
- Engram list by state
- DREAM consolidation as learning (with corroborating evidence -> knowledge)
- DREAM withholds knowledge without evidence (I-02)

## Verification
- `pytest`: 445 passed (was 438).
- `verify_runtime.py`: 46/46 pass (unchanged).

## Result
HMC/ENGRAM/DREAM are now canonical, tested CAPT_core subsystems implemented
cleanly (no external source copied). Ready for Phase 3J (Continuous Learning
foundation).
