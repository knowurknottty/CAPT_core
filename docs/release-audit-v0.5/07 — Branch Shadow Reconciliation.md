# CAPT Standalone Harness v0.5 — Branch Shadow Reconciliation

Date: 2026-08-05
PRE_REPAIR_INSTALLED_CANDIDATE_SHA: b45c4b005c9171172d055697a55034006bb0f2fe
VERIFICATION_REPAIR_SHA: b79c4f05784d001268e3fef523755365b1f5888e
CURRENT_LOCAL_HEAD: b79c4f05784d001268e3fef523755365b1f5888e
BRANCH: release/capt-standalone-final
REPOSITORY: https://github.com/knowurknottty/CAPT_core.git
ATTRIBUTION: knowurknot

## Git State (verified via direct fetch from origin)

### Remote Fetch
Command: `git fetch --all --prune` (executed 2026-08-05 from /Users/knowurknot/CAPT_core)
Result: fetch succeeded; no errors.

### Remote Branch Inventory
Origin branches present (after fetch):
- origin/main
- origin/audit/independent-602dc5a
- origin/docs/capt-runtime-architecture-spec
- origin/docs/capt-runtime-m0-freeze
- origin/docs/capt-runtime-m0-integration
- origin/docs/post-m0b-governance-review
- origin/docs/post-m0b-review-integration
- origin/feat/capt-desktop-runtime-m1
- origin/feat/capt-memory-trigger-integration
- origin/feat/capt-runtime-external-driver-conformance
- origin/feat/capt-runtime-hermes-execution-driver
- origin/feat/capt-runtime-m0a-contract-state-proof
- origin/feat/capt-runtime-m0b-readonly-driver-proof-hy3
- origin/feature/capt-bootstrap-bridge
- origin/feature/governed-deployment-adapters
- origin/feature/hermes-capt-core-runtime-skill
- origin/feature/meta-foundry
- origin/fix/context-provenance-security-boundary
- origin/hardening/ate-clean-single-user
- origin/hardening/post-merge-release-gates

### release/capt-standalone-final on Remote
Command: `git ls-remote origin release/capt-standalone-final`
Result: EMPTY — branch does NOT exist on remote.

### Local vs Remote main
Command: `git rev-list --left-right --count origin/main...release/capt-standalone-final`
Result: 0  44 (origin/main is 0 ahead; release/capt-standalone-final is 44 ahead)

### Worktree Status
Command: `git status --porcelain`
Result: EMPTY (clean worktree at b79c4f0)

## Commit Chain (local, most recent first)

```
b79c4f0 fix(verification): conform to frozen VerificationResult contract
b45c4b0 fix(runtime): reject idempotency key reuse with conflicting payload
6737f2c fix(harness): use ClaimGuard allowlisted claim for model task
6af19cd fix(client): decouple command recv timeout from connect timeout
ac6d057 fix(harness): grant artifact.create in model operator lease
3aa1be5 fix(harness): drop non-contract field from OperatorMissionIntent
cb8089d feat(harness): advertise governed Hermes model operator capability
554ff15 feat(harness): expose governed Hermes model operator
7475dcf feat(runtime): resolve driver tasks from authoritative task references
6b72922 feat(harness): complete standalone lifecycle controls
7ea5b67 docs(release): record composition inventory
3fda864 feat(runtime): centralize operator composition
```

## Shadow Assessment

1. **release/capt-standalone-final is LOCAL ONLY.** The branch does not exist on origin. All 44 commits ahead of origin/main are local.

2. **origin/main ends at an older state.** The release branch is 44 commits ahead of origin/main. Origin/main has not received any of the standalone harness or model operator work.

3. **Ancestry confirmed.** feat/capt-memory-trigger-integration IS an ancestor of release/capt-standalone-final (verified via git merge-base --is-ancestor). The memory-trigger/ContextPack/32K ladder work is present in the release branch.

4. **No push attempted.** All commits from 3fda864 through b79c4f0 are local-only. No `git push` was executed.

5. **No remote PR.** No open PR for release/capt-standalone-final exists (branch not on remote).

## Relevant Remote Branch Analysis

| Remote Branch | Relationship | Notes |
|---------------|-------------|-------|
| origin/main | Base; 44 commits behind release branch | Standalone harness work not on main |
| origin/feat/capt-memory-trigger-integration | Ancestor of release branch | Memory trigger/ContextPack/32K ladder work included in release |
| origin/feat/capt-runtime-hermes-execution-driver | May overlap with release model-operator commits | Requires semantic comparison |
| origin/feat/capt-desktop-runtime-m1 | May overlap with Desktop M1 work | Requires semantic comparison |
| origin/feat/capt-runtime-external-driver-conformance | May overlap with driver conformance | Requires semantic comparison |

## Reconciliation Required Before Release Declaration

1. Push: `git push origin release/capt-standalone-final`
2. Verify remote SHA matches local: `git ls-remote origin release/capt-standalone-final`
3. Compare overlapping remote branches (hermes-execution-driver, desktop-runtime-m1, external-driver-conformance) for semantic conflicts
4. Open a PR or merge directly depending on governance preference
5. Record the REMOTE_VERIFIED_SHA in the audit index

Until push completes, all commits are LOCAL ONLY. Do not claim GitHub contains these commits.

## SHA Scoping

| Label | SHA | Scope |
|-------|-----|-------|
| PRE_REPAIR_INSTALLED_CANDIDATE_SHA | b45c4b005c9171172d055697a55034006bb0f2fe | The SHA from which the installed wheel was built and the terminal verdict was issued |
| VERIFICATION_REPAIR_SHA | b79c4f05784d001268e3fef523755365b1f5888e | The verification-contract repair commit; current HEAD |
| CURRENT_LOCAL_HEAD | b79c4f05784d001268e3fef523755365b1f5888e | Same as VERIFICATION_REPAIR_SHA |
| FINAL_RELEASE_CANDIDATE_SHA | NOT_POPULATED | Pending final validation and commit selection after push |
| REMOTE_VERIFIED_SHA | NOT_POPULATED | No push performed |
