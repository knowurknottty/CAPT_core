> SUPERSEDED — historical architecture inventory. Contains a FALSE claim that capt_solo/ctp/journal.py is gitignored/missing from tree. VERIFIED: ctp/journal.py is tracked and present (8048 bytes). Do not treat this doc's 'MISSING FROM TREE' rows as current state. Authoritative: EXACT_SHA_RELEASE_VALIDATION.md + BASELINE_REVALIDATION.md.

# FULL ARCHITECTURE IMPLEMENTATION MATRIX

**Phase:** 1 — Full architecture census
**Baseline:** `knowurknottty/CAPT_core` @ `main` `abeff5c` (v0.4.1 lineage)
**Branch:** `integration/full-public-architecture`
**Date:** 2026-07-26
**Scope:** Every CAPT subsystem/component discovered in `capt-solo` (CAPT_core) plus the memory/knowledge stack named in issue #5 and the forensic reconstruction corpus. External source repos inspected: `biocapt-ecosystem`, `biocapt-ecosystem-github-current-20260518`, `Biocapt-ecosystem-fullcaptlang`, `.gitnexus/repos/biocapt-ecosystem`, `AIM-CAPTRYS`, `hermes_project/frankencapt-base`, `frankencapt-skills`, `capt-training*`.

**Status legend:** complete / partial / stub / spec-only / missing / duplicated / disconnected
**Evidence classes:** ✅ verified-in-tree (capt-solo committed code) · 🔬 inferred · ⚠️ external-only (not in capt-solo) · ❌ absent

> The forensic reconstruction is treated as an evidence corpus, NOT an authority. Its recommendations/deletions are not adopted. Where the forensic corpus and committed code conflict, both are recorded.

---

## A. Memory substrate (core)

| canonical name | aliases | purpose | source evidence | capt_core path | external repo/path | status | public API | persistence | security boundaries | tests | docs | deps | migration impact | proposed completion | unresolved owner decision |
|---------------|--------|---------|-----------------|---------------|-------------------|--------|-----------|------------|-------------------|-------|------|------|-----------------|-------------------|----------------------|
| MemoryEngine | mem | SQLite-backed memory store (memories, tags, nodes, edges, aliases, conflicts, retention, lifecycle transitions) | ✅ `capt_solo/memory/engine.py` | `capt_solo/memory/engine.py` | — | complete | `MemoryEngine` in `api.py` | SQLite, SCHEMA_VERSION=5 | local-only, secret-screened on store | ✅ memory and migration suites | ✅ DATA_MODEL, API | sqlite3, core.config | forward-migrates <5 | none | — |
| CSG (Cognitive State Graph) | csg | cognitive state graph: predict/path/centrality/history | ✅ `memory/csg.py` (375 LOC) | `capt_solo/memory/csg.py` | — | complete | `CSG` | SQLite (memory_nodes/edges) | local | ✅ test_v02_csg | ✅ ARCHITECTURE | engine | low | none | — |
| Context builder | context | build context windows from memory | ✅ `memory/context.py` (164) | `capt_solo/memory/context.py` | — | complete | internal | SQLite | local | ✅ test_v02_* | partial | engine, search | low | none | — |
| Search | search | memory retrieval/search | ✅ `memory/search.py` (102) | `capt_solo/memory/search.py` | — | complete | internal | SQLite | local | ✅ tests | partial | engine | low | none | — |
| Deduplicate | dedupe | dedupe memories | ✅ `memory/deduplicate.py` (100) | `capt_solo/memory/deduplicate.py` | — | complete | internal | SQLite | local | ✅ test_v02_models | partial | engine, normalize | low | none | — |
| Normalize | normalize | normalize memory content | ✅ `memory/normalize.py` (81) | `capt_solo/memory/normalize.py` | — | complete | internal | n/a | local | ✅ tests | partial | — | low | none | — |
| Trust | trust | trust scoring of memories/evidence | ✅ `memory/trust.py` (136) | `capt_solo/memory/trust.py` | — | complete | internal | SQLite | local | ✅ tests | partial | engine | low | none | — |
| Secrets screening | secrets | screen secrets before persistence | ✅ `memory/secrets.py` (84) | `capt_solo/memory/secrets.py` | — | complete | `secrets.screen` | n/a | secret-hiding | ✅ verify_runtime secret_screening | ✅ SECURITY | — | none | none | — |
| AntiToken extraction | antitoken, anti-token-extraction | deterministic token-reduction preserving decision-relevant structure; fidelity guards | ✅ `memory/antitoken.py` (273) | `capt_solo/memory/antitoken.py` | integration/anti-token-extraction-v0.2 branch | complete | `extract/validate/render` | n/a (stateless) | local-stdio, bounded, non-persistent, degradable | ✅ test_v04_degradation, verify_runtime | ✅ SECURITY, ARCHITECTURE | models | none | none (preserve optional/degradable per issue) | — |
| Episodic memory | episodic | session-scoped episodic timeline | ✅ partial: `lifecycle/sessions.py` (572) + `session_*` tables | `capt_solo/lifecycle/sessions.py` | — | partial | `SessionStore` | SQLite sessions/events/checkpoints | local | ✅ test_v03_sessions | ✅ ARCHITECTURE | engine | low | confirm coverage vs forensic "ECHO 90-day ring buffer" | — |
| Semantic memory | semantic | semantic index | ✅ `lifecycle/semantic.py` (153) + `semantic_index_metadata` | `capt_solo/lifecycle/semantic.py` | — | complete | `SemanticIndex` | SQLite | local | ✅ tests | partial | engine | low | none | — |
| Procedural memory | procedural | procedures + runs | ✅ `lifecycle/procedures.py` (391) + `procedures*` tables | `capt_solo/lifecycle/procedures.py` | — | complete | `ProcedureStore` | SQLite | local | ✅ test_v03_procedures | partial | engine | low | none | — |
| Prospective memory | prospective | future/intended memories | ✅ `lifecycle/prospective.py` (265) + `prospective_memories` | `capt_solo/lifecycle/prospective.py` | — | complete | `ProspectiveMemory` | SQLite | local | ✅ test_v03_prospective | partial | engine | low | none | — |
| Autobiographical memory | autobiographical | self/narrative timeline | ❌ absent in capt-solo | — | ⚠️ not in biocapt *_mobile set either (forensic lists no autobiographical module) | missing | — | — | — | none | none | — | — | PORT or confirm out-of-scope | **OWNER**: include in public release? |
| HMC (Holographic Memory Core) | hmc, holographic | FFT circular-convolution VSA memory (hippocampus analogue) | ❌ absent in capt-solo | — | ⚠️ `biocapt-ecosystem/primary/biocapt-desktop/modules/hmc_mobile.py` (Rust accel `biocapt_rust.hmc`) | missing (external) | — | SQLite holograms (external) | external | external-only | external-only | numpy/rustfft (external) | high if ported | PORT into capt-solo memory layer OR keep external w/ adapter | **OWNER**: port vs external? |
| ECHO (Episodic buffer) | echo | ring buffer 90-day timeline, time-travel | ❌ absent in capt-solo (name appears only in tests/docs as generic "echo") | — | ⚠️ `biocapt-ecosystem/.../echo_mobile.py` | missing (external) | — | in-mem + optional SQLite | external | external-only | external-only | — | high | PORT or map to SessionStore | **OWNER**: port vs map to SessionStore? |
| ENGRAM | engram | long-term encode/consolidation | ❌ absent in capt-solo | — | ⚠️ `biocapt-ecosystem/.../engram_mobile.py` | missing (external) | — | external | external | external-only | external-only | — | high | PORT or fold into MemoryEngine consolidation | **OWNER**: port vs fold? |
| DREAM / consolidation | dream, consolidation | offline consolidation | ❌ absent in capt-solo (consolidation logic exists only as lifecycle transitions) | — | ⚠️ `biocapt-ecosystem/.../dream_consolidator_mobile.py`, `dream_cycle_rpc_mobile.py` | missing (external) | — | external | external | external-only (forensic: "not auto-tested on disk") | external-only | — | high | PORT consolidation loop OR confirm SessionStore consolidation suffices | **OWNER**: port vs rely on lifecycle? |
| Holographic Memory | holographic memory | VSA holographic store | ❌ absent in capt-solo | — | ⚠️ see HMC above | missing (external) | — | — | — | — | — | — | — | see HMC | **OWNER** |
| Compression (memory) | compression | summarization/compression layer | ⚠️ only AntiToken char-compression present; forensic notes "no explicit summarization layer found in code" | `memory/antitoken.py` | — | partial | AntiToken | n/a | local | ✅ tests | partial | — | none | confirm whether holographic/summarization compression required | **OWNER**: required? |
| Retrieval feedback/adaptation | retrieval | adaptive retrieval | ✅ `retrieval_feedback`, `retrieval_adaptation` tables + `lifecycle/feedback.py` (198) | `capt_solo/lifecycle/feedback.py` | — | complete | `FeedbackStore` | SQLite | local | ✅ test_v03_feedback | partial | engine | low | none | — |
| Replay | replay | replay memories/sessions | ⚠️ mentioned in docs/skills (capt-recovery) but no dedicated module | docs/API.md, SKILL.md | — | spec-only | — | — | — | partial (recovery skill) | docs | — | — | implement replay API or document as recovery-only | **OWNER**: dedicated replay subsystem? |
| TTL / retention | ttl, retention | retention policies | ✅ `memory_retention_policies` table + `lifecycle` retention | `memory/engine.py`, `lifecycle/lifecycle.py` | — | complete | internal | SQLite | local | ✅ test_v03_lifecycle | partial | engine | low | none | — |
| Export / import | export, import | JSON export/import of memories | ✅ `mem.export_json` in verify; engine export methods | `memory/engine.py` | — | complete | `export_json` | file | local | ✅ verify_runtime mem.export_json | ✅ DATA_MODEL | — | none | none | — |
| Migration | migration | schema version migration | ✅ engine migrates <SCHEMA_VERSION; 3 migration test modules | `memory/engine.py` | — | complete | internal | SQLite | local | ✅ test_migration, test_v03_migration, test_v04_migration | ✅ MIGRATIONS | engine | n/a (it IS migration) | none | — |
| Provenance | provenance | track memory/evidence provenance | ✅ pervasive (proof_evidence, models, csg) | `memory/models.py`, `foundry/proof.py` | — | complete | internal | SQLite | local | ✅ tests | ✅ docs | engine, foundry | low | none | — |
| Consent | consent | user consent tracking | ❌ absent in capt-solo | — | ⚠️ not found in biocapt *_mobile scan either | missing | — | — | — | none | none | — | — | PORT or confirm consent handled at runtime boundary | **OWNER**: required for public release? |
| Identity | identity | agent/self identity | ⚠️ minimal: `lifecycle/semantic.py` (7 hits), `engine.py` (1) | `lifecycle/semantic.py` | — | partial | internal | SQLite | local | partial | partial | engine | low | define identity model or confirm out-of-scope | **OWNER** |
| Temporal ordering | temporal | time-ordered memory | ✅ `models.py` timestamps, `antitoken.py` temporal guards | `memory/models.py` | — | complete | internal | SQLite | local | ✅ tests | partial | engine | low | none | — |
| Synchronization | synchronization | multi-instance sync | ❌ absent in capt-solo | — | ⚠️ not in biocapt *_mobile scan | missing | — | — | — | none | none | — | — | PORT or confirm local-first single-instance | **OWNER**: sync required? |

## B. Transaction / knowledge-bus layer

| canonical name | aliases | purpose | source evidence | capt_core path | external repo/path | status | public API | persistence | security boundaries | tests | docs | deps | migration impact | proposed completion | unresolved owner decision |
|---------------|--------|---------|-----------------|---------------|-------------------|--------|-----------|------------|-------------------|-------|------|------|-----------------|-------------------|----------------------|
| CTP (Cognitive Transaction Protocol) | ctp, journal | append-only local transaction journal w/ receipts, idempotency, integrity | ✅ wheel `capt_solo/ctp/journal.py` (8048 bytes) BUT ❌ NOT in committed tree (gitignored) | **MISSING FROM TREE** (`capt_solo/ctp/`) | — | disconnected (built but uncommitted) | `CTPRuntime`, `Receipt` | JSONL journal | local, immutable receipts | ✅ verify_runtime ctp.* (in wheel) | ✅ docs | core.config, core.errors | high (must commit) | **COMMIT ctp/ from wheel source** (B1) | **OWNER**: approve committing ctp/ (currently gitignored) |
| KHSB (Knowledge/Hermes Service Bus) | khsb, bus | local pub/sub + request/reply bus | ✅ `khsb/bus.py` (173) | `capt_solo/khsb/bus.py` | — | complete | `KHSB`, `bus` | in-memory | local | ✅ verify_runtime khsb.*, test_khsb | ✅ ARCHITECTURE | core.config | low | none | — |

## C. Foundry (proof / trust / knowledge / skill)

| canonical name | aliases | purpose | source evidence | capt_core path | external repo/path | status | public API | persistence | security boundaries | tests | docs | deps | migration impact | proposed completion | unresolved owner decision |
|---------------|--------|---------|-----------------|---------------|-------------------|--------|-----------|------------|-------------------|-------|------|------|-----------------|-------------------|----------------------|
| ProofEngine | proof | proof/evidence integrity | ✅ `foundry/proof.py` (303) | `capt_solo/foundry/proof.py` | — | complete | `ProofEngine` | SQLite proof_evidence/requirements | local | ✅ verify_runtime foundry.proof_* | ✅ PROOF_ENGINE | engine | low | none | — |
| CapabilityRegistry | capability, registry | capability registration + degradation | ✅ `foundry/registry.py` (352) | `capt_solo/foundry/registry.py` | — | complete | `CapabilityRegistry` | SQLite capabilities/degradations | local, scoped downgrade | ✅ verify_runtime foundry.capability_*, test_v04_release_scenarios | ✅ CAPABILITY_REGISTRY | engine, claimguard | low | none | — |
| ClaimGuard | claimguard | claim verification / scoped downgrade | ✅ `foundry/claimguard.py` (208) | `capt_solo/foundry/claimguard.py` | — | complete | `ClaimGuard` | SQLite | local, trust-scoped | ✅ verify_runtime foundry.claimguard_* | ✅ CLAIMGUARD | engine, proof | low | none | — |
| SkillFoundry | skill foundry | skill publish/validate | ✅ `foundry/skill_foundry.py` (478) | `capt_solo/foundry/skill_foundry.py` | — | complete | `SkillFoundry` | SQLite skills/skill_candidates | local | ✅ verify_runtime foundry.skill_* | ✅ SKILL_FOUNDRY | engine, proof | low | none | — |
| KnowledgeBubble runtime | knowledge bubble, bubble | portable memory/knowledge packages | ✅ `foundry/bubble.py` (412) | `capt_solo/foundry/bubble.py` | — | complete | `KnowledgeBubbleRuntime` | SQLite knowledge_bubbles + `.capt-bubble.json` | local, quarantine isolation | ✅ verify_runtime foundry.bubble_*, test_v04_plugin | ✅ KNOWLEDGE_BUBBLES | engine, immu(external) | low | none | — |
| Governance | governance | governance audit/receipts | ✅ `foundry/governance.py` (137) | `capt_solo/foundry/governance.py` | — | complete | `Governance` | SQLite governance_audit | local | ✅ verify_runtime foundry.governance_* | ✅ GOVERNANCE | engine, ctp(imports) | low | none (depends on ctp commit) | — |
| Curator | curator | curation of knowledge/skills | ✅ `foundry/curator.py` (115) | `capt_solo/foundry/curator.py` | — | complete | `Curator` | SQLite | local | ✅ test_v04_curator | ✅ ARCHITECTURE | engine | low | none | — |
| WorkflowProof | workflow proof | composite workflow proofs | ✅ `foundry/workflow_proof.py` (273) | `capt_solo/foundry/workflow_proof.py` | — | complete | `WorkflowProofEngine` | SQLite workflow_proofs/composite_workflows | local, independent | ✅ verify_runtime foundry.workflow_*, test_v04_workflow_proof | ✅ ARCHITECTURE | engine, proof | low | none | — |
| ValidationHarness | harness | validation harness | ✅ `foundry/harness.py` (312) | `capt_solo/foundry/harness.py` | — | complete | `ValidationHarness` | n/a | local | ✅ tests | partial | engine, proof | low | none | — |
| Composition | composition | skill/proof composition | ✅ `foundry/composition.py` (156) | `capt_solo/foundry/composition.py` | — | complete | internal | SQLite | local | ✅ tests | partial | engine | low | none | — |
| Columns | columns | structured columns for proofs | ✅ `foundry/columns.py` (94) | `capt_solo/foundry/columns.py` | — | complete | internal | n/a | local | ✅ tests | partial | — | low | none | — |
| Proof Ledger | proof ledger | immutable proof ledger | ❌ absent in capt-solo (ProofEngine + governance_audit approximate it) | — | ⚠️ not in biocapt *_mobile scan as distinct | missing (approximated) | — | — | — | — | — | — | — | confirm ProofEngine+governance_audit suffice OR add explicit ledger | **OWNER**: explicit ledger required? |
| Skill Radar | skill radar | skill discovery/radar | ❌ absent in capt-solo | — | ⚠️ forensic lists `SKILL_RADAR` in registry (biocapt) | missing (external) | — | — | — | external-only | external-only | — | — | PORT or confirm SkillFoundry covers | **OWNER**: port vs fold into SkillFoundry? |

## D. Lifecycle / orchestration

| canonical name | aliases | purpose | source evidence | capt_core path | external repo/path | status | public API | persistence | security boundaries | tests | docs | deps | migration impact | proposed completion | unresolved owner decision |
|---------------|--------|---------|-----------------|---------------|-------------------|--------|-----------|------------|-------------------|-------|------|------|-----------------|-------------------|----------------------|
| Lifecycle manager | lifecycle | lifecycle orchestration | ✅ `lifecycle/lifecycle.py` (452) | `capt_solo/lifecycle/lifecycle.py` | — | complete | `Lifecycle` | SQLite | local | ✅ test_v03_lifecycle | ✅ ARCHITECTURE | engine | low | none | — |
| Session store | session | session management | ✅ `lifecycle/sessions.py` (572) | `capt_solo/lifecycle/sessions.py` | — | complete | `SessionStore` | SQLite | local | ✅ test_v03_sessions | partial | engine | low | none | — |
| Manager | manager | high-level manager | ✅ `lifecycle/manager.py` (334) | `capt_solo/lifecycle/manager.py` | — | complete | internal | SQLite | local | ✅ tests | partial | engine | low | none | — |
| Plugin | plugin | Hermes plugin entry | ✅ `plugin/__init__.py` (808) + `plugin.json` | `capt_solo/plugin/__init__.py` | — | complete | `get_plugin` | n/a | local | ✅ test_plugin, test_v04_plugin | ✅ PLUGIN_GUIDE | api, khsb | low | none | — |
| Skills (8) | skills | bundled CAPT skills | ✅ `skills/*` (8 SKILL.md) | `capt_solo/skills/` | — | complete | skill files | n/a | local | ✅ tests | ✅ SKILL_GUIDE | — | low | none | — |
| CLI | capt_cli | command-line interface | ✅ `capt_cli.py` | `capt_cli.py` | — | complete | CLI | n/a | local | ✅ test_v04_cli | ✅ CLI | api | low | none | — |

## E. External-only components discovered in forensic corpus (NOT in capt-solo)

These are recorded because the issue requires inventorying "every component found in the forensic corpus and source repos—not merely components already recognized in CAPT_core." Status reflects capt-solo perspective (all `missing`/`external`).

| canonical name | aliases | purpose | source evidence (external) | external repo/path | status in capt-solo | public API in capt-solo | tests in capt-solo | proposed completion | unresolved owner decision |
|---------------|--------|---------|----------------------------|-------------------|---------------------|------------------------|-------------------|-------------------|----------------------|
| NEDA | neural event-driven arch | thalamic RN | forensic CANONICAL_MODULE_REGISTRY | biocapt-ecosystem modules | missing | — | none | PORT or exclude | **OWNER** |
| QIPC | quantum-inspired consensus | PFC | forensic + code | biocapt-ecosystem | missing | — | none | PORT or exclude | **OWNER** |
| IMMU | immune/constitution | immune | forensic (IMMU verifies bubbles) | biocapt-ecosystem | missing (KnowledgeBubble uses trust, not IMMU) | — | none | PORT or map to trust | **OWNER** |
| CONSC | consciousness/Φ | global workspace | forensic | biocapt-ecosystem | missing | — | none | exclude (metaphorical) or PORT | **OWNER** |
| PLAST | Hebbian/BCM | synapse | forensic | biocapt-ecosystem | missing | — | none | PORT or fold into consolidation | **OWNER** |
| PULSE | LLM gateway | motor cortex | forensic | biocapt-ecosystem | missing | — | none | external gateway; confirm boundary | **OWNER** |
| CIG | causal inference | causal cortex | forensic | biocapt-ecosystem | missing | — | none | PORT or exclude | **OWNER** |
| HDR | hyperdim reasoning | parietal | forensic | biocapt-ecosystem | missing | — | none | PORT or exclude | **OWNER** |
| META | metacognition | ACC | forensic | biocapt-ecosystem | missing | — | none | PORT or exclude | **OWNER** |
| ALLO | allostatic | hypothalamus | forensic | biocapt-ecosystem | missing | — | none | PORT or exclude | **OWNER** |
| RYS | recursive yield | CAPT-RYS bridge | forensic | biocapt-ecosystem / AIM-CAPTRYS | missing | — | none | PORT or exclude | **OWNER** |
| FILT / FSR | attentional filter / feedback regulator | — | forensic (DISABLED, `__slots__` bugs) | biocapt-ecosystem | missing | — | none | PORT w/ bug fix or exclude | **OWNER** |
| +30 more | AIM, ATT, SENS, ... ZKC, CONSTITUTION, AUTONOMY, ... | various | forensic registry (46 registered) | biocapt-ecosystem | missing | — | none | triage per owner | **OWNER** |
| CAPTLANG compiler | captlang | WASM codegen for 30 modules | forensic CAPTLANG_COMPILER_PASS | Biocapt-ecosystem-fullcaptlang | missing | — | none | external build tool; confirm boundary | **OWNER** |

---

## F. Source-of-truth conflicts recorded

| Conflict | Side A | Side B | Resolution |
|----------|--------|--------|------------|
| Version | pyproject `0.1.0` | wheel/docs `0.4.1`, tag `v0.4.0` | Not resolved — owner picks canonical (B2) |
| CTP presence | wheel contains `ctp/journal.py` | committed tree has no `ctp/` (gitignored) | Not resolved — owner approves committing ctp/ (B1) |
| Module count | forensic "188 modules" / "280 modules" | fullcaptlang real source: 83 py + 95 captlang + 30 compiler-known | Forensic counts UNVERIFIED per forensic's own note; used real counts |
| HMC/ECHO/ENGRAM/DREAM | capt-solo absent | biocapt-ecosystem has `*_mobile.py` | Not resolved — owner decides port vs external (B3) |
| Compression | AntiToken char-compression present | forensic: "no explicit summarization layer found" | Recorded; owner decides if summarization required |

---

## G. Census summary

- Components inventoried: **70+** (A–E).
- In capt-solo, committed & complete: **~40** (memory core, CSG, lifecycle, foundry stack, KHSB, plugin, CLI, skills).
- In capt-solo but broken/disconnected: **1** (CTP — built but uncommitted).
- In capt-solo partial: **~6** (episodic via SessionStore, compression=AntiToken only, identity minimal, replay spec-only, autobiographical missing, consent missing, sync missing).
- External-only / missing from capt-solo: **HMC, ECHO, ENGRAM, DREAM, Holographic Memory, autobiographical, consent, synchronization, Proof Ledger (explicit), Skill Radar, NEDA, QIPC, IMMU, CONSC, PLAST, PULSE, CIG, HDR, META, ALLO, RYS, FILT, FSR, +30 registry modules, CAPTLANG compiler**.
- Forensic recommendations: explicitly NOT adopted.

---

## H. Reproduce

```bash
cd /Users/knowurknot/capt-solo
git checkout integration/full-public-architecture
# component presence scan
grep -rIl --include=*.py -E "HMC|ECHO|ENGRAM|DREAM|ClaimGuard|SkillFoundry|Curator|KnowledgeBubble" capt_solo
# ctp tree check
git ls-files capt_solo/ctp/         # empty
# external module check
find /Users/knowurknot/biocapt-ecosystem/primary/biocapt-desktop/modules -name "hmc_mobile.py"
```
