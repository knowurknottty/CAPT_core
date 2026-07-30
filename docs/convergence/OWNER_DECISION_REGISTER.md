# OWNER_DECISION_REGISTER — unresolved decisions

Generated: 2026-07-30. Each item: options, risk, evidence, recommendation.

## OD-1 — Are first-class Spaces (doc 15 Workstream D) in v0.5.0 or v0.5.1?
- Options:
  (a) v0.5.0 — implement Spaces now (large effort, schema/API risk, blocks
      release on D/E completion).
  (b) v0.5.1 — ship v0.5.0 as evidenced verification substrate; Spaces later.
- Risk: (a) delays truthful release, raises stability risk on memory/CTP/
  foundry; (b) public positioning cannot mention Spaces as present (already
  handled by claim ledger — no current claim asserts Spaces).
- Evidence: SPACE_TRACEABILITY_MATRIX (genuinely absent; seams only; ~comparable
  to evidence subsystem size; MEDIUM-HIGH risk; migration must be backup-gated).
- **STATUS: RATIFIED (2026-07-30) as (b) v0.5.1.** Owner decision: treat Spaces
  as an architectural consolidation plus four new primitives (identity,
  ownership, CTP scope, policy inheritance), NOT a missing v0.5 release
  capability.

## OD-2 — Is a provider-neutral runtime adapter (doc 15 Workstream E) in v0.5.0?
- Options:
  (a) v0.5.0 — implement adapter contract + two proven paths now.
  (b) v0.5.1 — keep architecture-level "no harness dependency" claim (evidenced
      today); add operational adapter proof later.
- Risk: (a) two-path proof needs Spaces (policy selection) → couples D+E;
  unprovable neutrality without Spaces; risk of second overlapping abstraction.
  (b) "model-agnostic" stays an architecture claim, not a shipped feature claim.
- Evidence: RUNTIME_CAPABILITY_READINESS_REVIEW (zero hermes imports proven;
  research/adapter.py registry precedent; no model-runtime contract exists).
- **STATUS: RATIFIED (2026-07-30) as (b) v0.5.1.** Owner-approved v0.5.0 claim
  wording: "CAPT is model-agnostic at the architecture level and does not require
  Hermes or another runtime provider to operate." Do NOT claim a general
  provider/model adapter framework ships in v0.5.0.

## OD-3 — Standards mappings scope for v0.5.0
- Options:
  (a) Ship SSDF + AI RMF + OWASP mappings in v0.5.0; ISO 27001 + SOC 2 in v0.5.1.
  (b) All mappings in v0.5.1.
- Risk: (a) reasonable support docs, no attestation claimed; (b) thinner v0.5.0
  trust story.
- Evidence: SECURITY_TRUST_READINESS §2 (ISO/SOC2 REQUIRE_ORGANIZATIONAL_CONTROL).
- Recommendation: (a). SSDF/AI-RMF/OWASP are achievable support docs; ISO/SOC2
  deferred (org control).

## OD-4 — Merge direction for main↔integration convergence (Package C)
- Options:
  (a) Integration absorbs main's ATE + gitleaks + release-security CI +
      whitepaper; integration becomes the release branch. (RECOMMENDED)
  (b) Merge v0.5 integration into public main piecemeal.
- Risk: (b) scatters 66 v0.5 commits across main history, risks losing the
  Option A identity lineage; harder to freeze. (a) keeps one coherent candidate;
  main is updated in one controlled PR at the end.
- Evidence: main has 29 commits (ATE/CI/whitepaper/docs-refresh) NOT in
  integration; integration has 66 commits (entire v0.5) NOT in main; they are
  disjoint supersets (CROSS_REPOSITORY_SOURCE_OF_TRUTH §2).
- Recommendation: (a). Integration is the richer, validator-clean candidate;
  bring main's 10 unique files in, then promote integration to main via one PR.

## OD-5 — Public main version reconciliation (PUBLIC_CLAIM_LEDGER C2)
- Options:
  (a) At release, replace public main entirely with the v0.5 integration tree
      (single source of truth).
  (b) Patch main's __init__/pyproject to 0.5.0 independently.
- Risk: (b) creates two divergent public histories; (a) is the clean end-state
  once OD-4(a) is chosen.
- Recommendation: fold into OD-4(a) — one promotion, no parallel patch.

## OD-6 — Package registry publication
- Options:
  (a) GitHub-only release (tag + wheel asset), no PyPI.
  (b) Publish to PyPI on owner authorization.
- Risk: (b) requires PyPI credentials + owner approval (per standing auth rules).
- Evidence: wheel builds + clean-installs today; publish is gated by doc 00/07
  owner authorization.
- Recommendation: defer to owner authorization step; default (a) until told.

## Summary of recommendations
- OD-1: **RATIFIED** → v0.5.1 (consolidation + 4 primitives).
- OD-2: **RATIFIED** → v0.5.1 (operational adapter contract; v0.5.0 keeps
  architecture-level neutrality claim only).
- OD-3: (a) — SSDF/AI-RMF/OWASP in v0.5.0; ISO 27001/SOC 2 in v0.5.1.
- OD-4: (a) — integration absorbs main, becomes release branch. **NOW THE
  ACTUAL RELEASE GATE** (per owner, post-ratification).
- OD-5: fold into OD-4a.
- OD-6: (a) — GitHub-only until owner authorization.

## Documentation caveat (ratified with OD-2)
- A16 wording fix: in `docs/WHITEPAPER.md` (currently on main only; recovered in
  Package C), change "semantic and vector search adapters" (L498) to
  "semantic and vector search adapter seam" (or equivalent). Enforce during
  Package F (Documentation Truth). Prevents presenting a reserved extension
  point as an operational adapter. Recorded in PUBLIC_CLAIM_LEDGER §D and
  IMPLEMENTATION_WORK_PACKAGES Package F.

## Execution order (owner-approved, 2026-07-30)
1. Ratify OD-1 and OD-2. ✅ DONE this turn.
2. Approve OD-4a: integration absorbs main.
3. Recover `verify_runtime.py` + verified security-hygiene delta (Package C).
4. Run full exact-SHA validation suite (Package A rerun at converged SHA).
5. Fix documentation truth items (Package F: LICENSE, version reconcile, A16
   seam wording, UNFROZEN contradiction).
6. Freeze the v0.5 candidate (doc 07 procedure).
7. Begin Spaces (Package D), then runtime adapters (Package E), on the
   converged lineage for v0.5.1.

No implementation starts until OD-4a is approved and the convergence branch is
created from the verified base `716ecc9`.
