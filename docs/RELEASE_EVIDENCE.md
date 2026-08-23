# Release and Integration Evidence

CAPT keeps evidence scoped to the claim it actually supports. Historical evidence is not rewritten into current proof, and ordinary test success does not become a security-control attestation.

## Historical v0.5 evidence

`release_evidence/v0.5/` remains the proof set for the numbered `0.5.0` lineage. It is historical and intentionally immutable.

## Merged convergence evidence — 2026-08-19→21

PR #117 is now merged into `main` at merge commit `4a654a74083cf341f8557983ce256949198a02e7`. The formerly stacked provider/native/UPG-001→019 lines were semantically reconciled there; stale implementation PRs were closed unmerged as superseded rather than mechanically merged one by one.

The exact merged PR head is `570babeef113943860c1268722200a48639e406d`. On that head, M0-A Contract & Runtime Proof and Native macOS Swift passed, while **Release Security failed** (workflow run `32440329043`). This means the integration is merged but not release-authorized.

### Frozen local runtime/product snapshot

Fresh local verification on the frozen runtime/product snapshot established:

- clean Python 3.14 environment, editable source resolved to the isolated convergence worktree;
- Core full suite: **1,055 passed / 57 skipped / 12 deselected / 0 failed**;
- generated-contract drift: **PASS** (`11 generated files match the schema source`);
- `git diff --check`: **PASS**;
- fatal Python lint subset (`E9/F63/F7/F82`): **PASS**;
- Swift normal: **64 tests / 7 deliberate opt-in skips / 0 failures**;
- Swift strict concurrency + warnings-as-errors: **PASS**;
- ThreadSanitizer: **64 / 7 skipped / 0 failures**, no sanitizer finding;
- MCP PR #2 full suite against that Core runtime snapshot: **259 passed / 0 failures**;
- MCP repository Ruff: **PASS**.

The broad Core repository Ruff F/E9 sweep is not globally clean; legacy unused imports/locals/redefinitions remain outside the terminal fix slice. Do not cite the scoped/fatal lint success as a repo-wide Ruff pass.

### Pre-merge/frozen GitHub CI evidence

After convergence, CI itself exposed and fixed two harness defects and one genuine presentation-lifecycle race:

1. M0-A had run the UI-inclusive full suite without installing the project dependency closure, producing false `textual` import failures. The workflow now installs the declared CAPT project dependencies before full regression.
2. the inherited workflow named `Release Security` did not execute the Security Closure Cockpit at all, allowing a green badge to disagree with CAPT's own fail-closed release authority. The workflow now generates exact-head evidence, evaluates the 47-control gate, uploads its evidence/result artifact, and fails closed when applicable controls remain unverified.
3. Python 3.10 exposed a Textual teardown race where a select-change callback could update `#status` after the status widget had been unmounted. `_set_status()` now ignores only that transient `NoMatches` presentation condition; runtime/provider/approval authority is unchanged.

Post-fix GitHub evidence:

- M0-A Python 3.10: **PASS** — conformance, full regression, wheel build/install, clean installed imports, package-content inspection;
- M0-A Python 3.12: **PASS** — same gates;
- contract regeneration + byte-reproducibility: **PASS**;
- TypeScript build + cross-language parity: **PASS**;
- Native macOS Swift workflow: **PASS**, including unit tests and `CAPTNativeMac` build;
- Release Security Python 3.10: **PASS**;
- Release Security Python 3.12: **PASS**;
- full-history gitleaks: **PASS**;
- dependency closure pip-audit: **PASS**;
- SecurityGate machinery tests: **11 passed**;
- final Security Closure Cockpit enforcement: **BLOCKED by design** because applicable release-control evidence remains incomplete.

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

The exact cross-surface acceptance report binds to the frozen runtime/product snapshot used for that test. Subsequent terminal-candidate changes are limited to CI workflow hardening, documentation reconciliation, and the Textual presentation teardown guard; they do not silently relabel the earlier acceptance report as a different source SHA.

## Security evidence boundary

The Security Closure Cockpit is integrated and intentionally fail-closed. The last detailed pre-merge gate projection recorded at exact head `33e24146094242d7a88612cea39267ef52a1d2e1` was:

- decision **BLOCKED**;
- `releaseAuthorized=false`;
- **2 PASS / 0 FAIL / 19 NOT_VERIFIED / 26 NOT_APPLICABLE**;
- PASS evidence currently includes `gitleaks:full-history` and `pip-audit:installed-runtime-closure`;
- the remaining 19 applicable controls are release-blocking until their required exact-head evidence is supplied.

The gate artifact is uploaded by the `Release Security` workflow for audit. `NOT_VERIFIED` is missing/incomplete evidence, not a discovered vulnerability and not permission to infer PASS from unrelated test suites.

The subsequent exact merged head `570babeef113943860c1268722200a48639e406d` produced a failing Release Security workflow; that historical result remains immutable evidence. The security-closure implementation now maps the full Python assurance suite into explicit per-control attestations, verifies a live provider-side OpenRouter key cap independently, and requires the Python spend-alert proof before `CAPT-SUP-07` can pass. Local projection over the 47-control catalog is **21 PASS / 0 FAIL / 0 NOT_VERIFIED / 26 NOT_APPLICABLE**.

That local projection is not itself release authorization. The exact source commit under consideration must reproduce PASS in hosted `Release Security`, after which release artifacts must be rebuilt and re-hashed from that authorized commit.

## Artifact evidence boundary

Wheel, sdist, and native-binary SHA-256 values recorded on PR #117 bind to the exact frozen runtime/product snapshot that produced them. Later workflow/documentation/TUI-lifecycle commits change the repository head, so those hashes must not be misrepresented as hashes of a different source commit.

A final public-release artifact set must be rebuilt and re-hashed from the exact source commit that is ultimately authorized for release.

## Evidence rule

A source test suite, sanitizer run, controlled provider protocol test, installed artifact, real provider run, security-control evidence record, signed/notarized release, and release-authorized source commit are distinct evidence classes. Claim only what the matching evidence establishes.
