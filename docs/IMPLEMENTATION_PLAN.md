# IMPLEMENTATION PLAN — reorganized by architecture

**Phase:** 2 — refined plan (replaces repo-grouped plan from Phase 1)
**Baseline inventory:** accepted (commit `33cc37a`)
**Architecture:** `docs/CANONICAL_ARCHITECTURE.md`, `docs/CANONICAL_OWNERSHIP_MATRIX.md`
**Branch:** `integration/full-public-architecture`
**Date:** 2026-07-26

## Organization principle

Grouped by **CAPT layer** (Architecture / Infrastructure / Memory / Knowledge / Governance / Execution / Learning / External Interfaces), NOT by source repository. Each work item references its canonical home and proceeds autonomously unless it hits one of the four owner gates (public/private boundary, licensing uncertainty, security exposure, irreconcilable canonical behavior).

## Owner-gate legend
- `[B]` public/private boundary
- `[L]` licensing uncertainty (external bioCAPT source → MIT reconciliation)
- `[S]` security exposure
- `[C]` irreconcilable canonical behavior

---

## 0. Architecture (this phase — done)
- CANONICAL_ARCHITECTURE.md, CANONICAL_OWNERSHIP_MATRIX.md committed. No runtime change.

## 1. Infrastructure (foundational, autonomous)
- **INF-1** Restore `capt_solo/ctp/` from verified wheel source into committed tree (fix `.gitignore` or relocate). Canonical home L6. No `[B/L/S/C]` — capt-solo's own code. Evidence: wheel `capt_solo/ctp/journal.py` (8048 B). Re-run verify_runtime + pytest → green.
- **INF-2** Set canonical version (resolve `[C]`): pyproject `0.1.0` vs wheel/docs `0.4.1` vs tag `v0.4.0`. Owner picks; agent applies + tags `v0.4.1`.
- **INF-3** Establish Constitution document (L1) + `Constitution.check()` hook consumed by Governance. Autonomous.

## 2. Memory (Layer 3 — canonicalize subsystems)
- **MEM-1** Adopt ECHO canonical episodic interface; merge `SessionStore` into it. Autonomous (capt-solo code).
- **MEM-2** Canonicalize HMC (holographic/FFT VSA) into `capt_solo/memory/hmc.py`; Rust accel as optional external package. `[L]` (source from biocapt-ecosystem — license reconcile before merge). numpy fallback mandatory.
- **MEM-3** Merge ENGRAM into MemoryEngine consolidation. `[L]`.
- **MEM-4** Canonicalize DREAM/Consolidation loop (L3+L10). `[L]`.
- **MEM-5** Design + implement Autobiographical Memory canonical interface (no prior impl). Autonomous.
- **MEM-6** Canonicalize Replay API (currently skill-only). Autonomous.
- **MEM-7** Make Identity explicit (L0) — table + scoping. Autonomous.
- **MEM-8** Design Consent ledger (L3, privacy-reviewed). `[S]` at integration (local-only, no network). Autonomous design; owner approves integration surface.
- **MEM-9** Synchronization — **deferred** to owner `[B]+[S]` ruling (network surface). No autonomous work until cleared.

## 3. Knowledge (Layer 4 — autonomous; already mostly complete)
- **KNOW-1** Knowledge Bubbles: add IMMU-style verification hook (merge IMMU canonical impl). `[L]` for IMMU source.
- **KNOW-2** KHSB: no change (complete). Add negative/concurrency tests per completion standard.
- **KNOW-3** Curator: no change (complete). Harden tests.

## 4. Trust (Layer 5 — autonomous + merges)
- **TRUST-1** Adopt IMMU as canonical verification/quarantine under Trust. `[L]`.
- **TRUST-2** Merge Proof Ledger into explicit ledger (ProofEngine + Governance audit). Autonomous (capt-solo code).
- **TRUST-3** Trust Engine / Evidence / Provenance / ClaimGuard: complete; add negative/security tests.

## 5. Execution (Layer 6 — autonomous)
- **EXEC-1** CTP restore (see INF-1). Re-wire Governance to use committed CTP.
- **EXEC-2** Lifecycle/Session/Procedure/Manager: complete; add fault-injection + crash-recovery tests (Phase 5 hardening).
- **EXEC-3** CLI / Runtime SDK: complete; add integration tests.

## 6. Reasoning (Layer 2 — adopt canonical impls; gates on boundary/licensing)
- **REAS-1** Adopt CIG canonical impl. `[L]`.
- **REAS-2** Adopt HDR (numpy; Rust accel optional external). `[L]`.
- **REAS-3** Adopt META. `[L]`.
- **REAS-4** Cognitive Loop adopt. `[L]`.
- **REAS-5** CONSC/Φ → research package. `[B]` owner includes?
- **REAS-6** QIPC → research package. `[B]`.
- **REAS-7** NEDA → research package. `[B]`.
- **REAS-8** FILT/FSR → research package; fix `__slots__` bugs if included. `[B]`.

## 7. Learning (Layer 10 — autonomous + gates)
- **LRN-1** Adopt Learning/Adaptation canonical impl. `[L]`.
- **LRN-2** Fold PLAST into consolidation. `[L]`.
- **LRN-3** Continuous Learning (orphan 792 LOC) → `[B]` include?
- **LRN-4** OUROBOROS → research package. `[B]`.

## 8. External Interfaces (Layer 11 — gates)
- **EXT-1** CAPTLANG compiler → external package (build tooling). Autonomous (no runtime impact).
- **EXT-2** RYS Bridge → external/optional plugin. `[B]+[S]`.
- **EXT-3** PULSE LLM gateway → optional plugin. `[B]+[S]` (network/LLM).
- **EXT-4** Hermes Plugin Interface — complete (capt-solo).

## 9. Governance (Layer 8 — autonomous)
- **GOV-1** Governance complete; depends on CTP restore (INF-1).
- **GOV-2** Release Gates (verify_runtime/doctor/verify) — extend with new subsystem checks as each is canonicalized.

## 10. Skills (Layer 9 — autonomous)
- **SKL-1** Skill Foundry complete; merge Skill Radar capability. `[L]` for Radar source.
- **SKL-2** Plugin SDK / Bundled Skills complete; add tests.

---

## Recommended first implementation PR (after architecture approval)

**PR-A (Infrastructure + Memory core, autonomous except version `[C]`):**
1. INF-1: restore `capt_solo/ctp/` from verified wheel → gates green (no owner gate; capt-solo's own code).
2. INF-2: apply owner-chosen canonical version + tag `v0.4.1` (`[C]` — needs owner pick, then agent applies).
3. MEM-1: adopt ECHO canonical interface, merge SessionStore (autonomous).
4. MEM-7: explicit Identity (autonomous).
5. TRUST-2: merge Proof Ledger (autonomous).
6. SKL-1 (partial): merge Skill Radar into Skill Foundry (autonomous; `[L]` cleared if Radar source license reconciled, else defer Radar portion).

This PR touches only CAPT_core-internal or capt-solo's-own code, adds tests per completion standard, and does not cross any `[B]/[S]` boundary. It is the safe, reviewable first step.

Subsequent PRs follow the layer order above, each gated only where a `[B]/[L]/[S]/[C]` flag applies.

## Autonomy boundary
- Autonomous: all items without a flag, plus INF-1, MEM-1/5/6/7, TRUST-2, EXEC-*, GOV-*, SKL-2, EXT-1/4.
- Stop for owner: every `[B]`, `[S]`, unresolved `[L]` (external source license), and `[C]` (version).
- No deletion/renaming of subsystems based on forensic opinion (architecture-preservation rules honored).
