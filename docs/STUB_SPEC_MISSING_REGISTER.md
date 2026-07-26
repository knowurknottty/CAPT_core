# STUB / SPEC-ONLY / MISSING-COMPONENT REGISTER

**Phase:** 1 — companion to FULL_ARCHITECTURE_IMPLEMENTATION_MATRIX.md
**Baseline:** `knowurknottty/CAPT_core` @ `main` `abeff5c`
**Branch:** `integration/full-public-architecture`
**Date:** 2026-07-26
**Rule applied:** issue #5 governing directive — anything spec-only / stubbed / placeholder / partial / disconnected / documented-but-absent / implemented-elsewhere-but-omitted / exposed-without-tests must be COMPLETED, not removed. Forensic recommendations are NOT adopted.

Status values: stub / spec-only / partial / disconnected / missing / missing-external / documented-absent

---

## 1. Disconnected (built but not in committed tree)

| id | component | evidence | impact | required action | owner decision |
|----|-----------|----------|--------|-----------------|----------------|
| D1 | CTP (`capt_solo/ctp/`) | wheel has `ctp/journal.py` (8048 B) + `__init__.py`; `git ls-files capt_solo/ctp/` empty; `.gitignore` has `ctp/`; `api.py`/`verify_runtime.py`/`foundry/governance.py` import it → fresh clone ImportError | verify_runtime + pytest fail (16 collection errors) | Restore `ctp/` from wheel source into committed tree (or change gitignore + import strategy) | **OWNER: approve committing ctp/ (currently gitignored)** |

---

## 2. Partial (present but incomplete vs full architecture)

| id | component | what exists | what is missing | required completion | owner decision |
|----|-----------|-------------|-----------------|---------------------|----------------|
| P1 | Episodic memory | `lifecycle/sessions.py` (572) + session tables | forensic "ECHO" = 90-day ring buffer w/ time-travel branching; capt-solo has sessions but no explicit ring-buffer/retention window semantics verified | confirm SessionStore covers ECHO semantics or port ECHO ring buffer | **OWNER: map-to-SessionStore vs port ECHO** |
| P2 | Compression (memory) | AntiToken char-compression (273 LOC, fidelity guards) | forensic: "no explicit summarization layer found in code" — holographic/semantic summarization absent | decide if summarization compression required for public release | **OWNER: required?** |
| P3 | Identity | `lifecycle/semantic.py` (7 refs), `engine.py` (1) | no explicit identity model/table | define identity model or confirm out-of-scope | **OWNER** |
| P4 | Replay | docs + capt-recovery skill mention replay | no dedicated replay API/module | implement replay API or document as recovery-only | **OWNER: dedicated subsystem?** |
| P5 | Memory coherence | none found | forensic: "no cross-module memory coherence check found" | add coherence check or confirm not required | **OWNER** |

---

## 3. Missing — named in issue #5, absent from capt-solo

| id | component | external evidence (if any) | in capt-solo? | required action | owner decision |
|----|-----------|---------------------------|---------------|-----------------|----------------|
| M1 | HMC (Holographic Memory Core) | `biocapt-ecosystem/.../hmc_mobile.py` (Rust accel) | NO | PORT into memory layer OR keep external w/ adapter | **OWNER: port vs external** |
| M2 | ECHO (Episodic buffer) | `biocapt-ecosystem/.../echo_mobile.py` | NO | PORT or map to SessionStore | **OWNER** |
| M3 | ENGRAM (long-term encode) | `biocapt-ecosystem/.../engram_mobile.py` | NO | PORT or fold into MemoryEngine consolidation | **OWNER** |
| M4 | DREAM / consolidation | `biocapt-ecosystem/.../dream_consolidator_mobile.py`, `dream_cycle_rpc_mobile.py` | NO (only lifecycle transitions) | PORT consolidation loop OR confirm SessionStore consolidation suffices | **OWNER** |
| M5 | Holographic Memory | see M1 (HMC) | NO | see M1 | **OWNER** |
| M6 | Autobiographical memory | not in biocapt scan either | NO | PORT or confirm out-of-scope | **OWNER: include?** |
| M7 | Consent | not found in biocapt scan | NO | PORT or confirm consent at runtime boundary | **OWNER: required?** |
| M8 | Synchronization | not found in biocapt scan | NO | PORT or confirm local-first single-instance | **OWNER: sync required?** |
| M9 | Proof Ledger (explicit) | approximated by ProofEngine + governance_audit | NO (explicit) | confirm sufficiency OR add explicit ledger | **OWNER: explicit ledger?** |
| M10 | Skill Radar | forensic registry `SKILL_RADAR` (biocapt) | NO | PORT or fold into SkillFoundry | **OWNER** |

---

## 4. Missing — external-only components from forensic corpus (not in capt-solo)

Recorded per issue requirement to inventory "every component found in the forensic corpus." All status = missing-external. None adopted as recommendations.

| id | component | external path | owner decision |
|----|-----------|---------------|----------------|
| X1 | NEDA | biocapt-ecosystem modules | **OWNER: port vs exclude** |
| X2 | QIPC | biocapt-ecosystem | **OWNER** |
| X3 | IMMU (immune/constitution; verifies bubbles) | biocapt-ecosystem | **OWNER: port vs map to trust** |
| X4 | CONSC (Φ) | biocapt-ecosystem | **OWNER: metaphorical? exclude?** |
| X5 | PLAST (Hebbian/BCM) | biocapt-ecosystem | **OWNER: port vs fold into consolidation** |
| X6 | PULSE (LLM gateway) | biocapt-ecosystem | **OWNER: external boundary** |
| X7 | CIG (causal inference) | biocapt-ecosystem | **OWNER** |
| X8 | HDR (hyperdim reasoning) | biocapt-ecosystem | **OWNER** |
| X9 | META (metacognition) | biocapt-ecosystem | **OWNER** |
| X10 | ALLO (allostatic) | biocapt-ecosystem | **OWNER** |
| X11 | RYS (recursive yield / CAPT-RYS bridge) | biocapt-ecosystem / AIM-CAPTRYS | **OWNER** |
| X12 | FILT (attentional filter, DISABLED `__slots__` bug) | biocapt-ecosystem | **OWNER: fix+port or exclude** |
| X13 | FSR (feedback regulator, DISABLED `__slots__` bug) | biocapt-ecosystem | **OWNER** |
| X14 | +30 registry modules (AIM, ATT, SENS, PCFE, IRIS, SYNC, NDS, EXEC, INHIB, ITC, MOTOR, TSCC, CREAT, BELIEF_GRAPH, CAUSAL_RSN, ANALOGICAL, CONCEPT_ALG, TEMPORAL_RSN, EMERGENCE_DET, CURIOSITY, EPISTEMIC, VALUE_ALIGN, TOM, ACTIVE_INF, COGNITIVE_LOOP, SWARM_DECOMP, AGENT_ROUTER, TOOL_SYNTH, SKILL_RADAR, BUG_BOUNTY, HOMEOSTASIS/STRESS/RECOV, MFO, SWC, SCF, ZKC, CONSTITUTION, AUTONOMY, LEARNING, ADAPTATION, OUROBOROS) | biocapt-ecosystem registry (46 total) | **OWNER: triage each** |
| X15 | CAPTLANG compiler (WASM codegen, 30 modules) | Biocapt-ecosystem-fullcaptlang | **OWNER: external build tool boundary** |

---

## 5. Documented-but-absent / spec-only within capt-solo

| id | item | evidence | note |
|----|------|----------|------|
| S1 | Replay API | docs/API.md, SKILL.md mention; no module | spec-only (P4) |
| S2 | Cross-module memory coherence | forensic gap; no code | missing (P5) |
| S3 | Explicit summarization compression | forensic: "documented compression may be aspirational" | spec-only (P2) |

---

## 6. Stubs / placeholders found (must NOT remain)

| id | location | evidence | action |
|----|----------|----------|--------|
| T1 | `capt_solo/ctp/` | absent from tree but imported → effective stub at package level (D1) | commit real impl from wheel |
| T2 | forensic "unified_modules/ 49 generated stubs — TODO: Add actual initialization logic" | external (biocapt-ecosystem) — NOT in capt-solo | out-of-scope for capt-solo; owner decides if any ported |
| T3 | forensic "capt/modules/continuous_learning_module.py (792 LOC, not in registry)" | external orphan | owner decides inclusion |

No `TODO`/empty-method stubs found inside committed capt-solo Python modules (verified by scan of `capt_solo/**/*.py`). The only "stub-like" condition is the missing `ctp/` package (D1).

---

## 7. Owner-decision backlog (stop conditions)

Per issue stop conditions, implementation halts for owner decision on:

1. **Public/private boundary** — which external bioCAPT modules (HMC, ECHO, ENGRAM, DREAM, NEDA, QIPC, IMMU, PULSE, RYS, +30) belong in the *public* CAPT release vs stay private/external.
2. **Licensing** — biocapt-ecosystem modules carry unspecified licenses vs capt-solo MIT; porting requires license reconciliation.
3. **Security exposure** — PULSE (LLM gateway), synchronization, consent handling introduce external/network surfaces; must be owner-approved before wiring into public runtime.
4. **Irreconcilable canonical behavior** — version divergence (B2) and CTP gitignore (B1) need owner sign-off on the fix.
5. **Metaphorical components** — CONSC/Φ, FILT/FSR disabled, "holographic" mapping: owner must confirm algorithmic-faithful vs analogical before porting.

All other inventory work is complete and committed; no autonomous deletion or renaming performed.
