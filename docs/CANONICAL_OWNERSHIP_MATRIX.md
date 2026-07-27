# CANONICAL OWNERSHIP MATRIX

**Phase:** 2 — companion to CANONICAL_ARCHITECTURE.md
**Baseline inventory:** accepted (commit `33cc37a`)
**Branch:** `integration/full-public-architecture`
**Date:** 2026-07-26
**Issue:** #5

## Column definitions

- **Component** — canonical subsystem name.
- **Canonical Home** — CAPT layer (L0–L11) where it permanently belongs.
- **Current Repo** — where the code lives today.
- **Current Path** — path in that repo.
- **Planned Public Repo** — where it will ship (CAPT_core / external package / optional plugin / research package / private / undecided).
- **Current Status** — complete / partial / disconnected / missing / spec-only (per accepted inventory).
- **Owner Decision** — none (autonomous) / specific gate required.

## Release Target vocabulary (used in Planned Public Repo)

- `CAPT_core` — ships in the public CAPT_core runtime.
- `external package` — separate published package, not in core runtime.
- `optional plugin` — opt-in plugin (may be external or core-contrib).
- `research package` — research/preview, not in stable public release by default.
- `private` — not for public release.
- `undecided` — requires owner ruling (boundary/licensing/security/irreconcilable).

---

| Component | Canonical Home | Current Repo | Current Path | Planned Public Repo | Current Status | Owner Decision |
|-----------|---------------|-------------|-------------|---------------------|----------------|----------------|
| Identity | L0 Identity | capt-solo | lifecycle/semantic.py (implicit) | CAPT_core | partial | none (autonomous: make explicit) |
| Constitution | L1 Constitution | (none) | — | CAPT_core | spec-only | none |
| Reasoning Core | L2 Reasoning | capt-solo | (implicit orchestration) | CAPT_core | partial | none |
| CIG (Causal Inference) | L2 Reasoning | biocapt-ecosystem | primary/biocapt-desktop/modules/cig_mobile.py | CAPT_core | missing | none (adopt canonical impl) |
| HDR (Hyperdim Reasoning) | L2 Reasoning | biocapt-ecosystem | .../hdr_mobile.py (+hdr.rs) | CAPT_core (Rust accel external pkg) | missing | none (adopt; accel optional) |
| META (Metacognition) | L2 Reasoning | biocapt-ecosystem | .../meta_mobile.py | CAPT_core | missing | none |
| CONSC (Φ / Global Workspace) | L2 Reasoning | biocapt-ecosystem | .../consc_mobile.py | research package | missing | **boundary** (metaphorical; public/private) |
| QIPC (Quantum-Inspired Consensus) | L2 Reasoning | biocapt-ecosystem | .../qipc_mobile.py (+qipc.rs) | research package | missing | **boundary** |
| RYS Bridge | L2 Reasoning / L11 | biocapt-ecosystem / AIM-CAPTRYS | .../rys_mobile.py | external package / optional plugin | missing | **boundary + security** (external call) |
| Cognitive Loop | L2 Reasoning | biocapt-ecosystem | registry COGNITIVE_LOOP | CAPT_core | missing | none |
| NEDA (Neural Event-Driven) | L2 Reasoning | biocapt-ecosystem | .../neda_mobile.py (+neda.rs) | research package | missing | **boundary** |
| MemoryEngine | L3 Memory | capt-solo | memory/engine.py | CAPT_core | complete | none |
| CSG | L3 Memory | capt-solo | memory/csg.py | CAPT_core | complete | none |
| Episodic Memory (ECHO) | L3 Memory | capt-solo (SessionStore) / biocapt-ecosystem (echo_mobile.py) | lifecycle/sessions.py / .../echo_mobile.py | CAPT_core | partial | none (adopt ECHO canonical interface, merge SessionStore) |
| Semantic Memory | L3 Memory | capt-solo | lifecycle/semantic.py | CAPT_core | complete | none |
| Procedural Memory | L3 Memory | capt-solo | lifecycle/procedures.py | CAPT_core | complete | none |
| Prospective Memory | L3 Memory | capt-solo | lifecycle/prospective.py | CAPT_core | complete | none |
| Autobiographical Memory | L3 Memory | (none) | — | CAPT_core | missing | none (design canonical interface) |
| HMC (Holographic Memory Core) | L3 Memory | biocapt-ecosystem | .../hmc_mobile.py (+hmc.rs, rustfft) | CAPT_core (Rust accel external pkg) | missing | none (canonicalize; accel optional) |
| ENGRAM | L3 Memory | biocapt-ecosystem | .../engram_mobile.py | CAPT_core | missing | none (merge into consolidation) |
| DREAM / Consolidation | L3 Memory / L10 | biocapt-ecosystem | .../dream_consolidator_mobile.py, dream_cycle_rpc_mobile.py | CAPT_core | missing | none (canonicalize loop) |
| Context Builder | L3 Memory | capt-solo | memory/context.py | CAPT_core | complete | none |
| Search / Retrieval | L3 Memory | capt-solo | memory/search.py | CAPT_core | complete | none |
| Deduplicate | L3 Memory | capt-solo | memory/deduplicate.py | CAPT_core | complete | none |
| Normalize | L3 Memory | capt-solo | memory/normalize.py | CAPT_core | complete | none |
| Memory Compression (AntiToken) | L3 Memory | capt-solo | memory/antitoken.py | CAPT_core | complete | none (preserve optional/degradable) |
| Memory Compression (Holographic) | L3 Memory | biocapt-ecosystem | .../hmc_mobile.py | CAPT_core | missing | none (see HMC) |
| Retrieval Feedback / Adaptation | L3 Memory | capt-solo | lifecycle/feedback.py | CAPT_core | complete | none |
| Replay | L3 Memory | capt-solo (skill/docs only) | docs + capt-recovery skill | CAPT_core | spec-only | none (canonicalize API) |
| TTL / Retention | L3 Memory | capt-solo | memory/engine.py, lifecycle/lifecycle.py | CAPT_core | complete | none |
| Temporal Ordering | L3 Memory | capt-solo | memory/models.py | CAPT_core | complete | none |
| Export / Import | L3 Memory | capt-solo | memory/engine.py | CAPT_core | complete | none |
| Migration | L3 Memory | capt-solo | memory/engine.py | CAPT_core | complete | none |
| Synchronization | L3 Memory / L11 | (none) | — | undecided | missing | **boundary + security** (network surface) |
| Consent | L3 Memory | (none) | — | CAPT_core | missing | **security** (privacy review at integration) |
| Secrets Screening | L3 Memory | capt-solo | memory/secrets.py | CAPT_core | complete | none |
| Knowledge Bubbles | L4 Knowledge | capt-solo | foundry/bubble.py | CAPT_core | complete | none |
| KHSB | L4 Knowledge | capt-solo | khsb/bus.py | CAPT_core | complete | none |
| Curator | L4 Knowledge | capt-solo | foundry/curator.py | CAPT_core | complete | none |
| Semantic Index | L4 Knowledge | capt-solo | lifecycle/semantic.py | CAPT_core | complete | none |
| Trust Engine | L5 Trust | capt-solo | memory/trust.py | CAPT_core | complete | none |
| Evidence Engine | L5 Trust | capt-solo | foundry/proof.py (proof_evidence) | CAPT_core | complete | none |
| Provenance | L5 Trust | capt-solo | memory/models.py, foundry/proof.py | CAPT_core | complete | none |
| ClaimGuard | L5 Trust | capt-solo | foundry/claimguard.py | CAPT_core | complete | none |
| Proof Engine | L5 Trust | capt-solo | foundry/proof.py | CAPT_core | complete | none |
| Proof Ledger | L5 Trust | capt-solo (approximated) | foundry/proof.py + governance.py | CAPT_core | missing (approximated) | none (merge explicit ledger) |
| IMMU (Immune/Constitution) | L5 Trust | biocapt-ecosystem | .../immu_mobile.py | CAPT_core | missing | none (adopt; note doc-drift NO DEFCON/SHA3) |
| Lifecycle Manager | L6 Execution | capt-solo | lifecycle/lifecycle.py | CAPT_core | complete | none |
| Session Store | L6 Execution | capt-solo | lifecycle/sessions.py | CAPT_core | complete | none (merge into ECHO) |
| Procedure Store | L6 Execution | capt-solo | lifecycle/procedures.py | CAPT_core | complete | none |
| Manager | L6 Execution | capt-solo | lifecycle/manager.py | CAPT_core | complete | none |
| CTP | L6 Execution | capt-solo (wheel only) | capt_solo/ctp/journal.py (NOT in tree) | CAPT_core | disconnected | none (restore from verified wheel; not a boundary/licensing/security/irreconcilable issue) |
| CLI | L6 Execution | capt-solo | capt_cli.py | CAPT_core | complete | none |
| Runtime SDK | L6 Execution | capt-solo | api.py | CAPT_core | complete | none |
| PULSE (LLM Gateway) | L7 Communication / L11 | biocapt-ecosystem | .../pulse_mobile.py | optional plugin / external package | missing | **boundary + security** (LLM/network) |
| Governance | L8 Governance | capt-solo | foundry/governance.py | CAPT_core | complete | none (depends on CTP restore) |
| Release Gates | L8 Governance | capt-solo | verify_runtime.py, doctor.sh, verify.sh | CAPT_core | complete | none |
| Migration Governance | L8 Governance | capt-solo | memory/engine.py + verify_runtime | CAPT_core | complete | none |
| Skill Foundry | L9 Skills | capt-solo | foundry/skill_foundry.py | CAPT_core | complete | none |
| Skill Radar | L9 Skills | biocapt-ecosystem | registry SKILL_RADAR | CAPT_core | missing | none (merge into Skill Foundry) |
| Plugin SDK | L9 Skills | capt-solo | plugin/__init__.py, plugin.json | CAPT_core | complete | none |
| Bundled Skills (8) | L9 Skills | capt-solo | skills/* | CAPT_core | complete | none |
| Learning / Adaptation | L10 Learning | biocapt-ecosystem | registry LEARNING, ADAPTATION | CAPT_core | missing | none (adopt) |
| Consolidation-as-Learning | L10 Learning | capt-solo (partial) / biocapt-ecosystem | lifecycle transitions / dream_* | CAPT_core | partial | none |
| Continuous Learning | L10 Learning | biocapt-ecosystem | capt/modules/continuous_learning_module.py (orphan, 792 LOC) | CAPT_core | missing | **boundary** (orphan; include?) |
| OUROBOROS | L10 Learning | biocapt-ecosystem | registry OUROBOROS | research package | missing | **boundary** |
| CAPTLANG (compiler/DSL) | L11 External | Biocapt-ecosystem-fullcaptlang | src/captlang/, codegen_wasm.py, Makefile.captlang | external package | missing | none (build tooling) |
| Plugin SDK (cross) | L11 / L9 | capt-solo | plugin/ | CAPT_core | complete | none |
| Runtime SDK (cross) | L11 / L6 | capt-solo | api.py | CAPT_core | complete | none |
| Hermes Plugin Interface | L11 External | capt-solo | plugin/__init__.py | CAPT_core | complete | none |
| FILT (Attentional Filter) | L2 Reasoning | biocapt-ecosystem | .../filt_mobile.py (DISABLED, __slots__ bug) | research package | missing | **boundary** (disabled; fix-then-canonicalize) |
| FSR (Feedback Regulator) | L2 Reasoning | biocapt-ecosystem | .../fsr_mobile.py (DISABLED, __slots__ bug) | research package | missing | **boundary** |
| PLAST (Hebbian/BCM) | L10 Learning | biocapt-ecosystem | .../plast_mobile.py | CAPT_core | missing | none (fold into consolidation) |
| ALLO (Allostatic) | L2 Reasoning | biocapt-ecosystem | .../allo_mobile.py | research package | missing | **boundary** |
| +30 registry modules (AIM, ATT, SENS, PCFE, IRIS, SYNC, NDS, EXEC, INHIB, ITC, MOTOR, TSCC, CREAT, BELIEF_GRAPH, CAUSAL_RSN, ANALOGICAL, CONCEPT_ALG, TEMPORAL_RSN, EMERGENCE_DET, CURIOSITY, EPISTEMIC, VALUE_ALIGN, TOM, ACTIVE_INF, SWARM_DECOMP, AGENT_ROUTER, TOOL_SYNTH, BUG_BOUNTY, HOMEOSTASIS/STRESS/RECOV, MFO, SWC, SCF, ZKC, CONSTITUTION, AUTONOMY) | various (L2/L5/L6/L10) | biocapt-ecosystem | modules/*_mobile.py | research package (default) | missing | **boundary** (per-module include decision) |

---

## Summary of owner gates remaining

Only four gate types remain (per issue: public/private boundary, licensing uncertainty, security exposure, irreconcilable canonical behavior):

1. **Public/private boundary** — CONSC, QIPC, NEDA, ALLO, FILT, FSR, OUROBOROS, +30 registry modules, Continuous Learning (orphan), Synchronization, RYS Bridge, PULSE. Decision: which enter the public release vs stay research/private.
2. **Licensing uncertainty** — bioCAPT `modules/*_mobile.py` carry unspecified license vs capt-solo MIT. Any component **adopted into CAPT_core** from bioCAPT requires license reconciliation before merge. (CTP is capt-solo's own code in wheel — no external license issue.)
3. **Security exposure** — PULSE (LLM/network), Synchronization (network), RYS Bridge (external call), Consent (privacy). These need owner-approved integration design before wiring into public runtime.
4. **Irreconcilable canonical behavior** — canonical version identity (pyproject 0.1.0 vs wheel/docs 0.4.1 vs tag v0.4.0). Owner picks the canonical version + tag.

## Everything else proceeds autonomously

All CAPT_core-internal subsystems (MemoryEngine, CSG, Semantic/Procedural/Prospective, Context, Search, Dedupe, Normalize, Trust, Evidence, Provenance, ClaimGuard, Proof Engine, Knowledge Bubbles, KHSB, Curator, Lifecycle, Session/Procedure/Manager, CLI, Runtime SDK, Governance, Release Gates, Skill Foundry, Plugin SDK, Bundled Skills, AntiToken, TTL/Retention, Export/Import, Migration, Secrets Screening) are complete and need no owner gate.

Canonicalization of HMC, ECHO, ENGRAM, DREAM, IMMU, CIG, HDR, META, Cognitive Loop, Learning/Adaptation, Proof Ledger (merge), Skill Radar (merge), Autobiographical (design), Consent (design), Replay (canonicalize), CTP (restore) — all proceed autonomously once the licensing gate for the specific external source is cleared (or the component is capt-solo's own code, e.g. CTP).
