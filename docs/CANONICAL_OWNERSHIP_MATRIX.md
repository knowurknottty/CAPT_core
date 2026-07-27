# CANONICAL OWNERSHIP MATRIX

**Phase:** 2.5 — companion to CANONICAL_ARCHITECTURE.md and CAPT_CANON.md
**Baseline inventory:** accepted (commit `33cc37a`); Phase 2 architecture accepted (commit `a2f0630`)
**Branch:** `integration/full-public-architecture`
**Date:** 2026-07-26
**Issue:** #5

## Column definitions

- **Component** — canonical subsystem name.
- **Canonical Home** — CAPT layer (L0–L11) where it permanently belongs.
- **Current Repo** — where the code lives today.
- **Current Path** — path in that repo.
- **Planned Public Repo** — where it will ship (CAPT_core / external package / optional plugin / research package / private).
- **Current Status** — complete / partial / disconnected / missing / spec-only (per accepted inventory).
- **Canonical Maturity** — Production / Beta / Experimental / Prototype / Research / Concept / Planned / Deprecated. Communicates implementation readiness independently from architectural importance.
- **Maturity Evidence** — why this maturity level (implementation evidence, not opinion).
- **Owner Decision** — none (autonomous) / specific gate required.

## Release Target vocabulary (Planned Public Repo)
- `CAPT_core` — ships in the public CAPT_core runtime.
- `external package` — separate published package, not in core runtime.
- `optional plugin` — opt-in plugin (may be external or core-contrib).
- `research package` — research/preview, not in stable public release by default.
- `private` — not for public release.

## Maturity vocabulary (Canonical Maturity)
- **Production** — complete per issue completion standard; verified.
- **Beta** — implemented/tested, not yet release-verified or API-stable.
- **Experimental** — implemented but unstable/limited; opt-in.
- **Prototype** — minimal working slice; interface may change.
- **Research** — research/preview form; not in stable public release.
- **Concept** — defined in architecture; no implementation.
- **Planned** — architecturally decided; implementation scheduled.
- **Deprecated** — architecturally retiring; migration path exists.

---

| Component | Canonical Home | Current Repo | Current Path | Planned Public Repo | Current Status | Canonical Maturity | Maturity Evidence | Owner Decision |
|-----------|---------------|-------------|-------------|---------------------|----------------|---------------------|-------------------|----------------|
| Identity | L0 Identity | capt-solo | lifecycle/semantic.py (implicit) | CAPT_core | partial | Beta | Implicit refs in semantic.py/engine.py; no explicit table/API yet → not Production. | none (autonomous: make explicit) |
| Ontology | L0.5 Ontology | (none) | — | CAPT_core | spec-only | Concept | Defined in CAPT_CANON §4; no code. | none |
| Constitution | L1 Constitution | (none) | — | CAPT_core | spec-only | Concept | Documented as invariant set (CAPT_CANON §2); no enforcement code. | none |
| Reasoning Core | L2 Reasoning | capt-solo | (implicit orchestration) | CAPT_core | partial | Beta | Orchestration implicit in lifecycle/foundry; no dedicated Reasoner class. | none |
| CIG (Causal Inference) | L2 Reasoning | biocapt-ecosystem | .../cig_mobile.py | CAPT_core | missing | Research | External research impl; not in capt-solo. | none (adopt canonical impl) |
| HDR (Hyperdim Reasoning) | L2 Reasoning | biocapt-ecosystem | .../hdr_mobile.py (+hdr.rs) | CAPT_core (Rust accel external pkg) | missing | Research | External impl + Rust; not adopted. | none (adopt; accel optional) |
| META (Metacognition) | L2 Reasoning | biocapt-ecosystem | .../meta_mobile.py | CAPT_core | missing | Research | External impl; not adopted. | none |
| CONSC (Φ / Global Workspace) | L2 Reasoning | biocapt-ecosystem | .../consc_mobile.py | research package | missing | Research | External research impl; metaphorical. | **boundary** |
| QIPC (Quantum-Inspired Consensus) | L2 Reasoning | biocapt-ecosystem | .../qipc_mobile.py (+qipc.rs) | research package | missing | Research | External research impl. | **boundary** |
| RYS Bridge | L2 Reasoning / L11 | biocapt-ecosystem / AIM-CAPTRYS | .../rys_mobile.py | external package / optional plugin | missing | Research | External impl; bridge to CAPT-RYS. | **boundary + security** |
| Cognitive Loop | L2 Reasoning | biocapt-ecosystem | registry COGNITIVE_LOOP | CAPT_core | missing | Research | External registry entry; not in capt-solo. | none |
| NEDA (Neural Event-Driven) | L2 Reasoning | biocapt-ecosystem | .../neda_mobile.py (+neda.rs) | research package | missing | Research | External impl. | **boundary** |
| MemoryEngine | L3 Memory | capt-solo | memory/engine.py | CAPT_core | complete | Production | 1364 LOC, 32 tables, SCHEMA_VERSION=4, test_memory + migration tests pass in-tree. | none |
| CSG | L3 Memory | capt-solo | memory/csg.py | CAPT_core | complete | Production | 375 LOC, test_v02_csg, verify_runtime. | none |
| Episodic Memory (ECHO) | L3 Memory | capt-solo (SessionStore) / biocapt-ecosystem (echo_mobile.py) | lifecycle/sessions.py / .../echo_mobile.py | CAPT_core | partial | Beta | SessionStore complete (572 LOC, test_v03_sessions) but ECHO canonical ring-buffer interface not adopted. | none (adopt ECHO, merge) |
| Semantic Memory | L3 Memory | capt-solo | lifecycle/semantic.py | CAPT_core | complete | Production | 153 LOC, semantic_index_metadata, tests. | none |
| Procedural Memory | L3 Memory | capt-solo | lifecycle/procedures.py | CAPT_core | complete | Production | 391 LOC, procedure_* tables, test_v03_procedures. | none |
| Prospective Memory | L3 Memory | capt-solo | lifecycle/prospective.py | CAPT_core | complete | Production | 265 LOC, prospective_memories, test_v03_prospective. | none |
| Autobiographical Memory | L3 Memory | (none) | — | CAPT_core | missing | Concept | No implementation anywhere (forensic confirms absent). | none (design canonical interface) |
| HMC (Holographic Memory Core) | L3 Memory | biocapt-ecosystem | .../hmc_mobile.py (+hmc.rs, rustfft) | CAPT_core (Rust accel external pkg) | missing | Research | External impl; not in capt-solo. | none (canonicalize; accel optional) |
| ENGRAM | L3 Memory | biocapt-ecosystem | .../engram_mobile.py | CAPT_core | missing | Research | External impl; not adopted. | none (merge into consolidation) |
| DREAM / Consolidation | L3 Memory / L10 | biocapt-ecosystem | .../dream_consolidator_mobile.py, dream_cycle_rpc_mobile.py | CAPT_core | missing | Research | External impl; capt-solo has only lifecycle-transition stand-in. | none (canonicalize loop) |
| Context Builder | L3 Memory | capt-solo | memory/context.py | CAPT_core | complete | Production | 164 LOC, tests. | none |
| Search / Retrieval | L3 Memory | capt-solo | memory/search.py | CAPT_core | complete | Production | 102 LOC, tests. | none |
| Deduplicate | L3 Memory | capt-solo | memory/deduplicate.py | CAPT_core | complete | Production | 100 LOC, test_v02_models. | none |
| Normalize | L3 Memory | capt-solo | memory/normalize.py | CAPT_core | complete | Production | 81 LOC, tests. | none |
| Memory Compression (AntiToken) | L3 Memory | capt-solo | memory/antitoken.py | CAPT_core | complete | Production | 273 LOC, fidelity guards, test_v04_degradation, verify_runtime. | none (preserve optional/degradable) |
| Memory Compression (Holographic) | L3 Memory | biocapt-ecosystem | .../hmc_mobile.py | CAPT_core | missing | Research | External (see HMC). | none (see HMC) |
| Retrieval Feedback / Adaptation | L3 Memory | capt-solo | lifecycle/feedback.py | CAPT_core | complete | Production | 198 LOC, test_v03_feedback. | none |
| Replay | L3 Memory | capt-solo (skill/docs only) | docs + capt-recovery skill | CAPT_core | spec-only | Concept | No dedicated module; only skill references. | none (canonicalize API) |
| TTL / Retention | L3 Memory | capt-solo | memory/engine.py, lifecycle/lifecycle.py | CAPT_core | complete | Production | memory_retention_policies + lifecycle retention, test_v03_lifecycle. | none |
| Temporal Ordering | L3 Memory | capt-solo | memory/models.py | CAPT_core | complete | Production | timestamps in models, tests. | none |
| Export / Import | L3 Memory | capt-solo | memory/engine.py | CAPT_core | complete | Production | export_json + verify_runtime mem.export_json. | none |
| Migration | L3 Memory | capt-solo | memory/engine.py | CAPT_core | complete | Production | forward-migrate + 3 migration test modules. | none |
| Synchronization | L3 Memory | (none) | — | CAPT_core (abstraction) | missing | Planned | No impl; abstraction defined as canonical capability (CAPT_CANON §8 / CANONICAL_ARCHITECTURE L3.22). Transports gated, not abstraction. | none (abstraction un-gated; transports [S]) |
| Consent | L3 Memory | (none) | — | CAPT_core | missing | Concept | No impl; local consent ledger designed in architecture. | **security** (privacy review at integration; local-only) |
| Secrets Screening | L3 Memory | capt-solo | memory/secrets.py | CAPT_core | complete | Production | 84 LOC, verify_runtime secret_screening, SECURITY doc. | none |
| Knowledge Bubbles | L4 Knowledge | capt-solo | foundry/bubble.py | CAPT_core | complete | Production | 412 LOC, verify_runtime bubble_*, test_v04_plugin. | none |
| KHSB | L4 Knowledge | capt-solo | khsb/bus.py | CAPT_core | complete | Production | 173 LOC, verify_runtime khsb.*, test_khsb. | none |
| Curator | L4 Knowledge | capt-solo | foundry/curator.py | CAPT_core | complete | Production | 115 LOC, test_v04_curator. | none |
| Semantic Index | L4 Knowledge | capt-solo | lifecycle/semantic.py | CAPT_core | complete | Production | see Semantic Memory. | none |
| Trust Engine | L5 Trust | capt-solo | memory/trust.py | CAPT_core | complete | Production | 136 LOC, tests. | none |
| Evidence Engine | L5 Trust | capt-solo | foundry/proof.py (proof_evidence) | CAPT_core | complete | Production | proof_evidence table, tests. | none |
| Provenance | L5 Trust | capt-solo | memory/models.py, foundry/proof.py | CAPT_core | complete | Production | pervasive provenance, tests. | none |
| ClaimGuard | L5 Trust | capt-solo | foundry/claimguard.py | CAPT_core | complete | Production | 208 LOC, verify_runtime claimguard_*, test. | none |
| Proof Engine | L5 Trust | capt-solo | foundry/proof.py | CAPT_core | complete | Production | 303 LOC, verify_runtime proof_*, test. | none |
| Proof Ledger | L5 Trust | capt-solo (approximated) | foundry/proof.py + governance.py | CAPT_core | missing (approximated) | Beta | Approximated by ProofEngine+governance_audit; explicit ledger not yet merged. | none (merge explicit ledger) |
| IMMU (Immune/Constitution) | L5 Trust | biocapt-ecosystem | .../immu_mobile.py | CAPT_core | missing | Research | External impl; forensic notes NO DEFCON/SHA3 doc-drift. | none (adopt; note drift) |
| Lifecycle Manager | L6 Execution | capt-solo | lifecycle/lifecycle.py | CAPT_core | complete | Production | 452 LOC, test_v03_lifecycle. | none |
| Session Store | L6 Execution | capt-solo | lifecycle/sessions.py | CAPT_core | complete | Production | 572 LOC, test_v03_sessions (to merge into ECHO). | none (merge into ECHO) |
| Procedure Store | L6 Execution | capt-solo | lifecycle/procedures.py | CAPT_core | complete | Production | see Procedural Memory. | none |
| Manager | L6 Execution | capt-solo | lifecycle/manager.py | CAPT_core | complete | Production | 334 LOC, tests. | none |
| CTP | L6 Execution | capt-solo (wheel only) | capt_solo/ctp/journal.py (NOT in tree) | CAPT_core | disconnected | Beta | Wheel has 8048-B impl + verify_runtime ctp.* checks, but absent from committed tree → not Production until restored. | none (restore from verified wheel; not a gate) |
| CLI | L6 Execution | capt-solo | capt_cli.py | CAPT_core | complete | Production | test_v04_cli. | none |
| Runtime SDK | L6 Execution | capt-solo | api.py | CAPT_core | complete | Production | public api surface, verify_runtime public_api_smoke. | none |
| PULSE (LLM Gateway) | L7 Communication / L11 | biocapt-ecosystem | .../pulse_mobile.py | optional plugin / external package | missing | Research | External impl; network/LLM surface. | **boundary + security** |
| Governance | L8 Governance | capt-solo | foundry/governance.py | CAPT_core | complete | Production | 137 LOC, verify_runtime governance_*, test_v04_curator. | none (depends on CTP restore) |
| Release Gates | L8 Governance | capt-solo | verify_runtime.py, doctor.sh, verify.sh | CAPT_core | complete | Production | 52 check_ids defined; runs in-tree (gated only by ctp import). | none |
| Migration Governance | L8 Governance | capt-solo | memory/engine.py + verify_runtime | CAPT_core | complete | Production | migration_backup_dir check, tests. | none |
| Skill Foundry | L9 Skills | capt-solo | foundry/skill_foundry.py | CAPT_core | complete | Production | 478 LOC, verify_runtime skill_*, test_v04_foundry. | none |
| Skill Radar | L9 Skills | biocapt-ecosystem | registry SKILL_RADAR | CAPT_core | missing | Research | External registry entry; to merge into Foundry. | none (merge into Skill Foundry) |
| Plugin SDK | L9 Skills | capt-solo | plugin/__init__.py, plugin.json | CAPT_core | complete | Production | 808 LOC, test_plugin, test_v04_plugin. | none |
| Bundled Skills (8) | L9 Skills | capt-solo | skills/* | CAPT_core | complete | Production | 8 SKILL.md, tests. | none |
| Learning / Adaptation | L10 Learning | biocapt-ecosystem | registry LEARNING, ADAPTATION | CAPT_core | missing | Research | External registry entries; not adopted. | none (adopt) |
| Consolidation-as-Learning | L10 Learning | capt-solo (partial) / biocapt-ecosystem | lifecycle transitions / dream_* | CAPT_core | partial | Beta | Lifecycle transitions present; full DREAM loop external. | none |
| Continuous Learning | L10 Learning | biocapt-ecosystem | capt/modules/continuous_learning_module.py (792 LOC candidate) | CAPT_core | missing | Research | External candidate impl (792 LOC, not in registry); architecture permanently Layer 10 regardless of impl completeness. | none (adopt; no longer "orphan") |
| OUROBOROS | L10 Learning | biocapt-ecosystem | registry OUROBOROS | research package | missing | Research | External registry entry. | **boundary** |
| CAPTLANG (compiler/DSL) | L11 External | Biocapt-ecosystem-fullcaptlang | src/captlang/, codegen_wasm.py, Makefile.captlang | external package | missing | Research | External build tooling; 30 compiler-known modules. | none (build tooling) |
| Plugin SDK (cross) | L11 / L9 | capt-solo | plugin/ | CAPT_core | complete | Production | see Plugin SDK. | none |
| Runtime SDK (cross) | L11 / L6 | capt-solo | api.py | CAPT_core | complete | Production | see Runtime SDK. | none |
| Hermes Plugin Interface | L11 External | capt-solo | plugin/__init__.py | CAPT_core | complete | Production | see Plugin SDK. | none |
| FILT (Attentional Filter) | L2 Reasoning | biocapt-ecosystem | .../filt_mobile.py (DISABLED, __slots__ bug) | research package | missing | Research | External, DISABLED in source. | **boundary** (fix-then-canonicalize) |
| FSR (Feedback Regulator) | L2 Reasoning | biocapt-ecosystem | .../fsr_mobile.py (DISABLED, __slots__ bug) | research package | missing | Research | External, DISABLED in source. | **boundary** |
| PLAST (Hebbian/BCM) | L10 Learning | biocapt-ecosystem | .../plast_mobile.py | CAPT_core | missing | Research | External impl; fold into consolidation. | none (fold into consolidation) |
| ALLO (Allostatic) | L2 Reasoning | biocapt-ecosystem | .../allo_mobile.py | research package | missing | Research | External impl. | **boundary** |
| +30 registry modules (AIM, ATT, SENS, PCFE, IRIS, SYNC, NDS, EXEC, INHIB, ITC, MOTOR, TSCC, CREAT, BELIEF_GRAPH, CAUSAL_RSN, ANALOGICAL, CONCEPT_ALG, TEMPORAL_RSN, EMERGENCE_DET, CURIOSITY, EPISTEMIC, VALUE_ALIGN, TOM, ACTIVE_INF, SWARM_DECOMP, AGENT_ROUTER, TOOL_SYNTH, BUG_BOUNTY, HOMEOSTASIS/STRESS/RECOV, MFO, SWC, SCF, ZKC, CONSTITUTION, AUTONOMY) | various (L2/L5/L6/L10) | biocapt-ecosystem | modules/*_mobile.py | research package (default) | missing | Research | External registry entries; per-module include decision pending. | **boundary** (per-module) |

---

## Maturity summary

- **Production (in capt-solo, verified):** MemoryEngine, CSG, Semantic, Procedural, Prospective, Context, Search, Dedupe, Normalize, AntiToken, Retrieval Feedback, TTL/Retention, Temporal, Export/Import, Migration, Secrets, Knowledge Bubbles, KHSB, Curator, Trust, Evidence, Provenance, ClaimGuard, Proof Engine, Lifecycle, Session, Procedure, Manager, CLI, Runtime SDK, Governance, Release Gates, Migration Gov, Skill Foundry, Plugin SDK, Bundled Skills, Hermes Plugin. (37 subsystems)
- **Beta (partial / approximated / disconnected-but-built):** Identity, Reasoning Core, Episodic (ECHO), Proof Ledger, CTP, Consolidation-as-Learning. (6)
- **Concept (defined, no impl):** Ontology, Constitution, Autobiographical, Replay, Consent, Synchronization (abstraction). (6)
- **Planned:** Synchronization (impl scheduled). (1)
- **Research (external / metaphorical / disabled):** CIG, HDR, META, CONSC, QIPC, RYS Bridge, Cognitive Loop, NEDA, HMC, ENGRAM, DREAM, Memory Compression (Holographic), IMMU, PULSE, Skill Radar, Learning/Adaptation, Continuous Learning, OUROBOROS, CAPTLANG, FILT, FSR, PLAST, ALLO, +30 registry modules. (24)

Maturity is independent of architectural importance: e.g. HMC is Research-maturity but architecturally permanent in L3; Ontology is Concept-maturity but foundational (L0.5).

---

## Summary of owner gates remaining

Only four gate types (per issue: public/private boundary, licensing uncertainty, security exposure, irreconcilable canonical behavior):

1. **Public/private boundary [B]** — CONSC, QIPC, NEDA, ALLO, FILT, FSR, OUROBOROS, +30 registry modules, RYS Bridge, PULSE. Decision: which enter public release vs stay research/private. (Continuous Learning and Synchronization are NO LONGER gated — CL is permanently L10; Sync abstraction is canonical/un-gated, only transports reviewed.)
2. **Licensing uncertainty [L]** — bioCAPT `modules/*_mobile.py` carry unspecified license vs capt-solo MIT. Any component adopted into CAPT_core from bioCAPT requires license reconciliation before merge. (CTP is capt-solo's own wheel code — no external license issue.)
3. **Security exposure [S]** — PULSE (LLM/network), RYS Bridge (external call), Consent (privacy), and Synchronization **transports** (LAN/P2P/cloud). These need owner-approved integration design before wiring into public runtime. (Synchronization *abstraction* is un-gated.)
4. **Irreconcilable canonical behavior [C]** — canonical version identity (pyproject 0.1.0 vs wheel/docs 0.4.1 vs tag v0.4.0). Owner picks canonical version + tag.

## Everything else proceeds autonomously

All Production/Beta capt-solo-internal subsystems and the canonicalization of HMC/ECHO/ENGRAM/DREAM/IMMU/CIG/HDR/META/Cognitive Loop/Learning/Proof Ledger/Skill Radar/Autobiographical/Replay/CTP need no [B]/[S] gate (only [L] for external-source adoption, which is a reconcile-before-merge step, not a stop).
