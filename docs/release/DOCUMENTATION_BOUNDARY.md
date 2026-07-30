# DOCUMENTATION_BOUNDARY — Where Each Recovered Document Belongs

Generated: 2026-07-30
Classification: Public / Internal / Engineering Reference / Historical.
Conservative: a doc is Public only if it describes shipped, user-facing behavior.

## Public (include in public repository docs/)
- `docs/ARCHITECTURE.md` — entry point; describes shipped layers + status. PUBLIC.
- `docs/PUBLIC_ARCHITECTURE.md` — six-pillar public model. PUBLIC.
- `docs/PUBLIC_API_STABILITY.md` — stability tiers contract. PUBLIC.
- `docs/API.md`, `docs/CLI.md` — user-facing surface. PUBLIC.
- `docs/SECURITY.md` — user-facing security posture. PUBLIC.
- `docs/EXTENDING.md`, `docs/PLUGIN_GUIDE.md`, `docs/SKILL_GUIDE.md` — contributor
  onboarding. PUBLIC.
- `docs/ROADMAP.md` — public roadmap (v0.1+). PUBLIC.

## Internal (contributors, not part of public user docs)
- `docs/DESIGN_PRINCIPLES.md` — ADR philosophy; useful for contributors. INTERNAL.
- `docs/TRUST_MODEL.md` — internal trust/provenance design. INTERNAL (contains
  concept-vs-implemented nuance not for end users).
- `docs/LIFECYCLE.md` — internal lifecycle design. INTERNAL.
- `docs/CAPT_CANON.md` — constitution; referenced by code, not user-facing. INTERNAL.
- `docs/CANONICAL_ARCHITECTURE.md`, `CANONICAL_OWNERSHIP_MATRIX.md` — ownership. INTERNAL.
- `docs/CAPABILITY_REGISTRY.md` — registry explainer. INTERNAL.
- `docs/EVIDENCE_MODEL.md`, `docs/VSI_MODEL.md`, `docs/PROOF_ENGINE.md` — design
  companions to shipped code. INTERNAL (engineering reference).
- `docs/GOVERNANCE.md`, `docs/CLAIMGUARD.md`, `docs/KNOWLEDGE_BUBBLES.md` — these
  describe IMPLEMENTED foundry/ modules; should be updated to say "implemented"
  and moved to INTERNAL (they are accurate design docs, just mislabeled conceptual).

## Engineering Reference (maintainer documentation)
- `docs/release/BRANCH_CENSUS.md` — branch decisions. ENGINEERING.
- `docs/release/ARCHITECTURE_INVENTORY.md` — subsystem scores. ENGINEERING.
- `docs/release/RELEASE_INTEGRATION_PLAN.md` — merge plan. ENGINEERING.
- `docs/release/RELEASE_BACKLOG.md` — deferred items. ENGINEERING.
- `docs/release/BATCH1_CHERRYPICK_IMPACT.md` — cherry-pick analysis. ENGINEERING.
- `docs/release/ARCHAEOLOGY_REVIEW.md` — this review's findings. ENGINEERING.
- `docs/release/IMPLEMENTATION_GAP_MATRIX.md` — gap matrix. ENGINEERING.
- `docs/release/PUBLIC_RELEASE_GAP_REPORT.md` — release gap. ENGINEERING.
- `docs/release/CANDIDATE_FREEZE_PROTOCOL.md` — release identity. ENGINEERING.
- `architecture/registry.yaml`, `architecture/*.schema.json`, `validate_registry.py`
  — machine-readable catalog. ENGINEERING.

## Historical (preserve for future archaeology, not release docs)
- `docs/release/HY3_RELEASE_FREEZE_INCIDENT.md` — incident record. HISTORICAL.
- `docs/release/CANDIDATE_IDENTITY_DESIGN_REVIEW.md` — design options considered. HISTORICAL.
- `docs/ROADMAP_FROM_RESEARCH.md` — research-to-roadmap mapping. HISTORICAL
  (becomes INTERNAL once roadmap is adopted).
- `docs/TREASURE_CHEST.md`, `CONCEPT_EVOLUTION.md`, `ARCHITECTURAL_PATTERNS.md` —
  archaeology outputs. HISTORICAL (they are the recovered intellectual map; keep
  for future contributors but mark as archaeology artifact, not live docs).
- `docs/CAPT_CORE_V0.5_ARCHITECTURE_EVOLUTION_REVIEW.md`, `FULL_ARCHITECTURE_
  IMPLEMENTATION_MATRIX.md` — census records. HISTORICAL.
- `~/captstreasurechest/` — forensic recovery archive. HISTORICAL (external).

## Recommended consolidation (after evidence, owner approval)
1. Merge `TRUST_MODEL.md` + `GOVERNANCE.md` + `CLAIMGUARD.md` + `KNOWLEDGE_BUBBLES.md`
   into one INTERNAL "Trust & Governance" doc that states IMPLEMENTED status.
2. Move `TREASURE_CHEST.md` / `CONCEPT_EVOLUTION.md` to a `docs/archive/` or
   `docs/archaeology/` folder (HISTORICAL) so they're not mistaken for live docs.
3. Correct `ARCHITECTURE.md` CONCEPTUAL list (remove ClaimGuard/Governance/Bubble/
   SkillFoundry/ProofEngine — they're implemented).
4. Keep `ARCHAEOLOGY_REVIEW.md` + `IMPLEMENTATION_GAP_MATRIX.md` as the authoritative
   correction record until the archaeology docs are updated.

## Boundary principle
Public docs describe WHAT the user gets. Internal docs describe HOW it's built.
Engineering docs describe HOW WE DECIDED. Historical docs preserve WHAT WE LEARNED.
The archaeology docs blurred these; this boundary restores them.
