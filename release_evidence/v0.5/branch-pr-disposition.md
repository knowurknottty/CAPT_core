# Canonical Branch / PR Disposition (release/capt-standalone-final)

**Release head:** `548ab3ae311366a3a83d4ae50ac6f2bb7495dcd4`
**Base:** main

| Branch | PR | Head | Relation | Unique commits | Disposition |
|--------|----|------|----------|---------------|-------------|
| feat/capt-desktop-runtime-m1 | PR #31 | 55b367b | FULLY_INCLUDED (branch is ancestor of release) | 0 unique, released | CLOSE_AS_SUPERSEDED |
| feat/capt-memory-trigger-integration | PR #32 | 52761c4 | FULLY_INCLUDED (branch is ancestor of release) | 0 unique, released | CLOSE_AS_SUPERSEDED |
| feat/capt-runtime-m0a-contract-state-proof | PR #22 | 6665a6a | FULLY_INCLUDED (branch is ancestor of release) | 0 unique, released | RETAIN_AS_HISTORICAL_EVIDENCE |
| feat/capt-runtime-external-driver-conformance | PR #28 | 9efe965 | DIVERGED (5 commits not in release, not ancestor) | 5 unique (Gate-A OpenHarness conformance tests) | SEMANTICALLY_SUPERSEDED |
| feature/capt-bootstrap-bridge | PR #20 | 76dd716 | DIVERGED (104 commits not in release) | 104 unique | CLOSE_AS_SUPERSEDED |
| feature/hermes-capt-core-runtime-skill | PR #19 | c1f0149 | DIVERGED (93 commits not in release) | 93 unique | REQUIRES_SEPARATE_PRODUCT |
| release/capt-v05-layer-reconciliation | n/a (prior internal) | c0f9340 | HISTORICAL | 86 unique prior reconciliation | RETAIN_AS_HISTORICAL_EVIDENCE |
| integration/full-public-architecture | n/a | 973b4ab | FULLY_INCLUDED | 0 unique | INCLUDED_IN_RELEASE |
| integration/capt-v05-final-audit | n/a | 466f0d2 | HISTORICAL | 85 unique prior audit | RETAIN_AS_HISTORICAL_EVIDENCE |
| integration/capt-v05-release-corrected | n/a | 2d64844 | HISTORICAL | 76 unique prior corrections | RETAIN_AS_HISTORICAL_EVIDENCE |

## Open PR recommendations

- **PR #31**: CLOSE_AS_SUPERSEDED — Fully included in release (ancestor).
- **PR #32**: CLOSE_AS_SUPERSEDED — Fully included in release (ancestor).
- **PR #28**: SEMANTICALLY_SUPERSEDED — 5 unique Gate-A commits replaced by release OpenHarnessDriver; port adversarial tests if missing.
- **PR #22**: RETAIN_AS_HISTORICAL_EVIDENCE — Fully included; historical contract-state proof.
- **PR #20**: CLOSE_AS_SUPERSEDED — Bootstrap bridge path obsolete.
- **PR #19**: REQUIRES_SEPARATE_PRODUCT — Separate Hermes compatibility skill.
- **PR #33**: READY_FOR_MAIN_PR_REVIEW — This release.

## Count reconciliation

10 internal branches classified (previously the summary alternated between inconsistent totals).

Dispositions: 2 CLOSE_AS_SUPERSEDED (PR #31/#32 branches), 1 SEMANTICALLY_SUPERSEDED (#28), 1 INCLUDED_IN_RELEASE, 3 RETAIN_AS_HISTORICAL_EVIDENCE (#22 + 2 integration), 1 REQUIRES_SEPARATE_PRODUCT (#19), and the release branch itself.