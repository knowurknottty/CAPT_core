# Release and Integration Evidence

CAPT keeps evidence scoped to the claim it actually supports. Historical evidence is not rewritten into current proof, and ordinary test success does not become a security-control attestation.

Snapshot date: **2026-09-15**. Source reviewed: `1e85bac5d17cde342a1ae55e6ee3da5fa681ff61`.

Current HEAD has **no inherited release authorization**. The historical receipts below remain bound to their original identities. This repository review establishes merged source and focused test coverage, not a current-HEAD hosted Release Security run or public artifact release.

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

Non-claim: those design documents alone did not implement Secure Intake/Quarantine, Projects, human-first results, composer palette, Search/Deep Research governance, or Cohort Council. Later implementation must be assessed separately; merged Model Council alpha is bounded below.

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

## Historical M0-A observation — 2026-08-27 audit start

For then-`main` `3aee7370bac880aed99ce3c9ecfaa6d9ff48101e`, push run `32958741310` completed with:

- Python 3.12 conformance/full regression/build/install: **PASS**;
- contract binding drift/generation: **PASS**;
- TypeScript build + parity: **PASS**;
- Python 3.10: **FAIL during collection**, because the Docker-daemon availability probe timed out after five seconds while trying `docker --context desktop-linux info`.

That failure is evidence of a CI/test-harness/environment interaction, not proof that the ToolBroker implementation itself failed. It is still a real red hosted run and must remain in this historical record; it is not the status of September HEAD. The failed job was retried during the 2026-08-27 documentation audit; the retry result is a separate hosted fact.

## September reconciliation: merged source and focused coverage

These are repository source/test facts on the reviewed HEAD ancestry. The test files identify bounded coverage, not newly executed tests, hosted run receipts, installed-runtime acceptance, or release-security authorization. No September hosted run IDs or test totals are asserted here.

### PR #146 convergence and operator control

PR #146 merged on August 28 at `cefc885e0b7f42acdc86c5d9e230d20677d85468`: CAPT-UPG-020–024 are merged source, not an active integration stack. Source includes the reciprocal-review harness (`benchmarks/reciprocal_review.py`), discovery symbol index (`capt_runtime/discovery/symbol_index.py`), structural-hash and chunk-stability probes, and cognitive-debt projection (`capt_ui/operator/cognitive_debt.py`). Corresponding `tests/test_reciprocal_review_benchmark.py`, `test_discovery_symbol_index.py`, `test_tree_sitter_hashing_probe.py`, `test_chunk_stability_probe.py`, and `test_cognitive_debt_projection.py` cover their bounded contracts. This does not establish empirical reciprocal-review benefit, context sufficiency, semantic equivalence, FastCDC/provider-cache gains, or absence-of-debt correctness.

PR #148 merged at `5709380a914467ea7c51c1b41e118b45ce6efb31`; semantic operator control subsequently merged at `42a6cd290a45a2154cb18f6c3d111057db2ec407`. `capt_runtime/prompt_proposals.py`, `desktop/operator_control.py`, and `desktop/m1_command_service.py` supply proposal and shared operator-control paths. `tests/capt_runtime/test_prompt_proposal_commands.py`, `test_operator_control.py`, and `test_operator_control_runtime.py` cover approval binding, configuration/session coordination, and stale-revision rejection. Operator-control persistence does not replace authoritative runtime state.

### PR #153 Model Council alpha

Merge `542f8206049b6bb2d1ffb2d4ec6dc43141c05800` contains `capt_runtime/council.py`, `aggregates/council_state.py`, governed admission/analysis commands, checkpoint/replay integration, and `capt_ui/operator/council_chamber.py`.

`tests/capt_runtime/test_council_alpha.py`, `test_council_claims.py`, `test_council_durability.py`, and `tests/capt_ui/test_council_chamber.py` cover topology, digest-bound launch interlocks, dissent/challenge analysis, idempotency, restart/replay, and read-only projection. The maximum 24,000 logical Vessels is structural expansion, not measured concurrent provider execution. Persisted analysis remains unverified; majority agreement is neither Verification nor ClaimGuard acceptance. This alpha is not proof of a live end-to-end Council provider scheduler or paid-provider scale acceptance.

### PR #155 hardening

Merge `5812a0cf2c7b58badf83262b78a57da47961f995` adds lifecycle authority gates, identity-refusal auditing, read projections, honest absent-context provenance, and explicit UNSHIPPED context-module labels. Source and focused tests are identified in [`SECURITY.md`](SECURITY.md#september-merged-authority-and-observability-boundaries). These close specific source gaps, not all hardening backlog items or exact-HEAD release-security controls.

### PR #156 SOMA M0

Merge `4f1c0a144f96ad001d998fe3b5d4ecbb4da217b4` incorporates the clean SOMA M0 contract closure, superseding the historical PR #154 branch lineage. `capt_runtime/soma/` provides canonical trajectory types, the explicit `ReducerResult` contract, deterministic event-budget reduction, and compression receipts binding policy, budget, input, retained, and removed content.

`tests/soma/test_contract_closure.py` covers local adapter/reducer/arena/reconstruction/benchmark composition, input validation, receipt sensitivity, duplicate-critical-event accounting, and an explicitly undefined preservation ratio for an empty critical set. The other `tests/soma/` files cover trajectory, corpus, reducer, and benchmark primitives. These are local contract tests, not live RuntimeService context integration, semantic reconstruction quality, external competition readiness, or measured model/token-cost benefit. Compression receipts are not CAPT Verification records.

### September 15 presentation and routing fixes

`d33a5e43cb63e79edb58ec180d4b860e066a33e9` separates renderable model answer text from execution-details JSON in the native client. `capt_ui/surfaces/desktop_swift/Tests/CAPTCoreDesktopTests/CAPTChatCoordinatorTests.swift` covers observation-summary extraction and receipt preservation; workspace/session tests cover propagation and persistence. This is source-level client coverage, not a newly run Swift suite or installed-app acceptance.

`1e85bac5d17cde342a1ae55e6ee3da5fa681ff61` expands actionable-prompt signals in `capt_runtime/prompt_compiler/router.py`; `tests/capt_runtime/test_prompt_compiler.py` adds a list-and-match research-request regression through AUTO's OMNI/META path using controlled transport. Routing is not evidence that current external research was performed or that an answer is verified.

## Cross-surface authority acceptance

Recorded native macOS ↔ RuntimeService ↔ MCP acceptance proved shared authority, exact approval binding, one dispatch on exact use, idempotent replay, mismatched-use rejection, `awaiting_verification` preservation, and restart reconstruction on the bound snapshot.

This proves transport/authority/replay behavior for that test setup. It is not model-quality proof or a claim that every production provider/tool behaves identically.

## Artifact evidence boundary

Wheel, sdist, native-binary, security-artifact, and test counts bind to the exact source that produced them. A later merge or docs commit does not inherit those hashes.

A final public artifact set must be built and hashed from the exact source selected and authorized for release.

## Evidence rule

A source test suite, sanitizer run, controlled provider/tool test, installed artifact, real provider run, security-control evidence record, signed/notarized release, and release-authorized source commit are distinct evidence classes. Claim only what the matching evidence establishes.
