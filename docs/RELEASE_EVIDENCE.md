# Release and Integration Evidence

CAPT keeps evidence scoped to the claim it actually supports.

## Numbered v0.5 evidence

`release_evidence/v0.5/` remains the historical proof set for the numbered `0.5.0` package lineage. It includes release readiness, requirement/evidence mapping, test matrix, wheel identity, installed model-operator evidence, and public-claim audit material.

Do not rewrite those records to make them describe later `main` or open-PR behavior.

## Merged-main evidence

Later productization tests establish the normal CLI/TUI/operator/provider-configuration foundations on `main`. Those are source/test claims for merged code, not a retroactive v0.5 wheel claim.

## Active PR evidence

Each active stacked PR has its own focused/full-suite evidence boundary. In particular, PR #47 reports focused prompt/provider/TUI/operator tests but explicitly leaves installed-wheel/live-provider/restart acceptance outside that focused proof.

## Hermes local evidence — LOCAL-002

Dedicated branch:

`evidence/hermes-local-002-r6`

Pushed HEAD:

`5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`

Report:

`reports/local-evidence/HERMES_AGENT_TUI_WORKSPACE_TESTS_AND_STATE_MAP_8F97AE9_2026-08-17.md`

Reported environment:

- Node `v22.22.2`;
- npm `11.14.1` system path: engine-incompatible;
- npm `11.17.0` via `npx`: faithful workspace path.

Reported results:

- **98 passed / 0 failed / 0 skipped**;
- **174 passed / 0 failed / 2 skipped**;
- verdict **`HERMES_LOCAL_002_COMPLETE`**;
- no product blocker;
- no state-map blocker.

Bounded residual gaps:

- destructive external-provider/tool-kill rollback E2E not yet run/proven;
- two pytest skips;
- unrelated macOS case-insensitive contributor-email checkout collision.

Related supplied identities: `46e7162dfa2bfb28ced981881e5dded0e74f078e` and `8f97ae9aec729bcbbad17da462115e1ec1398421`. This summary intentionally does not invent semantic labels for those hashes that are not present in the retrieved report.

At the moment of this documentation update, the GitHub connector lagged the just-pushed remote ref even though the operator supplied `git ls-remote` output showing `5c8cbf5... refs/heads/evidence/hermes-local-002-r6`. The branch/report itself becomes authoritative as soon as normal GitHub retrieval propagates.

## What still requires separate proof

- live intended-provider execution from the exact integrated head;
- installed-runtime acceptance of that provider path;
- true process-boundary Model-A -> Model-B continuity;
- destructive rollback/reconciliation cases where external work may have escaped cancellation;
- security controls explicitly left BLOCKED by #49;
- durable Cohort restart/evidence semantics.

## Evidence rule

A successful test suite, source file, controlled HTTP server, installed wheel, live provider, restart test, and destructive failure-injection test are different evidence classes. Claim only what the matching evidence establishes.