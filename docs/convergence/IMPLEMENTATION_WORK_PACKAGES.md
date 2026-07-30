# IMPLEMENTATION_WORK_PACKAGES — ordered, owner-gated

Generated: 2026-07-30. Taxonomy follows the mission's Package A–H, adjusted
for the findings of THIS pass (notably: the main↔integration divergence and
the obsolete backup-recovery plan). No package is executed until owner approves
the scope reconciliation (V0_5_SCOPE_RECONCILIATION §4) and the first package.

Dependency order: A → B → C → (D/E deferred per OD-1/OD-2) → F → G → H.

## Package A — Baseline Revalidation (no feature work)
- Objective: reproduce current candidate + evidence at frozen SHA.
- Files: none changed.
- Tests required: full suite (715), build, clean-install, release validate --final.
- Evidence: CROSS_REPOSITORY_SOURCE_OF_TRUTH §3 (already executed today).
- Status: DONE this pass. Remaining: prune 4 stale /tmp worktrees (ancestors of
  HEAD, no unique work) — housekeeping, low risk.
- Owner gate: none (already satisfied).

## Package B — Correct Stale Review Records
- Objective: fix internal contradictions found in this pass.
- Scope: (1) CURRENT_STATE.md / RELEASE_STATE.md say `candidate_sha: UNFROZEN`
  while tracked manifest says `3888f08` — align to design (tracked stays
  UNFROZEN; generated final manifest carries SHA). (2) Self-dirtying CHECKPOINT.md
  on `workspace status`/agent startup fails `clean_tree` under --final — make
  checkpoint regeneration opt-in / not write to tracked file during validation.
- Files: CURRENT_STATE.md, RELEASE_STATE.md, capt_solo/workspace.py
  (checkpoint write path), docs/release/CANDIDATE_IDENTITY_DESIGN_REVIEW.md.
- Tests: add test asserting tracked manifest UNFROZEN + generated final carries SHA;
  add test that `release validate --final` passes on a clean checkout without
  manual revert.
- Risk: LOW. Backward compat: doc-only + behavior change to validation hygiene.
- Owner gate: B1 (approve tracked-manifest UNFROZEN convention).

## Package C — Main↔Integration Convergence + Security Recovery
- Objective: bring ATE + secret scanning + security CI + whitepaper into the
  integration candidate; run the security campaign at the frozen SHA.
- Scope: merge 10 main-only files (BACKUP_RECOVERY_PLAN §2) into integration;
  resolve verify_runtime.py modify conflict; DROP already-present CTP/packaging/
  release-validator commits.
- Files: capt_solo/components/*, .gitleaks.toml, .github/workflows/release-security.yml,
  tests/test_v04_anti_token_extraction.py, docs/WHITEPAPER.md, docs/ANTI_TOKEN_EXTRACTION.md,
  docs/ARCHITECTURE_REVIEW_ATE_ADAPTER.md, docs/DESIGN.md (review).
- Architecture contract: none changed (additive).
- Tests: ATE suite (575 lines) must pass; full suite stays 715+; add bandit/
  semgrep/gitleaks/pip-audit to CI; prioritized manual scopes (doc 04).
- Security review: REQUIRED (this is the security campaign).
- Dependencies: Package B (clean tree) first.
- Rollback: branch reset to 716ecc9.
- Risk: MEDIUM (merge of 10 files; one modify conflict).
- Owner gate: OD-4 (merge direction: integration absorbs main's ATE/CI/whitepaper,
  then integration becomes the release branch — RECOMMENDED over merging v0.5
  into main piecemeal).

## Package D — Space Foundation  → DEFERRED to v0.5.1 (per OD-1)
- Blocked until owner ratifies OD-1. Design in SPACE_READINESS_REVIEW §6.
- Stop condition: if implementation would change existing stable API signatures
  (vs extend), owner direction required first.

## Package E — Runtime Adapter Foundation  → DEFERRED to v0.5.1 (per OD-2)
- Blocked until owner ratifies OD-2. Design in RUNTIME_ADAPTER_READINESS_REVIEW §5.
- Stop condition: implementation must not make Hermes mandatory (inbound plugin
  only). Two-path proof requires Spaces (policy selection) → E after D.

## Package F — Documentation Truth
- Objective: fix unsupported claims (PUBLIC_CLAIM_LEDGER §F) + terminology.
- Scope: add LICENSE (MIT, Copyright 2026 Inversion Labs) to integration;
  reconcile main __version__ (replace main with integration at release, or fix
  main); refresh whitepaper to v0.5.0 language (post OD-1/OD-2 — do NOT describe
  Spaces/adapters as present); fix terminology discipline docs.
- Files: LICENSE (new), README.md, docs/WHITEPAPER.md, docs/PUBLIC_ARCHITECTURE.md.
- Tests: packaging test asserts LICENSE shipped in wheel/sdist; version-consistency test.
- Risk: LOW.
- Owner gate: none beyond scope ratification.

## Package G — Trust and Release Evidence
- Objective: threat model, SECURITY.md, SBOM, doc 07 evidence files, sealed at SHA.
- Scope: docs/THREAT_MODEL.md, SECURITY.md (responsible disclosure), SBOM
  (pip freeze / syft), supply-chain statement, docs/release/RELEASE_VERIFICATION_V0.5.md,
  ARTIFACT_MANIFEST_V0.5.json, PACKAGE_CONTENTS_V0.5.json, CONFORMANCE_RESULTS_V0.5.json,
  docs/security/RELEASE_SECURITY_REPORT_V0.5.md + 3 JSONs.
- Standards mappings: SSDF/AI-RMF/OWASP as v0.5.0 support docs; ISO 27001/SOC 2
  as v0.5.1 (REQUIRES_ORGANIZATIONAL_CONTROL) — split per SECURITY_TRUST_READINESS §4.
- Tests: release validator must pass with all evidence files present.
- Risk: LOW-MEDIUM (evidence generation must be reproducible).
- Owner gate: none.

## Package H — Final Negative-Space Audit + Harsh Reviewer
- Objective: TODO/FIXME/.bak sweep, duplicate trees, stale versions, dead links,
  broken examples, hidden deps, unsupported claims; run doc 16 five-gate review.
- Scope: docs/REPOSITORY_COMPLETENESS_AUDIT.md, docs/FINAL_RELEASE_BLOCKERS.md
  (must say NONE only when resolved/accepted).
- Tests: add CI grep for UNFROZEN/0.4.1 in public docs post-freeze.
- Risk: LOW.
- Owner gate: none. Final gate before owner authorization.

## Recommended first safe package

**Package A is complete. The next safe, owner-approvable package is B
(stale-record correction) — pure hygiene, no feature work, LOW risk, unblocks
the clean-tree requirement for every later package.** Package C (convergence)
is the highest-value but requires OD-4 first. Do NOT start D/E until OD-1/OD-2
ratified.
