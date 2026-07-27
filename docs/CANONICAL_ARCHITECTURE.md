# CANONICAL ARCHITECTURE — CAPT

**Status:** Architectural source of truth (Phase 2)
**Baseline inventory:** accepted — `docs/BASELINE_EVIDENCE_REPORT.md`, `docs/FULL_ARCHITECTURE_IMPLEMENTATION_MATRIX.md`, `docs/STUB_SPEC_MISSING_REGISTER.md` (commit `33cc37a`)
**Branch:** `integration/full-public-architecture`
**Date:** 2026-07-26
**Issue:** #5

## Governing rules for this document

- The forensic reconstruction is **evidence**, not architectural authority. Current repository layout is an **implementation snapshot**, not automatically the canonical architecture.
- The owner's intent determines the architecture. Implementation converges toward this document; it does not redefine it.
- Every subsystem is assigned a **Canonical Home** (a CAPT layer) and a **Release Target** (CAPT_core / external package / optional plugin / research package / private / undecided).
- Current code location does **not** determine canonical home. Components currently living in `biocapt-ecosystem` are classified by where they *belong*, not where they are.
- Terminology: we **canonicalize**, **integrate**, **adopt the canonical implementation**, **merge the canonical implementation**, or **reimplement the canonical interface**. We do not "port bioCAPT modules."
- No runtime code changed. No public APIs changed. This is architecture only.

## Layer index

| Layer | Name | Canonical role |
|-------|------|----------------|
| 0 | Identity | Self/agent identity and boundary |
| 1 | Constitution | Governing principles, invariants, allowed behavior |
| 2 | Reasoning | Inference, causal/hyperdim/metacognitive reasoning, consensus, recursive yield |
| 3 | Memory | All memory kinds, storage, compression, retrieval, consolidation, lifecycle of memories |
| 4 | Knowledge | Knowledge structures, bubbles, knowledge bus, curation |
| 5 | Trust | Trust, evidence, provenance, proof, claim verification, immune checks |
| 6 | Execution | Lifecycle, procedures, sessions, transactions, runtime/CLI |
| 7 | Communication | LLM/external gateways, message routing |
| 8 | Governance | Audit, release gates, policy enforcement |
| 9 | Skills | Skill foundry, plugin SDK, bundled skills |
| 10 | Learning | Adaptation, consolidation-as-learning, continuous learning |
| 11 | External Interfaces | DSL/compiler, SDKs, bridges to external systems |

---

## Layer 0 — Identity

### L0.1 Identity subsystem
- **Purpose:** Establish and maintain the agent's self-identity, boundaries, and identity-scoped state.
- **Responsibilities:** identity record lifecycle; scoping of memories/sessions to an identity; identity verification for privileged operations.
- **Public APIs:** `IdentityStore.establish()`, `IdentityStore.resolve()`, `IdentityStore.scoped_state()`.
- **Dependencies:** L3 Memory (storage), L5 Trust (identity verification).
- **Upward dependencies:** consumed by Lifecycle, Governance, Trust.
- **Downward dependencies:** MemoryEngine, SQLite.
- **Persistent state:** `identities` table (currently only implicit in `lifecycle/semantic.py` + `engine.py`; to be made explicit).
- **Communication model:** in-process calls.
- **Failure boundaries:** identity resolution failure → operate in anonymous/local-only mode; never impersonate.

---

## Layer 1 — Constitution

### L1.1 Constitution
- **Purpose:** Encode CAPT's governing invariants, allowed behaviors, and non-negotiable constraints (anti-extraction, local-first, privacy defaults).
- **Responsibilities:** hold constitutional rules; expose them to Governance and Reasoning; reject operations violating invariants.
- **Public APIs:** `Constitution.rules()`, `Constitution.check(operation)`.
- **Dependencies:** none (foundational).
- **Upward dependencies:** Governance, Reasoning, Execution consult it.
- **Downward dependencies:** none.
- **Persistent state:** constitution document (versioned); optional `constitution_audit` table.
- **Communication model:** in-process; read-only reference.
- **Failure boundaries:** constitution load failure → fail closed (refuse operations requiring constitutional check).

---

## Layer 2 — Reasoning

### L2.1 Reasoning Core
- **Purpose:** Orchestrate inference across reasoning strategies; route to specialized reasoners.
- **Responsibilities:** request routing, strategy selection, aggregation of reasoning outputs, confidence reporting.
- **Public APIs:** `Reasoner.reason(query, strategy)`, `Reasoner.route()`.
- **Dependencies:** L5 Trust (confidence), L3 Memory (context), L7 Communication (model gateway).
- **Upward dependencies:** Execution, Skills, Governance.
- **Downward dependencies:** CIG, HDR, META, CONSC, QIPC, RYS, Cognitive Loop.
- **Persistent state:** reasoning traces (ephemeral or L3-backed).
- **Communication model:** in-process; may call L7 gateway.
- **Failure boundaries:** reasoner unavailable → degrade to available strategy; never return unverified as verified.

### L2.2 Causal Inference (CIG)
- **Purpose:** Causal reasoning over events/memories.
- **Canonical Home:** L2 Reasoning. **Release Target:** CAPT_core (adopt canonical implementation).
- **Current Location:** repository `biocapt-ecosystem`, path `primary/biocapt-desktop/modules/cig_mobile.py`.
- **Public APIs:** `CausalModel.infer()`, `CausalModel.explain()`.
- **Dependencies:** L3 Memory, L5 Trust.
- **Persistent state:** causal graph (L3-backed).
- **Failure boundaries:** inconclusive → return low-confidence, do not assert causation.

### L2.3 Hyperdimensional Reasoning (HDR)
- **Purpose:** Hyperdimensional/vector-symbolic reasoning.
- **Canonical Home:** L2 Reasoning. **Release Target:** CAPT_core (adopt canonical implementation; optional Rust accel external).
- **Current Location:** `biocapt-ecosystem/.../hdr_mobile.py` (+ `hdr.rs`).
- **Public APIs:** `HDR.bind()`, `HDR.query()`.
- **Dependencies:** L3 Memory (HMC for VSA), numpy.
- **Failure boundaries:** dimension mismatch → error, no silent truncation.

### L2.4 Metacognition (META)
- **Purpose:** Self-monitoring, confidence calibration, strategy selection.
- **Canonical Home:** L2 Reasoning. **Release Target:** CAPT_core (adopt canonical implementation).
- **Current Location:** `biocapt-ecosystem/.../meta_mobile.py`.
- **Public APIs:** `Metacognition.evaluate()`, `Metacognition.advise()`.
- **Dependencies:** L5 Trust, L2.1.
- **Failure boundaries:** metacognitive failure → defer to explicit reasoning.

### L2.5 Global Workspace / Consciousness (CONSC, Φ)
- **Purpose:** Global workspace integration (analogical mapping to biological consciousness).
- **Canonical Home:** L2 Reasoning. **Release Target:** research package (default) — owner decides public/private boundary.
- **Current Location:** `biocapt-ecosystem/.../consc_mobile.py`.
- **Public APIs:** `Workspace.broadcast()`, `Workspace.ignition()`.
- **Dependencies:** all reasoning modules.
- **Failure boundaries:** Φ computation failure → non-fatal, degrade to direct routing.

### L2.6 Quantum-Inspired Consensus (QIPC)
- **Purpose:** Consensus over distributed/uncertain beliefs.
- **Canonical Home:** L2 Reasoning. **Release Target:** research package (default) — owner decides boundary.
- **Current Location:** `biocapt-ecosystem/.../qipc_mobile.py` (+ `qipc.rs`).
- **Public APIs:** `Consensus.propose()`, `Consensus.resolve()`.
- **Dependencies:** L5 Trust.
- **Failure boundaries:** no quorum → retain uncertainty.

### L2.7 Recursive Yield / RYS Bridge
- **Purpose:** Recursive yield scheduling; bridge to CAPT-RYS external system.
- **Canonical Home:** L2 Reasoning (yield) + L11 External (bridge). **Release Target:** external package / optional plugin — owner decides boundary + security exposure.
- **Current Location:** `biocapt-ecosystem/.../rys_mobile.py`; `AIM-CAPTRYS`.
- **Public APIs:** `RYS.yield()`, `RYSBridge.connect()`.
- **Dependencies:** L6 Execution, L11.
- **Failure boundaries:** bridge down → local-only yield, no external call.

### L2.8 Cognitive Loop
- **Purpose:** Perceive–reason–act control loop.
- **Canonical Home:** L2 Reasoning. **Release Target:** CAPT_core (adopt canonical implementation).
- **Current Location:** `biocapt-ecosystem` registry (COGNITIVE_LOOP).
- **Public APIs:** `CognitiveLoop.step()`.
- **Dependencies:** L2.1, L6, L7.
- **Failure boundaries:** step failure → retry with backoff, then halt loop.

---

## Layer 3 — Memory

### L3.1 MemoryEngine (core store)
- **Purpose:** SQLite-backed canonical memory store.
- **Responsibilities:** CRUD for memories, tags, nodes, edges, aliases, conflicts, retention, lifecycle transitions.
- **Public APIs:** `MemoryEngine.store/get/update/delete/search/export_json`, `integrity_check()`, `migrate()`.
- **Dependencies:** sqlite3, L0 Identity (scoping), L5 Trust (trust scores).
- **Upward dependencies:** all layers.
- **Downward dependencies:** SQLite, core.config.
- **Persistent state:** 32 tables, SCHEMA_VERSION=4.
- **Communication model:** in-process.
- **Failure boundaries:** DB corrupt → refuse writes, expose read-only + backup/restore.

### L3.2 CSG (Cognitive State Graph)
- **Purpose:** Cognitive state graph: predict next state, path, centrality, history.
- **Public APIs:** `CSG.predict()`, `CSG.path()`, `CSG.centrality()`, `CSG.history()`.
- **Dependencies:** L3.1, L0.
- **Persistent state:** `memory_nodes`, `memory_edges`.
- **Failure boundaries:** graph inconsistency → rebuild from memories.

### L3.3 Episodic Memory (canonical: ECHO)
- **Purpose:** Time-ordered episodic timeline with retention window and time-travel.
- **Canonical Home:** L3 Memory. **Release Target:** CAPT_core.
- **Current Location:** CAPT_core has `lifecycle/sessions.py` (SessionStore) as the current implementation; canonical ECHO interface to be adopted. External reference: `biocapt-ecosystem/.../echo_mobile.py` (ring buffer, 90-day retention).
- **Public APIs (canonical):** `EpisodicMemory.append()`, `EpisodicMemory.window(retention)`, `EpisodicMemory.timetravel()`.
- **Dependencies:** L3.1, L3.12 (TTL/retention).
- **Persistent state:** `sessions`, `session_events`, `session_checkpoints`.
- **Failure boundaries:** retention overflow → drop oldest, never block append.

### L3.4 Semantic Memory
- **Purpose:** Semantic index of concepts.
- **Public APIs:** `SemanticIndex.index()`, `SemanticIndex.query()`.
- **Dependencies:** L3.1.
- **Persistent state:** `semantic_index_metadata`.
- **Failure boundaries:** index stale → rebuild.

### L3.5 Procedural Memory
- **Purpose:** Procedures and their run history.
- **Public APIs:** `ProcedureStore.define()`, `ProcedureStore.run()`.
- **Dependencies:** L3.1, L6.
- **Persistent state:** `procedures`, `procedure_versions`, `procedure_runs`.
- **Failure boundaries:** procedure missing → explicit error.

### L3.6 Prospective Memory
- **Purpose:** Future/intended memories and reminders.
- **Public APIs:** `ProspectiveMemory.schedule()`, `ProspectiveMemory.due()`.
- **Dependencies:** L3.1, L3.3.
- **Persistent state:** `prospective_memories`.
- **Failure boundaries:** due-check failure → skip silently, log.

### L3.7 Autobiographical Memory
- **Purpose:** Self/narrative timeline aggregating episodic + semantic + prospective into a coherent identity story.
- **Canonical Home:** L3 Memory. **Release Target:** CAPT_core (design canonical interface; no prior implementation exists).
- **Current Location:** absent in CAPT_core and bioCAPT (no source found).
- **Public APIs (canonical):** `AutobiographicalMemory.narrate()`, `AutobiographicalMemory.anchor()`.
- **Dependencies:** L3.3, L3.4, L3.6, L0.
- **Persistent state:** derived view over L3 stores (+ optional `autobiography` table).
- **Failure boundaries:** partial source → narrate from available, mark gaps.

### L3.8 HMC (Holographic Memory Core)
- **Purpose:** FFT circular-convolution (HRR/VSA) holographic memory — fixed-dimension, content-addressable, lossy-by-design compression.
- **Canonical Home:** L3 Memory. **Release Target:** CAPT_core (canonicalize numpy implementation; optional Rust accel as external package).
- **Current Location:** repository `biocapt-ecosystem`, path `primary/biocapt-desktop/modules/hmc_mobile.py` (+ `hmc.rs`, `rustfft`).
- **Public APIs (canonical):** `HMC.store(key, value)`, `HMC.query(key)`, `HMC.unbind()`.
- **Dependencies:** L3.1 (persistence), numpy; optional `biocapt_rust.hmc`.
- **Persistent state:** `holograms` table (SQLite).
- **Communication model:** in-process.
- **Failure boundaries:** key collision → superposition merge with documented fidelity loss; Rust accel failure → fall back to numpy.

### L3.9 ENGRAM (long-term encode)
- **Purpose:** Long-term encoding/consolidation of HMC/ECHO content into durable weights.
- **Canonical Home:** L3 Memory. **Release Target:** CAPT_core (merge canonical implementation into MemoryEngine consolidation).
- **Current Location:** `biocapt-ecosystem/.../engram_mobile.py`.
- **Public APIs (canonical):** `Engram.encode()`, `Engram.consolidate()`.
- **Dependencies:** L3.8, L3.3, L10.
- **Persistent state:** encoded weights (L3.1-backed).
- **Failure boundaries:** encode failure → keep source memories, retry.

### L3.10 DREAM / Consolidation
- **Purpose:** Offline consolidation loop — replay + integrate memories into long-term structure.
- **Canonical Home:** L3 Memory (consolidation) + L10 Learning. **Release Target:** CAPT_core (canonicalize consolidation loop; current lifecycle transitions are a partial stand-in).
- **Current Location:** `biocapt-ecosystem/.../dream_consolidator_mobile.py`, `dream_cycle_rpc_mobile.py`.
- **Public APIs (canonical):** `Consolidation.run()`, `Consolidation.schedule()`.
- **Dependencies:** L3.3, L3.8, L3.9, L10.
- **Persistent state:** consolidation checkpoints (L3.1).
- **Failure boundaries:** interrupted → resumable; never duplicate.

### L3.11 Context Builder
- **Purpose:** Assemble context windows from memory for reasoning/LLM.
- **Public APIs:** `ContextBuilder.build(scope)`.
- **Dependencies:** L3.1, L3.2, L3.4.
- **Persistent state:** `context_builds`, `context_build_items`.
- **Failure boundaries:** over-budget → truncate by relevance.

### L3.12 Search / Retrieval
- **Purpose:** Memory retrieval and search.
- **Public APIs:** `Search.query()`, `Search.rank()`.
- **Dependencies:** L3.1, L3.4.
- **Persistent state:** indexes in L3.1.
- **Failure boundaries:** no results → empty, not error.

### L3.13 Deduplicate
- **Purpose:** Detect/merge duplicate memories.
- **Public APIs:** `Deduplicate.check()`, `Deduplicate.merge()`.
- **Dependencies:** L3.1, L3.14.
- **Failure boundaries:** ambiguous → keep both, flag conflict.

### L3.14 Normalize
- **Purpose:** Normalize memory content for comparison/storage.
- **Public APIs:** `Normalize.content()`.
- **Dependencies:** none.
- **Failure boundaries:** unparseable → preserve raw + marker.

### L3.15 Memory Compression (Anti-Token-Extraction + holographic)
- **Purpose:** Two distinct mechanisms — (a) AntiToken: deterministic token-reduction preserving decision-relevant structure (fidelity-guarded); (b) HMC holographic: fixed-dim lossy storage compression.
- **Canonical Home:** L3 Memory. **Release Target:** CAPT_core (both; AntiToken already present, HMC per L3.8).
- **Current Location:** AntiToken in CAPT_core `memory/antitoken.py`; holographic in `biocapt-ecosystem/.../hmc_mobile.py`.
- **Public APIs:** `AntiToken.extract/validate/render`, `HMC.store/query`.
- **Dependencies:** L3.1, numpy.
- **Failure boundaries:** fidelity check fail → fall back to less-compressed form; never drop negation/uncertainty/warnings.

### L3.16 Retrieval Feedback / Adaptation
- **Purpose:** Adaptive retrieval from feedback.
- **Public APIs:** `FeedbackStore.record()`, `RetrievalAdaptation.adapt()`.
- **Dependencies:** L3.12, L10.
- **Persistent state:** `retrieval_feedback`, `retrieval_adaptation`.
- **Failure boundaries:** feedback loop unstable → clamp.

### L3.17 Replay
- **Purpose:** Replay memories/sessions for recovery/consolidation.
- **Canonical Home:** L3 Memory. **Release Target:** CAPT_core (canonicalize replay API; currently only referenced by capt-recovery skill).
- **Current Location:** CAPT_core docs/skills (capt-recovery); no dedicated module.
- **Public APIs (canonical):** `Replay.session(id)`, `Replay.memory(id)`.
- **Dependencies:** L3.1, L3.3.
- **Failure boundaries:** replay of corrupt record → skip + log.

### L3.18 TTL / Retention
- **Purpose:** Retention policies and expiry.
- **Public APIs:** `RetentionPolicy.apply()`, `TTL.expire()`.
- **Dependencies:** L3.1, L3.3.
- **Persistent state:** `memory_retention_policies`.
- **Failure boundaries:** policy missing → retain (safe default).

### L3.19 Temporal Ordering
- **Purpose:** Time-ordered memory access.
- **Public APIs:** implicit via timestamps.
- **Dependencies:** L3.1 (models timestamps).
- **Failure boundaries:** clock skew → monotonic guard.

### L3.20 Export / Import
- **Purpose:** JSON export/import of memories (portable, local).
- **Public APIs:** `MemoryEngine.export_json()`, `import_json()`.
- **Dependencies:** L3.1.
- **Failure boundaries:** import conflict → merge policy, never overwrite silently.

### L3.21 Migration
- **Purpose:** Schema version migration (forward-only).
- **Public APIs:** `MemoryEngine.migrate(target=SCHEMA_VERSION)`.
- **Dependencies:** L3.1, L8 (governance audit).
- **Persistent state:** `schema_version`.
- **Failure boundaries:** migration fail → restore from backup, abort.

### L3.22 Synchronization
- **Purpose:** Multi-instance memory sync.
- **Canonical Home:** L3 Memory + L11 External. **Release Target:** undecided — owner decides (network surface = security exposure + public/private boundary).
- **Current Location:** absent in CAPT_core and bioCAPT scan.
- **Public APIs (canonical):** `Sync.push()`, `Sync.pull()` (TBD).
- **Dependencies:** L3.1, L5, L11.
- **Failure boundaries:** conflict → last-writer-wins with provenance, never silent loss.

### L3.23 Consent
- **Purpose:** Track user consent for data handling/operations.
- **Canonical Home:** L3 Memory (scoped to identity) — privacy-adjacent, reviewed at integration for security exposure.
- **Release Target:** CAPT_core (canonicalize local consent ledger).
- **Current Location:** absent in CAPT_core and bioCAPT scan.
- **Public APIs (canonical):** `Consent.grant()`, `Consent.revoke()`, `Consent.required_for(op)`.
- **Dependencies:** L0, L5.
- **Persistent state:** `consent_records` (local-only).
- **Failure boundaries:** missing consent → refuse operation, never assume granted.

### L3.24 Secrets Screening
- **Purpose:** Screen secrets before persistence.
- **Public APIs:** `secrets.screen(text)`.
- **Dependencies:** none.
- **Persistent state:** none (stateless).
- **Failure boundaries:** detector uncertain → redact + flag.

---

## Layer 4 — Knowledge

### L4.1 Knowledge Bubbles
- **Purpose:** Portable, verifiable knowledge packages (HMC/ECHO/PLAST bundles).
- **Public APIs:** `KnowledgeBubbleRuntime.pack()`, `unpack()`, `verify()`, quarantine isolation.
- **Dependencies:** L3.8, L3.3, L5 (IMMU-style verification), L8.
- **Persistent state:** `knowledge_bubbles`, `.capt-bubble.json`.
- **Failure boundaries:** verification fail → quarantine, never merge.

### L4.2 KHSB (Knowledge/Hermes Service Bus)
- **Purpose:** In-process pub/sub + request/reply bus for knowledge/events.
- **Public APIs:** `KHSB.publish/subscribe/request/reply/ack`.
- **Dependencies:** L3, L6.
- **Persistent state:** in-memory (ephemeral).
- **Failure boundaries:** subscriber error → isolate, continue.

### L4.3 Knowledge Curation (Curator)
- **Purpose:** Curate knowledge/skills into trusted sets.
- **Public APIs:** `Curator.review()`, `Curator.promote()`.
- **Dependencies:** L4.1, L5, L9.
- **Persistent state:** curation records (L3.1).
- **Failure boundaries:** curation conflict → hold for review.

### L4.4 Semantic Index
- **Purpose:** Indexed concept store (see L3.4; cross-listed as knowledge structure).
- **Public APIs:** `SemanticIndex.*`.
- **Dependencies:** L3.1.

---

## Layer 5 — Trust

### L5.1 Trust Engine
- **Purpose:** Trust scoring of memories/evidence/agents.
- **Public APIs:** `Trust.score()`, `Trust.aggregate()`.
- **Dependencies:** L3, L5.2, L5.3.
- **Persistent state:** trust scores (L3.1).
- **Failure boundaries:** unknown source → default low trust.

### L5.2 Evidence Engine
- **Purpose:** Collect, structure, and weigh evidence for claims.
- **Public APIs:** `Evidence.collect()`, `Evidence.weight()`.
- **Dependencies:** L3, L5.4.
- **Persistent state:** `proof_evidence`.
- **Failure boundaries:** insufficient evidence → claim unverified.

### L5.3 Provenance
- **Purpose:** Track origin and derivation of every memory/claim.
- **Public APIs:** `Provenance.trace(id)`.
- **Dependencies:** L3, L5.2.
- **Persistent state:** provenance graph (L3.1).
- **Failure boundaries:** gap → mark provenance unknown.

### L5.4 ClaimGuard
- **Purpose:** Verify claims; support scoped downgrade of claims under trust thresholds.
- **Public APIs:** `ClaimGuard.verify()`, `ClaimGuard.downgrade()`.
- **Dependencies:** L5.1, L5.2, L5.5.
- **Persistent state:** claim records (L3.1).
- **Failure boundaries:** unverifiable → scoped downgrade, never assert.

### L5.5 Proof Engine
- **Purpose:** Proof/evidence integrity and requirement enforcement.
- **Public APIs:** `ProofEngine.prove()`, `ProofEngine.check_requirements()`.
- **Dependencies:** L5.2, L5.3, L8.
- **Persistent state:** `proof_evidence`, `proof_requirements`.
- **Failure boundaries:** requirement unmet → fail proof, report gap.

### L5.6 Proof Ledger
- **Purpose:** Canonical immutable ledger of proofs/receipts (currently implemented by ProofEngine + Governance audit; to be merged into an explicit ledger).
- **Canonical Home:** L5 Trust. **Release Target:** CAPT_core (merge canonical implementation).
- **Current Location:** CAPT_core `foundry/proof.py` + `foundry/governance.py` (approximates).
- **Public APIs (canonical):** `ProofLedger.append(receipt)`, `ProofLedger.verify(id)`.
- **Dependencies:** L5.5, L8.
- **Persistent state:** `governance_audit` + explicit ledger table.
- **Failure boundaries:** ledger tamper → detect, refuse.

### L5.7 IMMU (Immune / Constitution verification)
- **Purpose:** Immune-style verification/quarantine of knowledge before merge (biological analogue: horizontal gene transfer check).
- **Canonical Home:** L5 Trust. **Release Target:** CAPT_core (adopt canonical implementation; currently Trust Engine is the partial stand-in).
- **Current Location:** `biocapt-ecosystem/.../immu_mobile.py` (forensic notes NO DEFCON/SHA3 — doc drift).
- **Public APIs (canonical):** `IMMU.scan()`, `IMMU.quarantine()`.
- **Dependencies:** L4.1, L5.1.
- **Failure boundaries:** scan fail → quarantine, never merge unverified.

---

## Layer 6 — Execution

### L6.1 Lifecycle Manager
- **Purpose:** Orchestrate memory/knowledge lifecycle.
- **Public APIs:** `Lifecycle.transition()`, `Lifecycle.state()`.
- **Dependencies:** L3, L8.
- **Persistent state:** lifecycle transitions (L3.1).
- **Failure boundaries:** invalid transition → reject.

### L6.2 Session Store
- **Purpose:** Session management (see L3.3 Episodic — current implementation of episodic memory).
- **Public APIs:** `SessionStore.create/append/close`.
- **Dependencies:** L3.1.

### L6.3 Procedure Store
- **Purpose:** Procedure definitions/runs (see L3.5 Procedural).
- **Public APIs:** `ProcedureStore.*`.
- **Dependencies:** L3.1, L6.1.

### L6.4 Manager (orchestration)
- **Purpose:** High-level orchestration of subsystems.
- **Public APIs:** `Manager.dispatch()`.
- **Dependencies:** all.
- **Failure boundaries:** subsystem down → degrade.

### L6.5 CTP (Cognitive Transaction Protocol)
- **Purpose:** Append-only local transaction journal with immutable receipts, idempotency, integrity.
- **Canonical Home:** L6 Execution. **Release Target:** CAPT_core (restore verified wheel source into committed tree; currently gitignored/disconnected).
- **Current Location:** built in wheel `capt_solo/ctp/journal.py` (8048 B) + `__init__.py`; **absent from committed tree** (`.gitignore` has `ctp/`).
- **Public APIs:** `CTPRuntime.begin/commit/abort`, `Receipt`.
- **Dependencies:** core.config, core.errors, L8 (audit).
- **Persistent state:** JSONL journal.
- **Failure boundaries:** double-finalize → idempotency guard; corruption → recover from last consistent entry.

### L6.6 CLI
- **Purpose:** Command-line interface.
- **Public APIs:** `capt_cli` commands.
- **Dependencies:** L6.1, L3, L5.
- **Failure boundaries:** bad arg → usage error.

### L6.7 Runtime SDK
- **Purpose:** Public runtime API surface (`capt_solo.api`).
- **Public APIs:** `health()`, `CTPRuntime`, `KHSB`, `MemoryEngine`.
- **Dependencies:** all.
- **Release Target:** CAPT_core.

---

## Layer 7 — Communication

### L7.1 PULSE (LLM Gateway)
- **Purpose:** Gateway to LLM/model providers (biological motor-cortex analogue).
- **Canonical Home:** L7 Communication + L11 External. **Release Target:** optional plugin / external package — owner decides (network/LLM boundary = security exposure + public/private boundary).
- **Current Location:** `biocapt-ecosystem/.../pulse_mobile.py`.
- **Public APIs:** `PULSE.complete()`, `PULSE.route()`.
- **Dependencies:** L2.1, L11.
- **Failure boundaries:** provider down → local fallback or explicit failure; never send secrets without consent.

---

## Layer 8 — Governance

### L8.1 Governance
- **Purpose:** Audit, governance receipts, policy enforcement.
- **Public APIs:** `Governance.audit()`, `Governance.receipt()`.
- **Dependencies:** L5, L6.5, L3.21.
- **Persistent state:** `governance_audit`.
- **Failure boundaries:** audit fail → block operation.

### L8.2 Release Gates
- **Purpose:** `verify_runtime.py`, `doctor.sh`, `verify.sh` — structured release validation (schema, migration backup, proof integrity, secret screening, SQL boundary, etc.).
- **Public APIs:** CLI entrypoints.
- **Dependencies:** all.
- **Failure boundaries:** any `fail` → non-zero exit.

### L8.3 Migration Governance
- **Purpose:** Ensure migrations are backed up and reversible where possible.
- **Dependencies:** L3.21, L8.1.

---

## Layer 9 — Skills

### L9.1 Skill Foundry
- **Purpose:** Publish/validate skills; canonical home for skill lifecycle.
- **Public APIs:** `SkillFoundry.publish()`, `validate()`, `SkillRadar` merged as capability.
- **Dependencies:** L5, L4, L8.
- **Persistent state:** `skills`, `skill_candidates`.
- **Failure boundaries:** invalid skill → reject, quarantine.

### L9.2 Skill Radar
- **Purpose:** Skill discovery/radar — **merged into Skill Foundry** as a capability (not a separate subsystem).
- **Canonical Home:** L9 Skills (within Skill Foundry). **Release Target:** CAPT_core (merge canonical implementation).
- **Current Location:** `biocapt-ecosystem` registry (`SKILL_RADAR`).
- **Public APIs:** `SkillFoundry.radar()`.
- **Dependencies:** L9.1.

### L9.3 Plugin SDK
- **Purpose:** Hermes plugin entry + extension API.
- **Public APIs:** `get_plugin()`, plugin.json schema.
- **Dependencies:** L6.7, L11.
- **Release Target:** CAPT_core.

### L9.4 Bundled Skills (8)
- **Purpose:** Ships capt-arch-decision, capt-bootstrap, capt-debug, capt-knowledge-capture, capt-memory-review, capt-recovery, capt-session-recap, capt-transaction.
- **Release Target:** CAPT_core.

---

## Layer 10 — Learning

### L10.1 Learning / Adaptation
- **Purpose:** Parameter/behavior adaptation from experience.
- **Canonical Home:** L10 Learning. **Release Target:** CAPT_core (adopt canonical implementation).
- **Current Location:** `biocapt-ecosystem` registry (LEARNING, ADAPTATION).
- **Public APIs:** `Learning.adapt()`.
- **Dependencies:** L3.16, L3.10.
- **Failure boundaries:** unstable → clamp.

### L10.2 Consolidation-as-Learning
- **Purpose:** DREAM consolidation as the learning mechanism (see L3.10).
- **Dependencies:** L3.8–L3.10.

### L10.3 Continuous Learning
- **Purpose:** Ongoing learning loop.
- **Canonical Home:** L10 Learning. **Release Target:** CAPT_core (adopt canonical implementation) — note `capt/modules/continuous_learning_module.py` (792 LOC) exists externally as an orphan; owner decides inclusion.
- **Current Location:** `biocapt-ecosystem/capt/modules/continuous_learning_module.py` (not in registry).
- **Public APIs:** `ContinuousLearning.step()`.
- **Dependencies:** L10.1, L3.

### L10.4 OUROBOROS
- **Purpose:** Self-referential learning loop (research).
- **Release Target:** research package (default) — owner decides boundary.
- **Current Location:** `biocapt-ecosystem` registry.

---

## Layer 11 — External Interfaces

### L11.1 CAPTLANG (compiler/DSL)
- **Purpose:** CAPT dialect compiler → WASM codegen for 30 modules.
- **Canonical Home:** L11 External Interfaces. **Release Target:** external package (build tooling, not runtime).
- **Current Location:** `Biocapt-ecosystem-fullcaptlang` (docs/CAPTLANG_DIALECT.md, src/captlang/, codegen_wasm.py, Makefile.captlang).
- **Public APIs:** `captlang compile <src>`.
- **Dependencies:** none at runtime.
- **Failure boundaries:** compile fail → report, no runtime impact.

### L11.2 Plugin SDK (cross-ref L9.3)
- **Release Target:** CAPT_core.

### L11.3 Runtime SDK (cross-ref L6.7)
- **Release Target:** CAPT_core.

### L11.4 RYS Bridge (cross-ref L2.7)
- **Release Target:** external package / optional plugin — owner decides.

### L11.5 Hermes Plugin Interface
- **Purpose:** Bridge to Hermes agent runtime.
- **Release Target:** CAPT_core (plugin entry).
- **Dependencies:** L9.3.

---

## Cross-cutting: brain-lobe cognitive modules (registry group)

The bioCAPT registry lists ~46 modules (NEDA, QIPC, CONSC, PLAST, CIG, HDR, META, ALLO, RYS, FILT, FSR, +30). Their canonical homes by function:

- Reasoning (L2): CIG, HDR, META, CONSC, QIPC, RYS, cognitive loop, SWARM_DECOMP, AGENT_ROUTER, TOOL_SYNTH.
- Learning (L10): PLAST, LEARNING, ADAPTATION, OUROBOROS, MFO, SWC, SCF.
- Trust (L5): IMMU.
- Memory (L3): HMC, ECHO, ENGRAM, DREAM (covered above).
- Identity (L0): identity-related.
- Communication (L7): COMM, PULSE.
- Execution (L6): EXEC, MOTOR, INHIB, ITC, TSCC, CREAT, ACTIVE_INF, COGNITIVE_LOOP.
- Knowledge (L4): BELIEF_GRAPH, CAUSAL_RSN, ANALOGICAL, CONCEPT_ALG, TEMPORAL_RSN, EMERGENCE_DET, CURIOSITY, EPISTEMIC, VALUE_ALIGN, TOM, NEUR, HOMEO, STRESS, RECOV, AUTONOMY, CONSTITUTION, BUG_BOUNTY, ZKC, etc.

**Default canonical decision:** core memory/knowledge/trust/proof/skill/execution subsystems ship in CAPT_core. Broader brain-lobe modules default to **research package** unless the owner includes them in the public release (public/private boundary decision). FILT/FSR are DISABLED in source (`__slots__` bugs) — fix-then-canonicalize if included.

---

## Architectural conflicts discovered (recorded, not silently resolved)

1. **CTP location vs gitignore** — CTP is imported by core but gitignored and absent from tree. Canonical home = L6 Execution, CAPT_core. Resolution: restore verified wheel source (autonomous; not a boundary/licensing/security/irreconcilable issue).
2. **Version identity** — pyproject `0.1.0` vs wheel/docs `0.4.1` vs tag `v0.4.0`. Canonical version must be set. → **OWNER: irreconcilable canonical behavior (which version is canonical)**.
3. **ECHO vs SessionStore** — SessionStore is the current episodic implementation; ECHO is the canonical episodic interface. Resolution: adopt ECHO canonical interface, merge SessionStore into it (autonomous).
4. **Proof Ledger vs ProofEngine+governance** — Proof Ledger is canonical; current code approximates it. Resolution: merge into explicit ledger (autonomous).
5. **Skill Radar vs Skill Foundry** — Radar is a Skill Foundry capability. Resolution: merge (autonomous).
6. **IMMU vs Trust Engine** — IMMU is the verification/quarantine mechanism under Trust. Resolution: adopt IMMU as canonical verification (autonomous; note forensic doc-drift NO DEFCON/SHA3).
7. **Memory compression duality** — AntiToken (token-reduction) and HMC holographic (storage) are distinct, both canonical. Not a conflict; documented as two mechanisms.
8. **Metaphorical mappings** — CONSC/Φ, FILT/FSR, "holographic" are biological analogues. Resolution: preserve terminology, clarify analogical vs algorithmic-faithful per issue rules (owner confirms for research-package items).

---

## Components whose canonical home changed vs Phase 1 inventory

| Component | Phase 1 framing | Canonical decision (this doc) |
|-----------|-----------------|-------------------------------|
| HMC | "missing (external)" | L3 Memory, CAPT_core (canonicalize) |
| ECHO | "missing (external)" / SessionStore partial | L3 Memory canonical episodic, CAPT_core (merge) |
| ENGRAM | "missing (external)" | L3 Memory, CAPT_core (merge) |
| DREAM | "missing (external)" | L3 Memory + L10 Learning, CAPT_core (canonicalize) |
| CTP | "disconnected / external" | L6 Execution, CAPT_core (restore from wheel) |
| Proof Ledger | "missing (approximated)" | L5 Trust, CAPT_core (merge) |
| Skill Radar | "missing (external)" | L9 Skills within Skill Foundry, CAPT_core (merge) |
| IMMU | "missing (external)" | L5 Trust, CAPT_core (adopt) |
| Brain-lobe modules (NEDA…) | "missing (external)" | assigned to L2/L5/L10/etc.; default research package |
| Autobiographical | "missing" | L3 Memory, CAPT_core (design canonical interface) |
| Consent | "missing" | L3 Memory (privacy-reviewed), CAPT_core (canonicalize) |
| Synchronization | "missing" | L3 + L11; **undecided** (owner: security + boundary) |
