# OWNER_DECISION_REGISTER — CAPT Core v0.5

Generated: 2026-07-30
Every unresolved question requiring owner approval. Options include evidence,
risk, and recommendation. No decision made by agent.

## OWNER_DECISION #1 — Final v0.5 scope: six-pillar vs Treasure Chest full contract
- **Question:** Is v0.5 the six-pillar public architecture (ADR-0008) ONLY, or does
  it also include the Treasure Chest finish-line playbook's Spaces (doc 15-D),
  provider-neutral runtime adapters (doc 15-E), and Trust Center (doc 15-F)?
- **Evidence:**
  - Treasure Chest doc 15 explicitly lists D/E/F as v0.5 workstreams and says
    "NOT READY — BLOCKERS REMAIN" (docs 00/02).
  - Owner's live session instructions said "do not begin implementation / roadmap
    execution" and treated six-pillar as the release surface; Option A declared done.
  - The six-pillar surface is implementation-complete and tests pass.
- **Options:**
  - (A) Narrow v0.5 to six-pillar + Option A. Spaces/adapters/Trust Center = POST_V0_5.
    → B3/B4/B5 become non-blocking. Release can proceed after B1/B2 + doc fixes.
  - (B) Full Treasure Chest contract. Spaces/adapters/Trust Center are in v0.5.
    → B3/B4/B5 are blocking; significant implementation remains.
- **Risk:** (A) under-delivers vs Treasure Chest but matches owner's live "no
  implementation" instruction. (B) requires substantial new implementation,
  contradicting "do not begin implementation" in this session.
- **Recommendation:** (A) — consistent with owner's live directives and the
  "feature-complete per public architecture" finding. Record Treasure Chest's
  broader contract as the authoritative v0.5 DEFINITION but defer D/E/F with
  explicit owner sign-off. Update docs to state v0.5 = six-pillar + Option A.

## OWNER_DECISION #2 — Security closure exception (B1)
- **Question:** The Codex scan failed (doc 11). Should v0.5 proceed with a manual
  security campaign (doc 04) as the closure mechanism, or accept a documented
  owner exception with the 6 already-adjudicated Codex candidates?
- **Evidence:** 6 candidates closed with RED-GREEN tests in 3888f08; full campaign
  (Bandit/Semgrep/gitleaks/adversarial) not run. Doc 03 allows owner exception for
  open Critical/High with containment + expiry.
- **Options:**
  - (A) Run manual campaign (doc 04) before release. Stronger evidence.
  - (B) Accept exception: 6 closed + Batch 1 gitleaks/CI; document limitation.
- **Risk:** (A) delays release, needs tooling. (B) weaker security evidence but
  honest if documented.
- **Recommendation:** (B) for v0.5.0 with Batch 1 gitleaks + a documented limitation
  statement; schedule full campaign as v0.5.1 hardening.

## OWNER_DECISION #3 — Batch 1 ATE cherry-pick (S1)
- **Question:** Approve cherry-pick of ATE components/ + gitleaks + release-security
  CI from origin hardening/* branches?
- **Evidence:** BATCH1_CHERRYPICK_IMPACT.md — minimal 4-commit series, no release-
  semantic changes, no public API changes, LOW/MEDIUM conflict risk. components/
  absent in baseline.
- **Options:**
  - (A) Approve Batch 1 (4 commits, ordered).
  - (B) Defer to post-release.
- **Risk:** (A) adds MCP ATE + secret scanning to published artifact (security win).
  (B) published wheel lacks gitleaks CI.
- **Recommendation:** (A) — security hardening, no scope expansion, consistent with
  "narrow correction" discipline.

## OWNER_DECISION #4 — Public repository visibility (doc 17)
- **Question:** Which repos stay public? Treasure Chest doc 17 says CAPT_core public;
  others private by default. Visibility changes need GitHub settings (connector
  limitation noted in doc 17).
- **Evidence:** doc 17 triage table; captstreasurechest + backup are already private.
- **Options:**
  - (A) Keep CAPT_core public; all others private (per doc 17).
  - (B) Review capts-arena / anti-token-extraction for later public release.
- **Risk:** Public exposure of unfinished work contradicts doc 17's 2-minute test.
- **Recommendation:** (A). No agent may claim lockdown until visibility changed via
  GitHub settings (doc 17 connector limitation).

## OWNER_DECISION #5 — Archaeology doc corrections
- **Question:** Apply the 7 corrections from ARCHAEOLOGY_REVIEW.md (ClaimGuard/
  Governance/Bubble/SkillFoundry/ProofEngine/ProofLedger/InventionEngine status)?
- **Evidence:** ARCHAEOLOGY_REVIEW.md; verified via import smoke + registry.yaml.
- **Options:**
  - (A) Agent applies corrections to TREASURE_CHEST.md / CONCEPT_EVOLUTION.md now.
  - (B) Owner reviews first; agent applies on approval.
- **Risk:** Stale archaeology docs could mislead future contributors.
- **Recommendation:** (A) after this review (doc-only, no implementation). Already
  recorded in ARCHAEOLOGY_REVIEW.md; safe to apply.

## Summary of recommended owner actions
1. Confirm OD#1 = (A) narrow scope.
2. Confirm OD#2 = (B) exception + Batch 1.
3. Approve OD#3 Batch 1 cherry-pick.
4. Confirm OD#4 = (A) visibility.
5. Approve OD#5 archaeology doc corrections.
