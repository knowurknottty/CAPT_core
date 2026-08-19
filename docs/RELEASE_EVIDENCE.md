# Release and Integration Evidence

CAPT keeps evidence scoped to the claim it actually supports. Historical evidence is not rewritten into current proof, and ordinary test success does not become a security-control attestation.

## Historical v0.5 evidence

`release_evidence/v0.5/` remains the proof set for the numbered `0.5.0` lineage. It is historical and intentionally immutable.

## Terminal convergence evidence — 2026-08-19

Current integration authority is PR #117 with PR #118's provider/model coherence repair reconciled on top of its latest authored-skill-aware head.

Fresh local verification on the resulting candidate established:

- clean Python 3.14 environment, editable source resolved to the isolated convergence worktree;
- Core full suite: **1,055 passed / 57 skipped / 12 deselected / 0 failed**;
- generated-contract drift: **PASS** (`11 generated files match the schema source`);
- `git diff --check`: **PASS**;
- fatal Python lint subset (`E9/F63/F7/F82`): **PASS**;
- Swift normal: **64 tests / 7 deliberate opt-in skips / 0 failures**;
- Swift strict concurrency + warnings-as-errors: **PASS**;
- ThreadSanitizer: **64 / 7 skipped / 0 failures**, no sanitizer finding;
- MCP PR #2 full suite against that Core candidate: **PASS**;
- MCP repository Ruff: **PASS**.

The broad Core repository Ruff F/E9 sweep is not globally clean; legacy unused imports/locals/redefinitions remain outside the terminal fix slice. Do not cite the scoped/fatal lint success as a repo-wide Ruff pass.

## Cross-surface authority acceptance

A disposable RuntimeService/EventStore plus deterministic loopback OpenAI-compatible test provider reproduced `CROSS_SURFACE_PASS` across native Swift and MCP PR #2:

1. MCP created a concrete model approval.
2. Native Swift observed and denied it; MCP then observed authoritative `denied` and provider dispatch stayed zero.
3. Native Swift created a fresh approval.
4. MCP approved and executed that exact mission/task/DriverRun binding.
5. Provider dispatch occurred exactly once.
6. Exact replay returned idempotently without a second dispatch.
7. Mismatched reuse failed closed with `AUTHORITYVIOLATION`.
8. Native observed approval `consumed`, DriverRun completed, task `awaiting_verification`, and `verificationId=null`.
9. RuntimeService restarted on the same ledger and both surfaces reconstructed the same authority state and chain digest.

This proves transport, authority, binding, replay, and reconstruction behavior. It is not a model-quality benchmark or a claim that a loopback test provider equals a production external provider.

## Security evidence boundary

The Security Closure Cockpit is integrated and intentionally fail-closed. The prior terminal-candidate run reported `BLOCKED / releaseAuthorized=false` with applicable controls still `NOT_VERIFIED` rather than manufacturing PASS from general tests.

The final exact source/artifact head must rerun the cockpit and record its decision on PR #117. Until it returns authorized, the convergence candidate is **integration-verified but release-security blocked**.

## Artifact evidence boundary

Final wheel, sdist, and native-binary SHA-256 values are recorded only after the final convergence source/docs freeze. PR #117 is the authoritative terminal record for those exact identities.

## Evidence rule

A source test suite, sanitizer run, controlled provider protocol test, installed artifact, real provider run, security-control evidence record, and signed/notarized release are distinct evidence classes. Claim only what the matching evidence establishes.
