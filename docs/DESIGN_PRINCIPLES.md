# DESIGN_PRINCIPLES — CAPT Core Engineering Philosophy

Status: RECOVERED (knowledge archaeology pass, 2026-07-30)
Source of truth: `docs/CAPT_CANON.md`, `docs/adr/ADR-*.md`, `docs/PUBLIC_API_STABILITY.md`
Scope: philosophy, not implementation. These principles govern code; code does not
redefine them (ADR-0001).

## 1. Architecture governs implementation
- ADR-0001. When code and architecture conflict, the code changes. Exceptions
  require explicit owner approval recorded against a named invariant.
- Recovered origin: stated in CAPT_CANON as the first constitutional clause.
- Evolution: from a v0.1 aspiration to a hard ADR after the v0.5 SHA-loop
  incident proved what happens when process drifts from architecture.

## 2. Truth is earned, not asserted
- Claims are only as strong as the evidence and provenance behind them. The
  system records uncertainty rather than hiding it.
- Operationalized by: ClaimGuard (concept), Proof Engine (foundry.proof),
  Evidence Engine (capt_solo.evidence), VSI (capt_solo.verification).
- ADR-0006: Evidence over implementation — no capability is "verified" without a
  satisfied proof aggregate.

## 3. Local-first; optional network transports
- ADR-0005. No operation requires a network. Remote capabilities are opt-in and
  fail safe offline.
- CAPT_CANON I-01: Local-first by default.
- Evolution: the ATE component (components/anti_token_extraction) was designed to
  run as a local stdio child; later hardened to use the real upstream MCP without
  leaving the local boundary.

## 4. Biological terminology is a design language, not decoration
- ADR-0003: Memory remains biologically inspired. Hippocampus/holographic/
  consolidation analogues are either algorithmically faithful or explicitly
  analogical.
- Registry modules (CSG, HMC, ENGRAM, DREAM) encode this mapping.

## 5. Ontology precedes knowledge, memory, trust, governance
- ADR-0002. The type system and schema (ontology) are the foundation; everything
  else is layered on top.
- Operationalized by: `architecture/*.schema.json`, `ontology` subsystem.

## 6. Canonical, reference, and current implementations are distinct
- ADR-0004. The canonical architecture (CAPT_CANON) is the spec. A reference
  implementation may demonstrate it. The current code is whatever shipped.
- This principle directly prevented the SHA-loop incident from silently
  redefining the release identity: the manifest names the SOURCE commit, not the
  build artifact.

## 7. Owner release decisions for the public boundary
- ADR-0007. The public API surface and release gates are owner-controlled. No
  automated process expands the public boundary.
- Directly informed the v0.5 freeze incident response: HY3 was constrained to
  preserve-and-diagnose, not decide.

## 8. Six-pillar public architecture
- ADR-0008. The public surface is organized as six pillars; internal layers
  (CAPT_CANON Layers 3–11) are not required to map 1:1 to packages.

## 9. Canonical evidence ownership
- ADR-0009. Evidence has a single owning authority per scope; provenance is
  explicit. No silent reassignment.

## 10. Public API stability tiers
- ADR-0010. stable / experimental / internal / deprecated / private.
- Operationalized by: `docs/PUBLIC_API_STABILITY.md`, `PUBLIC_API_MANIFEST_V0.5.json`.

## 11. Public verification record terminology
- ADR-0011. Verification records use consistent, non-misleading terminology
  (present/believed/inferred/attempted/changed/verified/valid/invalidated).
- Operationalized by: `docs/EVIDENCE_MODEL.md` distinct-concepts table.

## 12. Future record convergence without v0.5 migration
- ADR-0012. Future record formats converge by negotiation, not by forcing a v0.5
  migration. Backward-compatible extension only.

## Cross-cutting principles (from CAPT_CANON)
- Cognition is modular and inspectable (every function = subsystem with failure
  boundaries).
- The agent belongs to the user (privacy-preserving, degradable-by-default).
- Provenance over confidence.
- Deterministic validation (release gates fail closed).
- Explicit trust (no implicit global trust).
- Reproducibility (VSI state-bound verification).
- Provider neutrality (no hardcoded LLM provider).
- Composability (plugins, skills, bubbles).
- Failure semantics (degradation-aware language, never false "verified").

## Where these principles first appeared
- CAPT_CANON (Phase 2, `a2f0630`) — the constitution.
- ADRs 0001–0012 — the durable decision record.
- PUBLIC_API_STABILITY.md — the stability contract.
- The v0.5 SHA-loop incident (2026-07-30) — empirically reinforced #1, #6, #7.
