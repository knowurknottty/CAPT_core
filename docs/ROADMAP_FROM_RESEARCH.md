# ROADMAP_FROM_RESEARCH — From Recovered Concepts to Roadmap

Status: RECOVERED (knowledge archaeology pass, 2026-07-30)
Purpose: convert the recovered intellectual assets (TREASURE_CHEST.md) into an
explicit roadmap. Distinguishes v0.5 (done), v0.5.1 (near-term), Future, Research,
and Owner-decision items. Nothing is deleted; every concept has a disposition.

## v0.5 (SHIPPED — baseline `be4b0da`)
- MemoryEngine, CSG, Semantic/Procedural/Prospective memory, Context/Search/
  Dedupe/Normalize/Trust/Secrets/AntiToken (memory/), Evidence Engine, VSI,
  CTP, KHSB, Foundry/Proof, CLI, Plugin, ContextPack v1, Release Validator (Option A),
  Six-Pillar public architecture, Capability Registry.

## v0.5.1 (recommended next, post-release)
1. **ClaimGuard** — implement as thin wrapper over Proof Engine (TREASURE #4).
   Completes degradation-aware language (P8). Low risk.
2. **Cherry-pick ATE components/** — MCP-based Anti-Token-Extraction + gitleaks +
   release-security CI (Batch 1, see BATCH1_CHERRYPICK_IMPACT.md). Security hardening.
3. **Proof Ledger / IMMU** — explicit immutable ledger extending CTP receipts
   (TREASURE #14). Medium risk.
4. **Ontology module test** — add test_ontology.py or mark internal (ARCHITECTURE_INVENTORY flag).
5. **Engines/Ontology doc pages** — KHSB, Foundry, CTP docs (RELEASE_INTEGRATION_PLAN Batch 2).

## Future (v0.6+)
- **Knowledge Bubbles** wrapper (TREASURE #5) — safe cross-instance portability.
- **Governance Layer** wrapper (TREASURE #6) — audited publish/deprecate/revoke.
- **Skill Foundry** (TREASURE #11) — skill authoring pipeline.
- **OUROBOROS / Continuous Learning** — add tests, wire consolidation loop (#15).
- **Synchronization** lifecycle — multi-instance (missing; bubbles are the
  portability primitive, not the sync protocol).

## Research (owner PORT-or-exclude)
- **Reasoning Core sub-lobes**: CIG, HDR, META, CONSC, QIPC, RYS Bridge, NEDA,
  Cognitive Loop, HMC, ENGRAM, DREAM, FILT, FSR, PLAST, ALLO (registry "missing").
  Decision: PORT to bioCAPT ecosystem or EXCLUDE as metaphorical. Owner-only.
- **Invention Engine** — recover from full-public-architecture branch if needed.
- **CAPTLANG compiler** — external package, not core runtime.
- **PULSE LLM gateway** — optional plugin, owner [S] decision.

## Missing pieces (referenced but incomplete) — disposition
| Piece | Status | Disposition |
|-------|--------|-------------|
| Governance mechanisms | conceptual | Future (#6) |
| Reasoning models (sub-lobes) | missing/research | Owner PORT-or-exclude |
| Validation flows | SHIPPED (validator) | keep |
| Provenance concepts | SHIPPED (evidence) | keep |
| Memory structures | SHIPPED (memory stack) | keep |
| Orchestration patterns | CSG shipped; full orchestration missing | Future |
| Trust boundaries | SHIPPED (local-first, secrets, ATE) | keep |
| Capability negotiation | Registry shipped; runtime negotiation missing | Future |
| Workflow semantics | CTP shipped; workflow DSL missing | Research |
| Knowledge structures | Knowledge Bubbles conceptual | Future (#5) |
| Evidence pipelines | SHIPPED (evidence engine) | keep |
| Execution models | Lifecycle/Session/Procedure shipped | keep |

## Explicitly deferred (not in v0.5 scope, per release discipline)
- Public Trust Center, Security Boundaries publication, Privacy/Compliance docs,
  Threat Model publication, website, launch. (From original v0.5 release brief.)
- All Reasoning Core sub-lobes until owner decides PORT-or-exclude.
- CAPTLANG compiler (external build tooling).

## Success criterion check
- Implementation map: ✅ (ARCHITECTURE.md, ARCHITECTURE_INVENTORY.md).
- Intellectual map: ✅ (TREASURE_CHEST.md, CONCEPT_EVOLUTION.md, this doc).
- No buried treasure: every recovered concept is shipped / deferred / archived.
- Provenance: each entry cites origin (commit/doc/ADR).
