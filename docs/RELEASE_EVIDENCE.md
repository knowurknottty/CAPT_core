# Release and Integration Evidence

CAPT keeps evidence scoped to the claim it actually supports. Historical evidence is not rewritten into current proof, and ordinary test success does not become a security-control attestation.

Snapshot date: **2026-08-27**.

## Historical v0.5 evidence

`release_evidence/v0.5/` remains the proof set for the numbered `0.5.0` lineage. It is historical and intentionally immutable.

## PR #117 convergence evidence

PR #117 merged provider/native/UPG-001→019/MCP convergence into Core `main` at `4a654a74083cf341f8557983ce256949198a02e7`.

Its exact PR head `570babeef113943860c1268722200a48639e406d` has:

- M0-A Contract & Runtime Proof: **PASS**;
- Native macOS Swift: **PASS**;
- Release Security: **FAIL** — run `32440329043`.

That failed receipt remains historical truth even though later source closed the security evidence gaps.

A frozen convergence snapshot also recorded full Python, Swift, contract, sanitizer, MCP, and cross-surface acceptance evidence. Those counts/hashes remain bound to the source identities in the original reports and are not relabeled as current-head proof.

## Release-security closure evidence — 2026-08-23

Exact Core source `2199c036aa22af33fb3eb0700f63f820a35aa55a` reproduced the closure in hosted push CI:

- Release Security run `32617740908`: **PASS**;
- **21 PASS / 0 FAIL / 0 NOT_VERIFIED / 26 NOT_APPLICABLE**;
- `blockingControls=[]`;
- M0-A run `32617740848`: **PASS**;
- `capt-security-gate` artifact ID `9487471673`, ZIP SHA-256 `89f1cb0e6a7ee75e45367deca213538824f5a96fbc98753cfc521604bf221371`.

Therefore that exact SHA is release-security authorized for the evaluated Core profile. This is source/security authorization, not proof that final public artifacts were rebuilt, re-hashed, signed, notarized, or distributed.

## ToolBroker evidence — PR #126

The governed ToolBroker tranche was verified on exact PR head `b21ed6e7ff3996d48c756e342b278b69af0d666f` before squash merge.

Recorded exact-head evidence includes:

- Core full suite: **1,178 passed / 62 skipped / 12 deselected / 0 failed**;
- focused ToolBroker suite: **90 passed / 5 real-Docker-daemon skips / 0 failed**;
- contract drift PASS;
- TypeScript parity **24/24**;
- Swift **64 / 7 skipped / 0 failures** and `CAPTNativeMac` build PASS;
- hosted M0-A run `32691812178`: **PASS**;
- hosted Release Security run `32691812182`: **PASS**;
- security decision **21 PASS / 0 FAIL / 0 NOT_VERIFIED / 26 NOT_APPLICABLE**, no blockers;
- security artifact ID `9507521011`, ZIP SHA-256 `40a9cbbe29e305f054b51cf0113dae825a0ccf3a0a81a9e305f670f69f73a25a`.

The squash merge `bcfdff9d43b35b5b192cc998b68ce16cc73b9985` resolves to the same tree but is a different commit SHA. The PR-head security receipt is **not** relabeled as a merge-SHA receipt.

The PR also documented remaining installed-runtime release gaps at merge time, including controlled installation/identity/ledger-continuity proof and real Docker-daemon acceptance. Source verification does not erase those separate gates.

## Public-release design convergence — PR #128

PR #128 merged nine documentation files at `54ac314294fb456cb2d9089615996b31dfeca753`, preserving exact owner-approved design (#111) and implementation-plan (#116) blobs on current Core ancestry.

Evidence claim: the approved documents are present on current `main` without stale runtime ancestry.

Non-claim: Secure Intake/Quarantine, Projects, human-first results, composer palette, Search/Deep Research governance, and Cohort Council are not thereby implemented.

## Managed authored skills evidence — PR #129

PR #129 merged at `3aee7370bac880aed99ce3c9ecfaa6d9ff48101e` after verification on its feature head `e55037d92e89c5a960ecad908a1714c06c0aad0b`.

The PR records:

- focused managed/authored/runtime cluster: **32/32 passed**;
- whole Python suite: **1,195 passed / 61 skipped / 12 deselected / 0 failed**;
- contract drift / TypeScript parity clean on the feature range;
- Swift suite: **66 executed / 7 opt-in skipped / 0 failed**;
- installed wheel SHA-256 `1a3b271bd268d22b5b0cc91ca2d70dfe351497b699078ee2f7aa1fee82a41b65`;
- Ultimate-skills import/verify: **26 skills**, manifest `sha256:450df8de682478602d5382e1541a9c84a7e28babc1cf2c53aecba92554e1eb36`;
- installed-runtime live probe of contextual selection, post-approval tamper rejection without consuming approval, restored accepted execution, and exactly-once model-visible skill-marker injection.

Known bounded limitation: four imported skills exceeded the current 32,768-character inline contract and remained installed/integrity-verified but non-inlineable rather than truncated.

## Current-main M0-A observation at audit start

For `main` `3aee7370bac880aed99ce3c9ecfaa6d9ff48101e`, push run `32958741310` completed with:

- Python 3.12 conformance/full regression/build/install: **PASS**;
- contract binding drift/generation: **PASS**;
- TypeScript build + parity: **PASS**;
- Python 3.10: **FAIL during collection**, because the Docker-daemon availability probe timed out after five seconds while trying `docker --context desktop-linux info`.

That failure is evidence of a CI/test-harness/environment interaction, not proof that the ToolBroker implementation itself failed. It is still a real red hosted run and must not be omitted from current status. The failed job was retried during the 2026-08-27 documentation audit; the retry result is a separate hosted fact.

## Cross-surface authority acceptance

Recorded native macOS ↔ RuntimeService ↔ MCP acceptance proved shared authority, exact approval binding, one dispatch on exact use, idempotent replay, mismatched-use rejection, `awaiting_verification` preservation, and restart reconstruction on the bound snapshot.

This proves transport/authority/replay behavior for that test setup. It is not model-quality proof or a claim that every production provider/tool behaves identically.

## Artifact evidence boundary

Wheel, sdist, native-binary, security-artifact, and test counts bind to the exact source that produced them. A later merge or docs commit does not inherit those hashes.

A final public artifact set must be built and hashed from the exact source selected and authorized for release.

## Evidence rule

A source test suite, sanitizer run, controlled provider/tool test, installed artifact, real provider run, security-control evidence record, signed/notarized release, and release-authorized source commit are distinct evidence classes. Claim only what the matching evidence establishes.
