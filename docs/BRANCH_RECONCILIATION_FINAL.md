# Branch Reconciliation Final

**Release branch:** `release/capt-standalone-final`  
**Release head:** `4005809f482ce81762ca5634615024683e4d6158`  
**Merge base with main:** `9d4fee12bc6147d7fe5da9e5025e8eb32911293a`  
**Generated:** 2026-08-07  

## Internal Branches

| Branch | Head | Merge Base | Release Ahead | Branch Ahead | Disposition |
|--------|------|------------|---------------|--------------|-------------|
| feat/capt-runtime-hermes-execution-driver | 6615646 | 6615646 | 49 | 0 | INCLUDED_IN_RELEASE |
| feat/capt-runtime-external-driver-conformance | 9efe965 | 5fb323d | 55 | 5 | SEMANTICALLY_SUPERSEDED |
| feat/capt-desktop-runtime-m1 | 6b643f8 | 6b643f8 | 39 | 0 | INCLUDED_IN_RELEASE |
| feat/capt-memory-trigger-integration | 52761c4 | 52761c4 | 33 | 0 | INCLUDED_IN_RELEASE |
| feature/capt-bootstrap-bridge | 76dd716 | abeff5c | 130 | 104 | CLOSE_AS_SUPERSEDED |
| feature/hermes-capt-core-runtime-skill | c1f0149 | abeff5c | 130 | 93 | REQUIRES_SEPARATE_PRODUCT |
| release/capt-v05-layer-reconciliation | c0f9340 | abeff5c | 130 | 86 | RETAIN_AS_HISTORICAL_EVIDENCE |
| integration/full-public-architecture | 973b4ab | 973b4ab | 115 | 0 | INCLUDED_IN_RELEASE |
| integration/capt-v05-final-audit | 466f0d2 | abeff5c | 130 | 85 | RETAIN_AS_HISTORICAL_EVIDENCE |
| integration/capt-v05-release-corrected | 2d64844 | abeff5c | 130 | 76 | RETAIN_AS_HISTORICAL_EVIDENCE |

## Open PR Recommendations

| PR | Disposition | Rationale |
|----|-------------|-----------|
| PR #31 | CLOSE_AS_SUPERSEDED | Included/superseded after parity check |
| PR #32 | CLOSE_AS_SUPERSEDED | Included/superseded after parity check |
| PR #28 | RETAIN_AS_HISTORICAL_EVIDENCE | Unique adversarial tests already covered in release test suite |
| PR #22 | RETAIN_AS_HISTORICAL_EVIDENCE | Historical proof |
| PR #20 | CLOSE_AS_SUPERSEDED | Obsolete bootstrap ownership path |
| PR #19 | REQUIRES_SEPARATE_PRODUCT | Separate Hermes compatibility skill |
| PR #33 | READY_FOR_MAIN_PR_REVIEW | This release; post-repair installed proof complete |

## External Repositories

| Repository | Disposition |
|------------|-------------|
| knowurknottty/capt-workspace-mcp | REQUIRES_SEPARATE_PRODUCT |
| knowurknottty/capt-core-debug | RETAIN_AS_HISTORICAL_EVIDENCE |
| knowurknottty/capt_core_engineering | RETAIN_AS_HISTORICAL_EVIDENCE |
| knowurknottty/biocapt-cli-a-preserved | RETAIN_AS_HISTORICAL_EVIDENCE |
