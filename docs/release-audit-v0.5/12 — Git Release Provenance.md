# CAPT Standalone Harness v0.5 — Git Release Provenance

Date: 2026-08-05
REPOSITORY: https://github.com/knowurknottty/CAPT_core.git
BRANCH: release/capt-standalone-final
CURRENT_LOCAL_HEAD: b79c4f05784d001268e3fef523755365b1f5888e
REMOTE_STATUS: LOCAL ONLY — release/capt-standalone-final not pushed to origin

## Commit Chain (local, this release session)

All commits produced during the standalone harness final closure:

```
b79c4f0 fix(verification): conform to frozen VerificationResult contract
    Files: 7 changed (verification.py, driver_host.py, services.py, capt_runtime_service.py, 3 test files)
    Insertions: 130, Deletions: 18
    Purpose: Repair build_verification_result to conform to frozen VerificationResult schema
    Dependent on: b45c4b0

b45c4b0 fix(runtime): reject idempotency key reuse with conflicting payload
    Purpose: IdempotencyConflict fix for create_mission early-return
    Dependent on: 6737f2c

6737f2c fix(harness): use ClaimGuard allowlisted claim for model task
    Purpose: Use bounded allowlisted claim statement
    Dependent on: 6af19cd

6af19cd fix(client): decouple command recv timeout from connect timeout
    Purpose: Client timeout decoupling
    Dependent on: ac6d057

ac6d057 fix(harness): grant artifact.create in model operator lease
    Purpose: Capability lease grant for model operator
    Dependent on: 3aa1be5

3aa1be5 fix(harness): drop non-contract field from OperatorMissionIntent
    Purpose: Remove non-contract field
    Dependent on: cb8089d

cb8089d feat(harness): advertise governed Hermes model operator capability
    Purpose: Capabilities advertisement
    Dependent on: 554ff15

554ff15 feat(harness): expose governed Hermes model operator
    Purpose: Model operator exposure
    Dependent on: 7475dcf

7475dcf feat(runtime): resolve driver tasks from authoritative task references
    Purpose: TaskResolver implementation
    Dependent on: 6b72922
```

## Documentation and Evidence Commits

STATUS: NOT YET COMMITTED. The documentation/vault package and raw evidence files are being prepared for commit. The recommended commit sequence from paste_2 is:

1. docs(release): add standalone harness audit and release evidence
2. docs(obsidian): archive final release audit package

These commits will be created after validation is complete and the full diff has been reviewed.

## Branch Ancestry

- origin/main ends at an older state (Desktop M0 era)
- release/capt-standalone-final is 44 commits ahead of origin/main
- feat/capt-memory-trigger-integration is an ancestor of release/capt-standalone-final
- release/capt-standalone-final does NOT exist on origin

## Remote Status

- Push: NOT YET PERFORMED
- Remote SHA: NOT POPULATED
- CI/PR: NONE

## Exact Repository State at Release

- Local clone: /Users/knowurknot/CAPT_core
- Worktree: /tmp/capt-final-integration
- Branch: release/capt-standalone-final
- HEAD: b79c4f05784d001268e3fef523755365b1f5888e
- Worktree status: CLEAN (pending documentation commits)
- contracts/ unmodified from b45c4b0

## Push Plan (pending documentation completion)

```
git push origin release/capt-standalone-final
git ls-remote origin release/capt-standalone-final
# Record REMOTE_VERIFIED_SHA
```
