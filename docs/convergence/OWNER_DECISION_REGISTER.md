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
- Evidence: SPACE_READINESS_REVIEW (genuinely absent; seams only; ~comparable
  to evidence subsystem size; MEDIUM-HIGH risk; migration must be backup-gated).
- Recommendation: (b) v0.5.1. Current public claims do not require Spaces.

## OD-2 — Is a provider-neutral runtime adapter (doc 15 Workstream E) in v0.5.0?
- Options:
  (a) v0.5.0 — implement adapter contract + two proven paths now.
  (b) v0.5.1 — keep architecture-level "no harness dependency" claim (evidenced
      today); add operational adapter proof later.
- Risk: (a) two-path proof needs Spaces (policy selection) → couples D+E;
  unprovable neutrality without Spaces; risk of second overlapping abstraction.
  (b) "model-agnostic" stays an architecture claim, not a shipped feature claim.
- Evidence: RUNTIME_ADAPTER_READINESS_REVIEW (zero hermes imports proven;
  research/adapter.py registry precedent; no model-runtime contract exists).
- Recommendation: (b) v0.5.1. The evidenced claim today is architecture-level
  and true; adapters become operational proof in v0.5.1 with Spaces.

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
OD-1 (b) · OD-2 (b) · OD-3 (a) · OD-4 (a) · OD-5 (fold into OD-4a) · OD-6 (a).
These yield a truthful, evidenced v0.5.0 (verification substrate + security
campaign + doc/claim truth + release evidence) with Spaces/adapters/mappings
as a clearly-scoped v0.5.1, and a single coherent release branch.
No implementation starts until OD-1, OD-2, OD-4 are ratified by the owner.
