# CAPT_CANON — Constitutional Architecture

**Status:** Highest-level architectural document in CAPT. Everything else derives from it.
**Historical baseline:** Phase 2 architecture accepted at `a2f0630`; Phase 1
inventory accepted at `33cc37a`.
**Current release line:** `0.5.x`
**Date reconciled:** 2026-07-29

> This document is an engineering constitution, not marketing. It exists so that future implementation cannot accidentally redefine CAPT. Code changes conform to this architecture. The architecture does not drift to match whatever code happens to exist.

---

## 1. Core Philosophy

CAPT is a local-first verification substrate with cognitive-runtime services.
Its purpose is not a feature set; it is a *discipline*:

- **Cognition is modular and inspectable.** Every mental function is a subsystem with explicit responsibilities, dependencies, and failure boundaries — not a monolith.
- **Truth is earned, not asserted.** Claims are only as strong as the evidence and provenance behind them. The system records uncertainty rather than hiding it.
- **The agent belongs to the user.** Local-first, privacy-preserving, and degradable-by-default are not options; they are the baseline.
- **Architecture governs implementation.** When code and architecture conflict, the code changes — not the architecture. Exceptions require explicit owner approval recorded against a named invariant.
- **Biological terminology is a design language, not decoration.** Where CAPT uses hippocampus/holographic/consolidation analogues, the mapping is either algorithmically faithful or explicitly analogical. Neither is stripped for convenience.

### Public architecture

ADR-0008 defines six public pillars: Identity & Scope, Evidence, Verification,
Context, Transactions, and Governance. This is the public mental model, not a
replacement for the constitutional L0-L11 ownership layers or the subsystem
registry. It does not require six physical packages.

---

## 2. Architectural Invariants

These are laws. Future implementations may not violate them without explicit owner approval, recorded with the invariant ID and rationale.

| ID | Invariant | Meaning |
|----|-----------|---------|
| I-01 | Local-first by default | No operation requires a network. Remote capabilities are opt-in and fail safe offline. |
| I-02 | Evidence before assertion | No claim enters Trust/Knowledge without linked evidence and provenance. |
| I-03 | Deterministic where practical | Core memory/transaction/proof logic is deterministic; randomness is bounded and seeded where feasible. |
| I-04 | Explicit uncertainty | Confidence is always represented; unknown is a first-class value, never silently resolved to true/false. |
| I-05 | Privacy-preserving defaults | Secrets are screened, consent is required for sensitive handling, export is local-only by default. |
| I-06 | Modular cognition | Subsystems have single responsibilities and explicit interfaces; no hidden cross-subsystem state. |
| I-07 | Bounded failure domains | A subsystem failure is contained; it does not cascade into silent corruption of others. |
| I-08 | Backward-compatible public contracts | Public APIs and persisted schemas evolve with migration; breaking changes require a version + migration path. |
| I-09 | Optional capabilities degrade independently | An optional subsystem (e.g. Anti-Token-Extraction, PULSE) can be disabled without breaking core. |
| I-10 | Architecture drives implementation | Implementation converges to CANONICAL_ARCHITECTURE; it never silently redefines it. |
| I-11 | Implementation never silently redefines architecture | No code change may alter a subsystem's canonical home, responsibilities, or layer without a documented architecture update. |
| I-12 | Ontology is shared and upstream | Memory/Knowledge/Trust/Governance consume one ontology (§4); they do not each define reality. |
| I-13 | Canonical home is permanent unless re-canonicalized | A subsystem's layer/home changes only via an architecture update, not via repo movement. |
| I-14 | Forensic corpus is evidence, not authority | The forensic reconstruction informs; it does not authorize deletion, simplification, or redesign. |
| I-15 | Evidence over implementation | Disagreements are resolved through explicit evidence and a recorded architectural decision. Existing code is never self-justifying architectural authority. A violation of any invariant requires cited ID, evidence of necessity, explicit owner approval, recorded exception, and canonical doc update. |

---

## 3. Layer Definitions

The architecture is organized into layers. Lower numbers are foundational; higher numbers build upon them. A subsystem's canonical home is its permanent layer unless re-canonicalized.

| Layer | Name | Canonical role |
|-------|------|----------------|
| 0 | Identity | Self/agent identity and boundary |
| 0.5 | Ontology | Shared vocabulary and meaning (upstream of Memory/Knowledge/Trust/Governance) |
| 1 | Constitution | Governing invariants, allowed behavior |
| 2 | Reasoning | Inference, causal/hyperdim/metacognitive reasoning, consensus, recursive yield |
| 3 | Memory | All memory kinds, storage, compression, retrieval, consolidation, lifecycle |
| 4 | Knowledge | Knowledge structures, bubbles, knowledge bus, curation |
| 5 | Trust | Trust, evidence, provenance, proof, claim verification, immune checks |
| 6 | Execution | Lifecycle, procedures, sessions, transactions, runtime/CLI |
| 7 | Communication | LLM/external gateways, message routing |
| 8 | Governance | Audit, release gates, policy enforcement |
| 9 | Skills | Skill foundry, plugin SDK, bundled skills |
| 10 | Learning | Adaptation, consolidation-as-learning, continuous learning |
| 11 | External Interfaces | DSL/compiler, SDKs, bridges to external systems |

---

## 4. Ontology

CAPT lacks an explicit ontology layer historically. This section defines the canonical meaning of core terms. It is shared vocabulary across Memory, Knowledge, Trust, Governance, and Reasoning. It is **defined, not implemented** here.

| Term | Canonical definition |
|------|----------------------|
| entity | Any distinguishable thing CAPT can reference: agent, memory, claim, skill, module, external system. Has a stable identifier. |
| relationship | A typed, directed association between two entities (e.g. `supports`, `derives_from`, `contradicts`, `scoped_to`). |
| identity | The stable referent of an agent/self; the scope under which state is partitioned. Distinct from an entity's transient attributes. |
| claim | A proposition asserted by or about an entity, pending verification. Has a confidence and provenance. |
| evidence | A structured observation or artifact that supports or weakens a claim. Linked, not embedded. |
| provenance | The origin and derivation chain of any entity/claim/evidence — who/what produced it and from what. |
| confidence | A bounded numeric representation of belief in a claim, in [0,1]; never implies certainty at 1.0. |
| uncertainty | The explicit complement of confidence; the set of unresolved or contradictory supports. First-class. |
| truth | A claim's standing after evidence + provenance + verification; contextual, not absolute. |
| contradiction | Two claims whose co-acceptance violates a consistency rule; triggers resolution, not silent drop. |
| temporal ordering | The partial order of observations/events by time; monotonic-guarded to resist clock skew. |
| observation | A raw input from an external or internal source, pre-claim. |
| inference | A derived claim produced by Reasoning from observations/evidence; carries its derivation path. |
| procedure | A parameterized, replayable sequence of operations with defined inputs/outputs and failure semantics. |
| skill | A packaged, publishable capability (procedure + metadata + verification) managed by Skill Foundry. |
| memory | Any persisted cognitive state — episodic, semantic, procedural, autobiographical, holographic, or working. |

These definitions are consumed by L3 (Memory schemas), L4 (Knowledge structures), L5 (Trust/Proof), and L8 (Governance audit). No layer redefines them independently.

---

## 5. Memory Architecture (Layer 3 decomposition)

Memory is not one subsystem. It decomposes into conceptual components. This is architectural only — no runtime change.

| Component | Responsibility | Notes |
|-----------|---------------|-------|
| Identity Memory | Identity-scoped state partition | L0 + L3 boundary |
| Working Memory | Short-horizon active context | volatile/in-process |
| Episodic Memory | Time-ordered timeline (canonical: ECHO) | ring-buffer retention, time-travel |
| Semantic Memory | Concept index | `semantic_index_metadata` |
| Procedural Memory | Procedures + runs | `procedures*` tables |
| Autobiographical Memory | Narrative self over episodic/semantic/prospective | designed canonical interface |
| HMC Compression | Holographic (FFT/VSA) fixed-dim storage compression | lossy-by-design, documented fidelity |
| DREAM Consolidation | Offline replay+integration into long-term | L3 + L10 |
| Replay | Replay memories/sessions for recovery/consolidation | canonical API |
| Retrieval | Search/rank over memory | `Search` |
| Synchronization | Canonical capability to reconcile memory across instances | see §8 / CANONICAL_ARCHITECTURE L3.22 — abstraction only; transports reviewed |
| Consent | Local consent ledger for sensitive operations | privacy-reviewed |
| Retention | TTL / retention policies | `memory_retention_policies` |
| Migration | Forward-only schema migration | `SCHEMA_VERSION` |
| Provenance | Origin/derivation of memories | links to L5 |
| Evidence linkage | Memories link to supporting evidence | links to L5 |

---

## 6. Canonical Subsystem Registry

Single source of truth. (Full current-implementation detail in CANONICAL_OWNERSHIP_MATRIX.md; maturity in §7.)

| Canonical name | Aliases | Responsibilities | Layer | Dependencies | Current impl | Planned impl | Public status |
|---------------|---------|------------------|-------|--------------|--------------|--------------|--------------|
| Identity | L0 | identity lifecycle, scoping | 0 | L3, L5 | implicit (semantic.py) | explicit store | CAPT_core |
| Ontology | L0.5 | shared vocabulary | 0.5 | none | none | defined in CANON | CAPT_core |
| Constitution | L1 | invariants, checks | 1 | none | none | document + check hook | CAPT_core |
| Reasoning Core | L2 | inference routing | 2 | L3,L5,L7 | implicit | explicit | CAPT_core |
| CIG | causal | causal inference | 2 | L3,L5 | biocapt-ecosystem | adopt | CAPT_core |
| HDR | hyperdim | VSA reasoning | 2 | L3 | biocapt-ecosystem | adopt (numpy) | CAPT_core |
| META | metacog | self-monitoring | 2 | L5,L2 | biocapt-ecosystem | adopt | CAPT_core |
| CONSC | Φ | global workspace | 2 | all | biocapt-ecosystem | research pkg | research |
| QIPC | consensus | quantum-inspired | 2 | L5 | biocapt-ecosystem | research pkg | research |
| RYS Bridge | rys | recursive yield bridge | 2/11 | L6,L11 | biocapt-ecosystem | external/plugin | external |
| Cognitive Loop | loop | perceive-reason-act | 2 | L2,L6,L7 | biocapt-ecosystem | adopt | CAPT_core |
| MemoryEngine | mem | core store | 3 | L0,L5 | capt-solo engine.py | unchanged | CAPT_core |
| CSG | csg | state graph | 3 | L3 | capt-solo csg.py | unchanged | CAPT_core |
| Episodic (ECHO) | echo | timeline | 3 | L3,L3.18 | capt-solo sessions / biocapt echo | adopt ECHO, merge | CAPT_core |
| Semantic | semantic | concept index | 3 | L3 | capt-solo semantic.py | unchanged | CAPT_core |
| Procedural | procedural | procedures | 3 | L3,L6 | capt-solo procedures.py | unchanged | CAPT_core |
| Prospective | prospective | future memories | 3 | L3,L3.3 | capt-solo prospective.py | unchanged | CAPT_core |
| Autobiographical | auto | narrative self | 3 | L3.3,L3.4,L3.6,L0 | none | design | CAPT_core |
| HMC | holographic | VSA memory | 3 | L3,numpy | biocapt-ecosystem | canonicalize | CAPT_core |
| ENGRAM | engram | long-term encode | 3 | L3.8,L3.3,L10 | biocapt-ecosystem | merge | CAPT_core |
| DREAM | dream | consolidation | 3/10 | L3.3,L3.8,L3.9,L10 | biocapt-ecosystem | canonicalize | CAPT_core |
| Context Builder | context | context windows | 3 | L3,L3.2,L3.4 | capt-solo context.py | unchanged | CAPT_core |
| Search/Retrieval | search | retrieval | 3 | L3,L3.4 | capt-solo search.py | unchanged | CAPT_core |
| Deduplicate | dedupe | merge dupes | 3 | L3,L3.14 | capt-solo deduplicate.py | unchanged | CAPT_core |
| Normalize | normalize | normalize | 3 | none | capt-solo normalize.py | unchanged | CAPT_core |
| Memory Compression (AntiToken) | antitoken | token-reduction | 3 | L3 | capt-solo antitoken.py | unchanged | CAPT_core |
| Retrieval Feedback | feedback | adaptive retrieval | 3 | L3.12,L10 | capt-solo feedback.py | unchanged | CAPT_core |
| Replay | replay | replay | 3 | L3,L3.3 | skill/docs only | canonicalize API | CAPT_core |
| TTL/Retention | ttl | retention | 3 | L3,L3.3 | capt-solo engine/lifecycle | unchanged | CAPT_core |
| Temporal Ordering | temporal | time order | 3 | L3 | capt-solo models.py | unchanged | CAPT_core |
| Export/Import | export | portability | 3 | L3 | capt-solo engine.py | unchanged | CAPT_core |
| Migration | migration | schema migrate | 3 | L3,L8 | capt-solo engine.py | unchanged | CAPT_core |
| Synchronization | sync | reconcile instances | 3/11 | L3,L5,L11 | none | canonical capability (transports reviewed) | CAPT_core (abstraction) |
| Consent | consent | consent ledger | 3 | L0,L5 | none | design (local) | CAPT_core |
| Secrets Screening | secrets | secret screen | 3 | none | capt-solo secrets.py | unchanged | CAPT_core |
| Knowledge Bubbles | bubble | portable knowledge | 4 | L3.8,L3.3,L5,L8 | capt-solo bubble.py | +IMMU hook | CAPT_core |
| KHSB | khsb | knowledge bus | 4 | L3,L6 | capt-solo bus.py | unchanged | CAPT_core |
| Curator | curator | curation | 4 | L4.1,L5,L9 | capt-solo curator.py | unchanged | CAPT_core |
| Trust Engine | trust | trust scoring | 5 | L3,L5.2,L5.3 | capt-solo trust.py | unchanged | CAPT_core |
| Evidence Engine | evidence | evidence weighting | 5 | L3,L5.4 | capt-solo proof.py | unchanged | CAPT_core |
| Provenance | provenance | origin trace | 5 | L3,L5.2 | capt-solo models/proof | unchanged | CAPT_core |
| ClaimGuard | claimguard | claim verify | 5 | L5.1,L5.2,L5.5 | capt-solo claimguard.py | unchanged | CAPT_core |
| Proof Engine | proof | proof integrity | 5 | L5.2,L5.3,L8 | capt-solo proof.py | unchanged | CAPT_core |
| Proof Ledger | ledger | immutable ledger | 5 | L5.5,L8 | capt-solo proof+governance | merge explicit | CAPT_core |
| IMMU | immu | immune verify | 5 | L4.1,L5.1 | biocapt-ecosystem | adopt | CAPT_core |
| Lifecycle | lifecycle | orchestration | 6 | L3,L8 | capt-solo lifecycle.py | unchanged | CAPT_core |
| Session Store | session | sessions | 6 | L3.1 | capt-solo sessions.py | merge→ECHO | CAPT_core |
| Procedure Store | procedure | procedures | 6 | L3.1,L6.1 | capt-solo procedures.py | unchanged | CAPT_core |
| Manager | manager | dispatch | 6 | all | capt-solo manager.py | unchanged | CAPT_core |
| CTP | ctp | transaction journal | 6 | core,L8 | wheel only (not tree) | restore | CAPT_core |
| CLI | cli | command line | 6 | L6.1,L3,L5 | capt-solo capt_cli.py | unchanged | CAPT_core |
| Runtime SDK | api | public API | 6 | all | capt-solo api.py | unchanged | CAPT_core |
| PULSE | pulse | LLM gateway | 7/11 | L2,L11 | biocapt-ecosystem | optional plugin | optional plugin |
| Governance | governance | audit | 8 | L5,L6.5,L3.21 | capt-solo governance.py | +CTP | CAPT_core |
| Release Gates | gates | validation | 8 | all | capt-solo verify* | extend | CAPT_core |
| Skill Foundry | skillfoundry | skill lifecycle | 9 | L5,L4,L8 | capt-solo skill_foundry.py | +Radar | CAPT_core |
| Skill Radar | radar | skill discovery | 9 | L9.1 | biocapt-ecosystem | merge→Foundry | CAPT_core |
| Plugin SDK | plugin | extension API | 9 | L6.7,L11 | capt-solo plugin/ | unchanged | CAPT_core |
| Bundled Skills | skills | 8 skills | 9 | — | capt-solo skills/ | unchanged | CAPT_core |
| Learning/Adaptation | learning | adaptation | 10 | L3.16,L3.10 | biocapt-ecosystem | adopt | CAPT_core |
| Consolidation-as-Learning | — | DREAM learning | 10 | L3.8–L3.10 | partial | canonicalize | CAPT_core |
| Continuous Learning | contlearning | ongoing loop | 10 | L10.1,L3 | biocapt-ecosystem (orphan 792 LOC) | adopt (Layer 10 permanent) | CAPT_core |
| OUROBOROS | ouroboros | self-ref loop | 10 | L10 | biocapt-ecosystem | research pkg | research |
| CAPTLANG | captlang | DSL compiler | 11 | none | Biocapt-ecosystem-fullcaptlang | external pkg | external |
| RYS Bridge | rys | external bridge | 11 | L2.7 | biocapt-ecosystem | external/plugin | external |
| Hermes Plugin | hermes | bridge to Hermes | 11 | L9.3 | capt-solo plugin/ | unchanged | CAPT_core |
| FILT/FSR | filt/fsr | filter/regulator | 2 | L2 | biocapt-ecosystem (disabled) | research pkg | research |

---

## 7. Canonical Maturity

Maturity communicates implementation readiness **independently** from architectural importance. Architecture and maturity are separate concepts — a subsystem can be architecturally permanent yet immature.

| Level | Meaning |
|-------|---------|
| Production | Complete per issue completion standard; in public release; verified. |
| Beta | Implemented, tested, but not yet release-verified or API-stable. |
| Experimental | Implemented but unstable/limited; opt-in. |
| Prototype | Minimal working slice; interface may change. |
| Research | Exists in research/preview form; not in stable public release. |
| Concept | Defined in architecture; no implementation. |
| Planned | Architecturally decided; implementation scheduled. |
| Deprecated | Architecturally retiring; migration path exists. |

Per-subsystem maturity is recorded in CANONICAL_OWNERSHIP_MATRIX.md (Canonical Maturity column), justified by implementation evidence, not opinion.

---

## 8. Public Boundary

What determines where a subsystem ships. These are governing rules, not a component list.

- **CAPT_core** — subsystems required for the local-first cognitive runtime: Identity, Ontology, Constitution, Reasoning Core, all Layer 3 Memory components, Layer 4 Knowledge (Bubbles/KHSB/Curator), Layer 5 Trust (Trust/Evidence/Provenance/ClaimGuard/Proof/Proof Ledger/IMMU), Layer 6 Execution (Lifecycle/Session/Procedure/Manager/CTP/CLI/Runtime SDK), Layer 8 Governance, Layer 9 Skills (Foundry/Plugin/Bundled), Layer 10 Learning (core), Layer 11 Hermes Plugin. Determined by: required for core cognition + local-first + no unresolved [B]/[S] gate.
- **optional plugin** — capabilities that add function but are disabled by default and degrade independently (e.g. PULSE LLM gateway). Determined by: [S] network/LLM surface + owner approval; must be independently degradable (I-09).
- **external package** — separately published, not in core runtime (e.g. CAPTLANG compiler, RYS Bridge, HMC Rust accel). Determined by: build-tooling or optional-accel nature; no core dependency.
- **research package** — preview/experimental brain-lobe modules not in stable public release by default (CONSC, QIPC, NEDA, ALLO, FILT, FSR, OUROBOROS, +30 registry modules). Determined by: [B] public/private boundary owner decision; metaphorical/disabled status.
- **private** — explicitly withheld from public release. Determined by: owner [B] decision + licensing/security.

**Synchronization rule:** Synchronization is a *canonical capability* of Layer 3 (abstraction only). Its **transport implementations** — filesystem, LAN, removable media, peer-to-peer, cloud — are what are subject to [S] security review. The abstraction itself is not gated. Only transports crossing a network boundary trigger the security gate.

---

## 9. Compatibility Policy

- **Semantic versioning:** `MAJOR.MINOR.PATCH`. MAJOR = breaking public API or persisted-schema change without migration. MINOR = backward-compatible addition. PATCH = fix only.
- **Migration guarantees:** persisted schemas migrate forward only; every migration writes a backup and is reversible where technically feasible; `SCHEMA_VERSION` is authoritative.
- **Persistence guarantees:** local SQLite is the canonical store; exports are local JSON; no remote persistence without explicit consent.
- **API stability:** public APIs in `capt_solo.api` and documented `foundry`/`memory`/`khsb` surfaces are contract-stable within a MAJOR version.
- **Deprecation strategy:** deprecated subsystems retain a migration/compat layer for ≥1 MINOR; removal requires owner approval + architecture update (I-11).
- **Compatibility contracts:** v0.4.0/v0.4.1 public contracts preserved unless a migration + compat adapter are supplied (issue architecture-preservation rule).

---

## 10. Release Philosophy

A CAPT release is not "it compiles." A subsystem is complete only when all hold:

1. **Implementation** — real code, no placeholder/TODO/empty body/fake adapter/demo-only return.
2. **Documentation** — executable examples + architecture reference.
3. **Tests** — unit + integration + negative/security tests (no import-only assertions).
4. **Failure semantics** — explicit, bounded, documented.
5. **Migrations** — versioned, backed-up, reversible where feasible.
6. **Security review** — secret scan, SQL boundary audit, degraded-mode, privacy check.
7. **Examples** — runnable usage.
8. **Release verification** — passes `verify_runtime.py`, `doctor.sh`, build, dependency audit, secret scan, and existing release-security gates.

No subsystem ships to a public release without all eight. The forensic corpus's "done because registered" stance is explicitly rejected (I-14).

---

## Invariant enforcement

Any code change that would violate an invariant in §2 must:
1. cite the invariant ID,
2. obtain explicit owner approval,
3. record the exception in CANONICAL_ARCHITECTURE.md's conflict section,
4. update this document if the invariant itself changes.

This is how CAPT prevents silent architectural redefinition.
