# Release and Integration Evidence

CAPT keeps evidence scoped to the claim it actually supports.

## Numbered v0.5 evidence

`release_evidence/v0.5/` remains the historical proof set for the numbered `0.5.0` package lineage. It includes release readiness, requirement/evidence mapping, test matrix, wheel identity, installed model-operator evidence, and public-claim audit material.

Do not rewrite those records to make them describe later `main` or open-PR behavior.

## Merged-main evidence

Later productization tests establish the normal CLI/TUI/operator/provider-configuration foundations on `main`. Those are source/test claims for merged code, not a retroactive v0.5 wheel claim.

## Active PR evidence

Each active stacked PR has its own evidence boundary. PR #47 now has clean exact-head **source/editable-runtime** verification at `4334657a919f74803e65d9b01aa5054d6d7b9a61`:

- approval-security regressions: 8 passed;
- focused prompt/provider/TUI/operator suite: 31 passed;
- Ouroboros lifecycle: 18 passed;
- `tests/capt_runtime`: 387 passed / 10 skipped / 12 deselected;
- full repository: 861 passed / 67 skipped / 12 deselected;
- contract drift and `git diff --check`: passed.

That proof does not convert the source tree into an installed-wheel, live-provider, process-boundary cross-model, destructive rollback, or release artifact proof.

## Hermes LOCAL-002 metadata — quarantined pending retrieval

The operator supplied branch `evidence/hermes-local-002-r6`, HEAD `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`, report `reports/local-evidence/HERMES_AGENT_TUI_WORKSPACE_TESTS_AND_STATE_MAP_8F97AE9_2026-08-17.md`, classification `HERMES_LOCAL_002_COMPLETE`, and reported 98/0/0 focused plus 174/0/2 broader results with Node/npm environment notes and a no-product/state-map-blocker statement.

Terra later verified that the branch, commit, and named report are absent from the current GitHub remote/API. These values are therefore **not independently usable evidence**. The prior explanation that GitHub retrieval was merely lagging is superseded by the later remote/API audit.

Historical v0.5 Hermes evidence remains authoritative for its own bounded release lineage. If LOCAL-002 is restored, its report must be retrieved and reviewed before any of its claims re-enter the release ledger. Even a restored LOCAL-002 record would remain adjacent Hermes workspace evidence rather than proof of PR #47 exact head, installed-wheel behavior, live-provider execution, destructive rollback, restart continuity, or release readiness.

## What still requires separate proof

- live intended-provider execution from the exact integrated head;
- installed-runtime acceptance of that provider path;
- true process-boundary Model-A -> Model-B continuity;
- destructive rollback/reconciliation cases where external work may have escaped cancellation;
- security controls explicitly left BLOCKED by #49;
- durable Cohort restart/evidence semantics.

## Evidence rule

A successful test suite, source file, controlled HTTP server, installed wheel, live provider, restart test, and destructive failure-injection test are different evidence classes. Claim only what the matching evidence establishes.