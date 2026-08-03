# M0-B Acceptance Decision

Date: 2026-08-03
Decision authority: independent post-M0-B review (lead runtime engineer)

## Findings summary

### Blocking findings
**None.** The independent revalidation (M0B_INDEPENDENT_REVIEW.md) confirms:
- M0-B is proven: 51 targeted M0-B tests pass; 469 full-suite pass; 44 optional
  skips (anti-token-extraction absent).
- Driver classification is honest: locally-implemented CAPT reference driver
  inspired by OpenHarness, NOT an external integration.
- Authority boundary holds at interface and call-path level.
- Read-only proof reconfirmed (repo unchanged, staging-only artifact, traversal
  denied, leases validated, observations untrusted, replay guarded).
- No M0-C code, no RuntimeAggregate implementation.
- Generated-contract drift: clean. Ruff: clean. TS build: OK.

### Non-blocking findings / residual risks
1. **CI "Release Security" red** on both M0-B and the M0-A base branch — caused by
   an inaccessible private `anti-token-extraction` dependency, NOT by M0-B. The
   relevant conformance suites pass. Dispositioned in
   RELEASE_SECURITY_DEPENDENCY_DECISION.md (recommend Option 4+5; not executed
   here — out of M0-B scope, requires separate authorization).
2. **`ruff format --check`** reports 3 M0-B files would be reformatted. Lint
   (ruff check) is clean; this is a style-only item, not a defect. Optional
   cleanup before merge.
3. **mypy not installed** in this environment → no static type gate run. Runtime
   contract validation is the enforced type mechanism.
4. **Governance incident:** unauthorized skill mutation (verification-workflows)
   occurred post-stop. Contained (quarantined read-only, evidence preserved);
   baseline unrecoverable → owner decision required. Does not affect CAPT code or
   M0-B acceptance, but is recorded as an open governance item.
5. **Canonical branch name collision:** `feat/capt-runtime-m0b-readonly-driver-proof`
   is owned by a parallel local worktree (canonical instance); this PR uses
   the `-hy3` suffix to avoid disturbing it. Merge target is the proven M0-A
   branch, not `main`.

### Documentation accuracy
All architecture docs (ADRs 0120–0127, M0-A forensic doc, M0-B evidence logs)
reflect the implemented behavior. No documentation-ahead-of-implementation or
implementation-ahead-of-documentation gaps found in the M0-B scope.

## Decision

**M0_B_ACCEPTED_PENDING_MERGE**

Rationale: M0-B is independently proven; PR #23 has no blocking defects; the CI
failure is conclusively unrelated (pre-existing on base branch, environmental);
the unauthorized skill mutation is contained and does not affect CAPT; and
documentation is accurate. The only remaining step is an authorized merge of PR
#23 by the owner (the agent is not authorized to merge).

Note: this is a review decision, not a merge. The PR remains DRAFT pending owner
review and merge. RuntimeAggregate and M0-C remain explicitly out of scope.
