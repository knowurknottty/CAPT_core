# CAPT Standalone Harness v0.5 — Residual Backlog

Date: 2026-08-05
CURRENT_LOCAL_HEAD: b79c4f05784d001268e3fef523755365b1f5888e
BRANCH: release/capt-standalone-final

## BLOCKER

| ID | Item | Current Evidence | Deficiency | Acceptance Test | Owner | Dependency |
|----|------|-------------------|------------|-----------------|-------|------------|
| BLK-1 | Wheel rebuild after verification-contract repair | Wheel (sha256 348fe9da...) built from b45c4b0; repair is at b79c4f0 | Installed wheel does not include the VerificationResult contract fix | Rebuild wheel from b79c4f0; shasum; fresh-venv install; import; run record_verification through installed capt harness with build_verification_result output requiring no crash | operator | b79c4f0 clean worktree |

## REQUIRED

| ID | Item | Current Evidence | Deficiency | Acceptance Test | Owner | Dependency |
|----|------|-------------------|------------|-----------------|-------|------------|
| REQ-1 | Remote push | release/capt-standalone-final not on origin; 44 local commits | Local-only status blocks any external verification | git push origin release/capt-standalone-final; ls-remote confirms SHA | operator | network access |
| REQ-2 | Installed end-to-end claim lifecycle after repair | Installed lifecycle proven at b45c4b0 (pre-repair) | Verification-contract repair (b79c4f0) not exercised through installed wheel | Rebuild wheel; install; capt harness command run_approved_hermes_inspection; verify EvidenceRecorded + ClaimVerified events committed with contract-conforming records | operator | BLK-1 |
| REQ-3 | CAPT Solo / KHSB / CTP CLI reachability reconciliation | Modules ship in wheel but CLI/operator exposure not independently proven | governance/exposure via capt harness commands not independently verified | Enumerate capt CLI subcommands; exercise memory store/restore, KHSB pub/sub, CTP journal begin/commit through installed CLI | operator | BLK-1 |

## IMPORTANT

| ID | Item | Current Evidence | Deficiency | Acceptance Test | Owner | Dependency |
|----|------|-------------------|------------|-----------------|-------|------------|
| IMP-1 | _view separation refactor | _view mechanism works but risks reintroducing contract failure if strip_view() is forgotten | Transitional design; any persistence path forgetting strip_view could violate additionalProperties=false | Replace _view dict key with explicit VerificationResult + VerificationView dataclasses; eliminate the risk entirely | developer | none |
| IMP-2 | Repository-wide lint baseline (Ruff) | 2,721 findings (inherited baseline) | No CI lint gate | CI gate with zero findings or explicit allowlist with review dates | developer | none |
| IMP-3 | Plugin version axis | v0.5 declares no plugin registry/axis | Version-axis gap | Define plugin axis; map existing runtime/plugin surfaces onto it | developer | none |
| IMP-4 | OpenAI-compatible packaged CAPT driver | LM Studio live during proof but not wrapped as a CAPT driver | Only HermesDriver is packaged | Implement generic OpenAI-compatible driver; test through installed capt harness command | developer | none |
| IMP-5 | Remote branch semantic comparison | Overlapping remote branches not compared against release | Possible conflicts or duplication | Compare origin/feat/capt-runtime-hermes-execution-driver, origin/feat/capt-desktop-runtime-m1, origin/feat/capt-runtime-external-driver-conformance against release branch | operator | REQ-1 |

## DEFER

| ID | Item | Notes |
|----|------|-------|
| DEF-1 | Multi-user / enterprise operator identity | v0.6 scope |
| DEF-2 | TaskResolver redispatch policy | v0.6 scope |
| DEF-3 | Verification policy expansion (dirty-but-expected trees) | v0.6 scope |
| DEF-4 | ClaimGuard statement registry | v0.6 scope |
| DEF-5 | ECP v0.6 | Explicitly out-of-scope for v0.5 |
| DEF-6 | Bytecode / encryption / dual-layer encryption | Deferred by current release scope, not prohibited |
| DEF-7 | Cross-model resume | Not identified in current evidence; deferred |
| DEF-8 | Hermes compression interception / CAPTMem extension (MemoryGovernor activation) | Module exists in wheel; plugin-hook activation path not exercised in installed proof |

## REMOVE

| ID | Item | Notes |
|----|------|-------|
| REM-1 | Quarantined invalid drafts | _quarantine/INVALIDATED_DRAFTS/ contains the audit-method-failure evidence; preserve as process evidence, do not cite as release truth |
