# TREASURE_CHEST — Recovered Intellectual Assets

Status: RECOVERED (knowledge archaeology pass, 2026-07-30)
Purpose: catalog every significant architectural idea developed during CAPT's
lifetime — whether shipped, deferred, or abandoned. Future contributors read this
BEFORE the code. This is an intellectual asset catalog, not a feature list.

Classification legend: Core / Supporting / Future / Research / Historical / Obsolete
Implementation: Shipped / Partial / Conceptual / Missing

---

## 1. Verified State Identity (VSI)
- Origin: `a0124c1` feat(verification): VSI subsystem. ADR-0006 evidence lineage.
- Purpose: attach verification to the verified STATE, not conversation age. Ends
  the "verification loop" (re-running identical tests wastes tokens).
- Current: SHIPPED (`capt_solo/verification/identity.py`).
- Value: foundational — makes verification reproducible and cacheable.
- Recommendation: Core. Keep.

## 2. Evidence Engine + Invalidation Model
- Origin: `15247b7` Evidence Engine core (Phases 1–4), `5e51203` VSI<->Evidence.
- Purpose: record evidence, invalidate on concrete events, proof-preserving reuse.
- Current: SHIPPED (`capt_solo/evidence/`). Distinct present/believed/inferred/
  attempted/changed/verified/valid/invalidated concepts (EVIDENCE_MODEL.md).
- Value: epistemic backbone. Prevents false "verified".
- Recommendation: Core. Keep.

## 3. Proof Engine (Foundry Proof)
- Origin: `capt_solo/foundry/proof.py`. Named "Proof Engine" in PROOF_ENGINE.md.
- Purpose: aggregate evidence against declared requirements; no verified claim
  without satisfied proof.
- Current: SHIPPED (partial — aggregation; ledger separate).
- Value: claim discipline.
- Recommendation: Core. Extend with explicit Proof Ledger (see #14).

## 4. ClaimGuard
- Origin: docs/CLAIMGUARD.md (v0.4 concept).
- Purpose: scan claims for trigger verbs; downgrade unsupported claims with
  scoped, degradation-aware language. Never report unverified as verified.
- Current: CONCEPTUAL (no module).
- Value: output-contract discipline; pairs with Proof Engine.
- Recommendation: Future (v0.5.1) — implement as thin wrapper over Proof Engine.

## 5. Knowledge Bubbles
- Origin: docs/KNOWLEDGE_BUBBLES.md (v0.4 concept). Referenced in registry L4.
- Purpose: portable, governed transfer of claims/procedures/skills/evidence/
  proof/trust/provenance/CTP receipts/AntiToken/CSG between instances. Quarantined
  import lifecycle. v2 manifest with hashes + redaction declaration.
- Current: CONCEPTUAL (CTP substrate shipped; bubble wrapper absent).
- Value: safe cross-instance knowledge portability.
- Recommendation: Future — high value for multi-instance deployments.

## 6. Governance Layer
- Origin: docs/GOVERNANCE.md (v0.4 concept).
- Purpose: wrap consequential actions in CTP transactions + GovernanceReceipt;
  named-actor audit trail; publish/deprecate/revoke/approve/install governed.
- Current: CONCEPTUAL (CTP journal shipped; Governance wrapper absent).
- Value: auditable mutation; trust boundary enforcement.
- Recommendation: Future — pairs with Knowledge Bubbles + ClaimGuard.

## 7. Anti-Token-Extraction (ATE)
- Origin: hardening/* branches (`973b4ab` integrate ATE). Two implementations:
  (a) `capt_solo/memory/antitoken.py` (SHIPPED, 273 LOC, deterministic token
  reduction preserving decision structure); (b) `capt_solo/components/
  anti_token_extraction.py` (CHERRY-PICK candidate from ATE branch, MCP-based).
- Purpose: reduce token surface for LLM contexts without losing decision-relevant
  structure; fidelity guards.
- Current: SHIPPED (memory/antitoken.py) + candidate (components/ version).
- Value: core privacy/provider-neutrality enabler.
- Recommendation: Core. Cherry-pick components/ version for MCP interoperability.

## 8. Cognitive State Graph (CSG)
- Origin: `capt_solo/memory/csg.py` (375 LOC). Referenced as "CSG fragments" in
  Knowledge Bubbles.
- Purpose: cognitive state graph — predict/path/centrality/history.
- Current: SHIPPED (complete, in memory/csg.py not capt_solo/csg/).
- Value: state reasoning; basis for future orchestration.
- Recommendation: Core. Keep. (Note: bioCAPT CSG tools are a separate, external
  subsystem — not the same as this in-tree CSG.)

## 9. ContextPack v1
- Origin: `cve-v0.2` branch, absorbed into baseline. docs/CONTEXTPACK_V1.md.
- Purpose: deterministic, integrity-checked context packaging.
- Current: SHIPPED (`capt_solo/contextpack/`).
- Value: reproducible context assembly.
- Recommendation: Core. Keep.

## 10. Invention Engine
- Origin: `3493ef2` feat(invention): structured invention reasoning on math+physics.
- Purpose: structured reasoning for novel math/physics synthesis (M4).
- Current: MISSING in baseline (commit on full-public-architecture lineage, not
  in integration baseline). Concept: invention reasoning as a verification domain.
- Value: research — extends Evidence Engine to generative reasoning.
- Recommendation: Research — recover from full-public-architecture branch if
  needed; otherwise roadmap.

## 11. Skill Foundry
- Origin: docs/SKILL_FOUNDRY.md, registry L9.
- Purpose: skill authoring/compilation pipeline.
- Current: CONCEPTUAL (plugin system shipped; foundry for skills absent).
- Value: skill ecosystem.
- Recommendation: Future.

## 12. Reasoning Core sub-lobes (CIG/HDR/META/CONSC/QIPC/RYS/NEDA)
- Origin: registry "missing"; forensic CANONICAL_MODULE_REGISTRY; biocapt-ecosystem.
- Purpose: causal inference, hyperdim reasoning, metacognition, consciousness Φ,
  quantum-inspired consensus, recursive yield, neural event-driven arch.
- Current: MISSING (research package per CAPT_CANON).
- Value: long-term cognitive architecture; metaphorical or PORT decisions pending.
- Recommendation: Research / Owner PORT-or-exclude (matrix line 128). Do NOT
  implement in v0.5.

## 13. CAPTLANG compiler
- Origin: registry "external package"; Biocapt-ecosystem-fullcaptlang.
- Purpose: CAPTLANG compiled architecture (83 unified + 22 primary modules).
- Current: EXTERNAL (not in capt-solo). Memory note: fullcaptlang is authoritative
  source for CAPTLANG modules, newer than .hermes copies.
- Value: separate build tooling.
- Recommendation: External package — not in core runtime.

## 14. Proof Ledger / IMMU
- Origin: registry L5 (Proof Ledger, IMMU).
- Purpose: explicit immutable ledger of proofs/receipts.
- Current: MISSING (CTP receipts exist but no dedicated ledger module).
- Value: tamper-evident proof history.
- Recommendation: Future — natural extension of CTP receipts.

## 15. OUROBOROS / Continuous Learning / Consolidation-as-Learning
- Origin: registry L10.
- Purpose: self-improving learning loops (biological consolidation analogue).
- Current: PARTIAL (`capt_solo/learning` exists, no dedicated test).
- Value: adaptive behavior.
- Recommendation: Future — add tests; mark internal.

## 16. PULSE LLM gateway
- Origin: registry "optional plugin".
- Purpose: optional LLM gateway (provider-neutral).
- Current: MISSING in baseline (optional plugin, degradable).
- Value: provider neutrality enabler.
- Recommendation: Optional plugin — owner [S] decision.

## 17. Release Validator (Option A)
- Origin: v0.5 incident response (2026-07-30). docs/release/CANDIDATE_FREEZE_PROTOCOL.md.
- Purpose: mathematically valid release identity (source commit + metadata commit;
  no self-SHA invariant).
- Current: SHIPPED (`capt_solo/release_validation.py`, frozen).
- Value: prevents release-identity loops; auditable provenance.
- Recommendation: Core. Frozen unless defect found.

## 18. Six-Pillar Public Architecture
- Origin: ADR-0008.
- Purpose: organize public surface as six pillars; decouple from internal layers.
- Current: SHIPPED (docs/PUBLIC_ARCHITECTURE.md, manifest).
- Value: stable public contract.
- Recommendation: Core. Keep.

## 19. Capability Registry
- Origin: `architecture/registry.yaml`, docs/CAPABILITY_REGISTRY.md.
- Purpose: canonical catalog of all capabilities with status/ownership/ADRs.
- Current: SHIPPED (partial — ~70 capabilities cataloged, many missing).
- Value: single source of truth for "what exists vs what's planned".
- Recommendation: Core. Keep as the intellectual map's backbone.

## 20. Degradation-Aware Language
- Origin: ClaimGuard concept + ATE fidelity guards.
- Purpose: report capabilities as scoped/degraded, never falsely "verified".
- Current: PARTIAL (ATE fidelity guards shipped; ClaimGuard wrapper conceptual).
- Value: honest failure semantics.
- Recommendation: Core principle. Implement ClaimGuard (#4) to complete.

---

## Summary
- Shipped & keep: VSI, Evidence Engine, Proof Engine, ATE (memory), CSG, ContextPack,
  Release Validator, Six-Pillar, Capability Registry, Degradation-Aware Language.
- Future (high value): ClaimGuard, Knowledge Bubbles, Governance, Proof Ledger,
  Skill Foundry, OUROBOROS.
- Research / owner decision: Reasoning Core sub-lobes, CAPTLANG, PULSE, Invention
  Engine recovery.
- Nothing discarded. Every concept has a home: shipped, deferred, or archived.
