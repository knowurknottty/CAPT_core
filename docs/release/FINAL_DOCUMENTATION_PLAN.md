# FINAL_DOCUMENTATION_PLAN — CAPT_core

Generated: 2026-07-30
Classifies every document/concept and proposes an ordered rewrite sequence.
Treasure Chest stays private; only selected, rewritten content may become public.

## Proposed document structure

### Public user documentation (docs/ user-facing)
- README.md (KEEP; accurate, says pre-release)
- docs/CLI.md, docs/API.md, docs/EXTENDING.md, docs/PLUGIN_GUIDE.md, docs/SKILL_GUIDE.md (KEEP)
- docs/tutorials/VERIFY_AI_WORK_IN_FIVE_MINUTES.md (KEEP; exists per doc 02)
- CHANGELOG.md (REWRITE: clarify v0.4.1 refs as historical; add v0.5 section)

### Public architecture/reference
- docs/PUBLIC_ARCHITECTURE.md (KEEP)
- docs/PUBLIC_API_STABILITY.md (KEEP)
- docs/CAPT_CANON.md (KEEP; constitution)
- architecture/registry.yaml + validate_registry.py (KEEP; authoritative)
- docs/release/PUBLIC_API_MANIFEST_V0.5.json (KEEP; freeze source of truth)

### Contributor documentation
- docs/DESIGN_PRINCIPLES.md, TRUST_MODEL.md, LIFECYCLE.md (KEEP; internal)
- docs/GOVERNANCE.md, CLAIMGUARD.md, KNOWLEDGE_BUBBLES.md, PROOF_ENGINE.md,
  EVIDENCE_MODEL.md, VSI_MODEL.md (UPDATE: state IMPLEMENTED in foundry/)
- docs/CAPABILITY_REGISTRY.md (KEEP)

### Maintainer / release engineering
- docs/release/BRANCH_CENSUS.md, ARCHITECTURE_INVENTORY.md, RELEASE_INTEGRATION_PLAN.md,
  RELEASE_BACKLOG.md, BATCH1_CHERRYPICK_IMPACT.md (KEEP; update stale claims)
- docs/release/ARCHAEOLOGY_REVIEW.md, IMPLEMENTATION_GAP_MATRIX.md,
  PUBLIC_RELEASE_GAP_REPORT.md (KEEP; superseded by FINAL_V0_5_GAP_REPORT)
- docs/release/THREE_REPOSITORY_RECONCILIATION.md, TREASURE_CHEST_REQUIREMENT_MATRIX.md,
  BACKUP_DELTA_REPORT.md, PUBLIC_DOC_TRUTH_AUDIT.md, CAPABILITY_SUPPORT_MATRIX.md,
  FINAL_V0_5_GAP_REPORT.md, FINAL_DOCUMENTATION_PLAN.md, OWNER_DECISION_REGISTER.md (NEW this review)
- docs/release/CANDIDATE_FREEZE_PROTOCOL.md, CANDIDATE_IDENTITY_DESIGN_REVIEW.md (KEEP)

### Security evidence (private until exact-SHA closure)
- docs/security/RELEASE_SECURITY_REPORT_V0.5.md + findings/coverage/manifest JSON (CREATE — BLOCKING B1)
- docs/release/RELEASE_VERIFICATION_V0.5.md, ARTIFACT_MANIFEST_V0.5.json,
  PACKAGE_CONTENTS_V0.5.json, CONFORMANCE_RESULTS_V0.5.json (CREATE — BLOCKING B2)

### Historical incident record
- docs/release/HY3_RELEASE_FREEZE_INCIDENT.md (KEEP; historical)
- ~/captstreasurechest/hy3_sha_loop_recovery/ (external; historical)

### Private operational runbook (Treasure Chest — NEVER public)
- captstreasurechest docs/00-17 + AGENTS.md + templates (KEEP PRIVATE)
- Do NOT copy internal security procedures, private evidence, or unfinished
  compliance claims into public repo.

### Research / archive
- docs/TREASURE_CHEST.md, CONCEPT_EVOLUTION.md, ARCHITECTURAL_PATTERNS.md (archaeology;
  move to docs/archive/ or docs/archaeology/ — HISTORICAL)
- docs/ROADMAP_FROM_RESEARCH.md (HISTORICAL)

## Ordered rewrite sequence (after owner approval)

1. **D1 fix** (doc-only, immediate): update CURRENT_STATE.md + RELEASE_STATE.md
   candidate_sha to 3888f08, status FROZEN. (No implementation.)
2. **D2 fix**: SECURITY.md add closure-pending statement.
3. **D4 fix**: add contributor note in GOVERNANCE.md/CLAIMGUARD.md that these are
   implemented in foundry/ (corrects archaeology mislabel).
4. **B2 files**: generate RELEASE_VERIFICATION, ARTIFACT_MANIFEST, PACKAGE_CONTENTS,
   CONFORMANCE_RESULTS at final frozen SHA (requires S2 re-run).
5. **B1**: execute manual security campaign (doc 04) or owner accepts exception;
   produce RELEASE_SECURITY_REPORT + findings/coverage/manifest.
6. **S1**: cherry-pick Batch 1 ATE (owner approves).
7. **S2**: re-run full suite + 6-profile clean-install at frozen SHA.
8. **OWNER_DECISION #1**: resolve Space/runtime-adapter/Trust-Center scope.
   If in-scope → implement (B3-B5). If deferred → mark POST_V0_5, update docs.
9. **D3**: CHANGELOG v0.4.1 clarification.
10. Final PUBLIC_DOC_TRUTH_AUDIT re-run; set status to READY or owner-exception.

## Principle
Public docs describe WHAT the user gets (six pillars). Internal docs describe HOW.
Engineering docs describe DECISIONS. Historical docs preserve LEARNING. Treasure
Chest stays OPERATIONAL/PRIvATE. No internal security procedure copied to public.
