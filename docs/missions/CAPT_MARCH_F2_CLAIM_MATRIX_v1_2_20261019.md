# CAPT Core F2 — Claim Matrix v1.2 (ISOLATED BRANCH CANDIDATE; NOT MERGED)

- Repair branch source pin: 5cbe0ffed3d5070da51de40acbd61feb6dd41611, on fix/black-swan-f2-verifier-reconciliation-20261019.
- Base origin/main before repairs: 2ce53288f565cd387a1d7629b41690f9872b2a4b.
- Most recently observed remote HEAD: 7e1182154a4086b74529b970d04bef3ece4f4442. This matrix is therefore NOT the main branch's current production certification.
- Older MiMo and DeepSeek read-only model review pin: 444d85862325db9c23dd435bc96098d703f95281.
- v1.1 matrix historical source pin: e28b66504c422946a66409d0de12e71f1646aae6.
- RuntimeService last review reconciliation snapshot: ledger integrity ok, head 28252. Executable-to-ledger build identity is NOT established.
- Original MARCHING-ORDERS-DRAFT.md was absent from uploaded workflow ZIP. Workflow and TASK_REGISTER.csv were available.
- G0 CONDITIONAL / OPEN; F2 CONDITIONAL / OPEN. No release readiness or primitive integration claim.

## Evidence-qualified claims — conservative carry-forward

Old matrix status labels are historical unless independently revalidated on this branch. CM02 and CM05 are specifically re-tested in the new patch. The broad suite is NOT fully green (one Docker-environment mismatch).

| ID | Claim | Source | Test or observation | Status | Scope limitation |
|---|---|---|---|---|---|
| CM01 | EventStore projection | RuntimeService snapshot | integrity ok at event head 28252, not a build pin | LIVE_PROJECTION | not deployed SHA / not replay audit |
| CM02 | ToolBroker effect admission | capt_runtime/tool_broker.py | test_tool_broker.py incl. F2 recovery identity regression | PATCH_REGRESSION_TESTED | not exactly once external effects |
| CM03 | Authority enforcement | capt_runtime/authority.py | test_authority.py;test_authority_gates_mission_driverrun.py | SOURCE_TESTED | hostile same UID excluded |
| CM04 | Approval binding | capt_runtime/aggregates/human_approval.py | test_human_approval_capability_binding.py;test_prompt_approval_security.py | SOURCE_TESTED | user presence unverified |
| CM05 | ClaimGuard procedural truth | capt_runtime/verification.py | test_claim.py; test_f2_failclosed_digest.py | PATCH_REGRESSION_TESTED | not content-verification proof |
| CM06 | Replay/runtime single owner | capt_runtime/replay.py | test_replay.py;test_runtime_replay_hardening.py | SOURCE_TESTED | no live-ledger full replay |
| CM07 | Model endpoint preflight | capt_runtime/provider_model_preflight.py | test_provider_model_preflight.py | SOURCE_TESTED | no billable live call |
| CM08 | Typed failure sanitization | capt_runtime/provider_error_types.py;capt_runtime/diagnostic_receipts.py | test_openrouter_typed_errors.py;test_diagnostic_receipts.py | SOURCE_TESTED | not all failure classes certified |
| CM09 | Memory authority ceilings | capt_runtime/memory/policy.py | test_memory_policy_authority_lineage.py | SOURCE_TESTED | not live migration proof |
| CM10 | Prepared mapping immutable | capt_runtime/prepared_execution.py | test_prepared_frozen_mapping.py | SOURCE_TESTED | bounded fixtures |
| CM11 | Keychain create-only behavior | capt_runtime/state_security.py | test_state_keychain_initialization.py | SOURCE_TESTED | not hostile OS proof |
| CM12 | Swift socket I/O deadline | capt_ui/surfaces/desktop_swift/Sources/CAPTCoreDesktop/CAPTRuntimeClient.swift | CAPTRuntimeClientTests.swift | SOURCE_SWIFT_TESTED | not signed installer |
| CM13 | Primitive cbit | capt_runtime/cbit.py | tests/test_cbit.py | UNIT_TESTED_ONLY | live integration unverified |
| CM14 | Primitive calibration | capt_runtime/calibration.py | tests/test_calibration.py | UNIT_TESTED_ONLY | live integration unverified |
| CM15 | Primitive loop_detector | capt_runtime/loop_detector.py | tests/test_loop_detector.py | UNIT_TESTED_ONLY | live integration unverified |
| CM16 | Primitive lattice | capt_runtime/lattice.py | tests/test_lattice.py | UNIT_TESTED_ONLY | live integration unverified |
| CM17 | Primitive approval_metrics | capt_runtime/approval_metrics.py | tests/test_approval_metrics.py | UNIT_TESTED_ONLY | live integration unverified |
| CM18 | Primitive gate_result | capt_runtime/gate_result.py | tests/test_gate_result.py | UNIT_TESTED_ONLY | live integration unverified |
| CM19 | Runtime build identity | live executable not attested against repair SHA | attestation pending | UNKNOWN | executable-to-ledger binding unverified |
| CM20 | Same UID hostile-model boundary | capt_runtime/authority.py | selected authority tests | UNRESOLVED | do not claim security vs same UID |

## Tracked change-impact inventory d250cb3..repair SHA

Source: git diff --name-status d250cb36abb34e78326537d5e540429ac906aeae 5cbe0ffed3d5070da51de40acbd61feb6dd41611. An inventory is not equivalent to comprehensive behavioral verification.

- M  LICENSE
- M  README.md
- M  capt_runtime/diagnostic_receipts.py
- M  capt_runtime/drivers/provider.py
- M  capt_runtime/memory/policy.py
- M  capt_runtime/prepared_execution.py
- A  capt_runtime/provider_error_types.py
- M  capt_runtime/provider_model_preflight.py
- M  capt_runtime/state_security.py
- M  capt_runtime/tool_broker.py
- M  capt_runtime/verification.py
- M  capt_ui/surfaces/desktop_swift/Sources/CAPTCoreDesktop/CAPTRuntimeClient.swift
- M  capt_ui/surfaces/desktop_swift/Tests/CAPTCoreDesktopTests/CAPTRuntimeClientTests.swift
- M  docs/TROUBLESHOOTING.md
- A  docs/missions/CAPT_OPENROUTER_ENDPOINT_READINESS_R2_20261019.md
- M  docs/workflows/CAPT_REVIEWER_VERIFIER_CONTRACT.md
- M  pyproject.toml
- M  scripts/capt_repo_audit_gate.py
- A  tests/capt_runtime/test_f2_failclosed_digest.py
- A  tests/capt_runtime/test_memory_policy_authority_lineage.py
- A  tests/capt_runtime/test_openrouter_typed_errors.py
- A  tests/capt_runtime/test_prepared_frozen_mapping.py
- M  tests/capt_runtime/test_provider_model_preflight.py
- M  tests/capt_runtime/test_release_security_assurance.py
- A  tests/capt_runtime/test_state_keychain_initialization.py
- M  tests/capt_runtime/test_tool_broker.py
- M  tests/test_capt_repo_audit_gate.py

## Adversarial tests and verification scope

- Read-only MiMo and DeepSeek F2/G0 reviews: both CONDITIONAL, source HEAD 444d8586, their model tasks await independent verification.
- Patch VER-1: on synthetic OSError, earlier tree digest silently skipped a file. A failing pre-fix test and passing post-fix test prove the fail-closed regression.
- Patch TB-1: in-process dispatch failure and restart reconciliation emitted different toolResultId for one logical operation. A failing pre-fix test and passing post-fix test now enforce the same result identity, with no adapter re-dispatch.
- Current main source baseline 2ce53288: 114 selected tests passed pre-fix.
- Preregistered RED: 2 failed and 1 passed; failures reproduced VER-1 and TB-1.
- Post-fix GREEN: 117 selected tests passed; a separate final run after lint cleanup also passed 117.
- Broader tests with RLIMIT_NOFILE=4096: 1,734 passed, 1 failed, 14 skipped and 13 deselected. Failure was a Docker profile diagnostic expectation when Docker CLI was unavailable. TypeScript cross-language contract test was deliberately deselected after missing build dependencies; do not claim full suite PASS.
- Historical 218 pass and Swift 8 pass were measured at prior pins. Neither constitutes new integrated source coverage.
- Six primitives remain UNIT_TESTED_ONLY and not validated as wired live.

## F2 closeout gates remaining

1. Independently review this repair SHA; the models reviewed earlier source.
2. Full authoritative EventStore ledger replay and live executable-to-ledger SHA attestation.
3. Correct environment-aware Docker diagnostic test and install/verify local TypeScript build deps if appropriate, then run integrated CI.
4. Review the concurrent upstream changes 2ce53288..7e118215 and re-pin before any merge.
5. Prove six-primitive runtime integration; retain same-UID threat-model caveat.
6. No automatic human verification acceptance, push, merge, deployment, or provider retry.

**Disposition:** TEST-PROVEN ISOLATED FIX; F2 gate remains open.
