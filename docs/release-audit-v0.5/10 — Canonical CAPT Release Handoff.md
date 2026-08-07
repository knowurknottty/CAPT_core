# CAPT Standalone Harness v0.5 — Canonical CAPT Release Handoff

Date: 2026-08-05
PRE_REPAIR_INSTALLED_CANDIDATE_SHA: b45c4b005c9171172d055697a55034006bb0f2fe
VERIFICATION_REPAIR_SHA: b79c4f05784d001268e3fef523755365b1f5888e
CURRENT_LOCAL_HEAD: b79c4f05784d001268e3fef523755365b1f5888e
BRANCH: release/capt-standalone-final
REPOSITORY: https://github.com/knowurknottty/CAPT_core.git
REMOTE_STATUS: LOCAL ONLY (release/capt-standalone-final not on origin)
WHEEL_SHA256: 348fe9da477e0323d9c9b294677a1e10de4f9245373a27300367a9e8bdf879b3 (built from b45c4b0)
EVIDENCE_ROOT: /tmp/capt-release-evidence-b45c4b005c9171172d055697a55034006bb0f2fe/
ATTRIBUTION: knowurknot

## Exact Repository State

- Repository: https://github.com/knowurknottty/CAPT_core.git
- Local clone: /Users/knowurknot/CAPT_core
- Worktree: /tmp/capt-final-integration
- Branch: release/capt-standalone-final
- HEAD: b79c4f05784d001268e3fef523755365b1f5888e
- Worktree status: CLEAN
- Remote: release/capt-standalone-final NOT pushed; 44 commits ahead of origin/main

## Build and Install

```zsh
cd /tmp/capt-final-integration
git checkout release/capt-standalone-final
git rev-parse HEAD            # b79c4f05784d001268e3fef523755365b1f5888e
git status --porcelain        # must be EMPTY

# Build wheel
python -m pip wheel . --no-deps -w /tmp/capt-release-wheel

# Fresh venv install
python -m venv /tmp/capt-release-venv
/tmp/capt-release-venv/bin/pip install --no-deps   /tmp/capt-release-wheel/capt_solo-0.5.0-py3-none-any.whl
/tmp/capt-release-venv/bin/python -c   "import capt_runtime, desktop; from capt_runtime.task_resolver import TaskResolver; print('ok')"
```

NOTE: The wheel built from b45c4b0 (sha256 348fe9da...) does NOT include the verification-contract repair. Rebuild from b79c4f0 after this handoff to produce the corrected wheel.

## Harness Launch

```zsh
mkdir -p /tmp/capt-release-state
cd /tmp && PYTHONPATH= /tmp/capt-release-venv/bin/capt harness start   --ledger /tmp/capt-release-state/ledger.db   --sock /tmp/capt-release-state/rt.sock   --token-file /tmp/capt-release-state/token
```
Expect: CAPT_RUNTIME_SERVICE_READY sock=... pid=...

## Health and Capabilities

```zsh
PYTHONPATH= /tmp/capt-release-venv/bin/capt --json harness health   --sock /tmp/capt-release-state/rt.sock --token-file /tmp/capt-release-state/token
PYTHONPATH= /tmp/capt-release-venv/bin/capt --json harness capabilities   --sock /tmp/capt-release-state/rt.sock --token-file /tmp/capt-release-state/token
```
Expect: HEALTHY; commandOperations includes run_fixed_openharness_inspection and run_approved_hermes_inspection.

## Fixed-Function Operation

```zsh
PYTHONPATH= /tmp/capt-release-venv/bin/capt --json harness command   run_fixed_openharness_inspection   --payload-json '{"targetRoot": "/tmp/capt-final-integration"}'   --idempotency-key fixed-task-1   --sock /tmp/capt-release-state/rt.sock --token-file /tmp/capt-release-state/token
```

## Checkpoint / Stop / Resume

```zsh
# Checkpoint
PYTHONPATH= /tmp/capt-release-venv/bin/capt --json harness command   checkpoint_runtime   --idempotency-key cp-1   --sock /tmp/capt-release-state/rt.sock --token-file /tmp/capt-release-state/token

# Stop
PYTHONPATH= /tmp/capt-release-venv/bin/capt --json harness command   shutdown   --idempotency-key stop-1   --sock /tmp/capt-release-state/rt.sock --token-file /tmp/capt-release-state/token

# Restart on same ledger
cd /tmp && PYTHONPATH= /tmp/capt-release-venv/bin/capt harness start   --ledger /tmp/capt-release-state/ledger.db   --sock /tmp/capt-release-state/rt.sock   --token-file /tmp/capt-release-state/token

# Resume
PYTHONPATH= /tmp/capt-release-venv/bin/capt --json harness command   resume_runtime   --idempotency-key resume-1   --sock /tmp/capt-release-state/rt.sock --token-file /tmp/capt-release-state/token
```
Expect: resume returns not_repeated (no re-execution).

## Model Operator Status

REAL Hermes driver proven through installed wheel (3 real model tasks, evidence-backed findings, ClaimGuard, checkpoint/restart/resume).
Installation: requires operator to have Hermes CLI installed and accessible.
General model-driven engineering: NOT yet proven (only bounded read-only inspection is proven).

## Evidence Paths

- Release evidence: /tmp/capt-release-evidence-b45c4b005c9171172d055697a55034006bb0f2fe/
- Verification-fix log: /tmp/capt-verify-verification-fix.log
- Vault audit package: /Users/knowurknot/Documents/Obsidian Vault/02 Knowledge Base/CAPT/Assessments & Reviews/CAPT Standalone Harness v0.5 — b79c4f0/

## Unresolved Items

1. Wheel NOT rebuilt from b79c4f0 (BLK-1)
2. Installed claim lifecycle NOT exercised with repaired verification contract (REQ-2)
3. Remote push NOT performed (REQ-1)
4. CAPT Solo/KHSB/CTP CLI reachability NOT reconciled (REQ-3)
5. Remote branch semantic comparison NOT performed (IMP-5)

## Recommended Next Action

1. Rebuild wheel from b79c4f0
2. Push release/capt-standalone-final to origin
3. Exercise installed claim lifecycle with repaired verification contract
4. Reconcile CAPT Solo/KHSB/CTP CLI reachability
5. Compare overlapping remote branches
6. Open PR and merge reconciled branch into main
