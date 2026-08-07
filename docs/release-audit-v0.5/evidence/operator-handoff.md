# CAPT Standalone Harness v0.5 — Persistent Operator Handoff

SHA-bound to: b45c4b005c9171172d055697a55034006bb0f2fe
Date: 2026-08-05
Prepared by: knowurknot

## Release identity
- Repo worktree: /tmp/capt-final-integration
- Branch: release/capt-standalone-final
- HEAD: b45c4b005c9171172d055697a55034006bb0f2fe
- Wheel: /tmp/capt-release-evidence-b45c4b005c9171172d055697a55034006bb0f2fe/artifacts/capt_solo-0.5.0-py3-none-any.whl
  sha256 348fe9da477e0323d9c9b294677a1e10de4f9245373a27300367a9e8bdf879b3
- Full suite: 766 passed, 12 deselected in 19.83s (log in evidence dir)
- Evidence root: /tmp/capt-release-evidence-b45c4b005c9171172d055697a55034006bb0f2fe/

## Exact zsh commands to reproduce the installed proof

### 1. Build the wheel from the clean SHA
```
cd /tmp/capt-final-integration
git checkout release/capt-standalone-final
git rev-parse HEAD            # must be b45c4b005c9171172d055697a55034006bb0f2fe
git status --porcelain        # must be EMPTY
python -m pip wheel . --no-deps -w /tmp/capt-release-wheel
shasum -a 256 /tmp/capt-release-wheel/capt_solo-0.5.0-py3-none-any.whl
# must print 348fe9da477e0323d9c9b294677a1e10de4f9245373a27300367a9e8bdf879b3
```

### 2. Fresh external interpreter install
```
python -m venv /tmp/capt-release-venv
/tmp/capt-release-venv/bin/pip install --no-deps \
  /tmp/capt-release-wheel/capt_solo-0.5.0-py3-none-any.whl
/tmp/capt-release-venv/bin/python -c \
  "import capt_runtime, desktop; from capt_runtime.task_resolver import TaskResolver; print('ok')"
mkdir -p /tmp/capt-release-state
```

### 3. Start the harness (from OUTSIDE the repo; PYTHONPATH cleared)
```
cd /tmp && PYTHONPATH= /tmp/capt-release-venv/bin/capt harness start \
  --ledger /tmp/capt-release-state/ledger.db \
  --sock   /tmp/capt-release-state/rt.sock \
  --token-file /tmp/capt-release-state/token
```
Expect: CAPT_RUNTIME_SERVICE_READY sock=... pid=...

### 4. Health and capabilities
```
PYTHONPATH= /tmp/capt-release-venv/bin/capt --json harness health \
  --sock /tmp/capt-release-state/rt.sock --token-file /tmp/capt-release-state/token
PYTHONPATH= /tmp/capt-release-venv/bin/capt --json harness capabilities \
  --sock /tmp/capt-release-state/rt.sock --token-file /tmp/capt-release-state/token
```
Expect: HEALTHY; commandOperations includes run_approved_hermes_inspection.

### 5. Real model task (governed; objective becomes authoritative Task state)
```
PYTHONPATH= /tmp/capt-release-venv/bin/capt --json harness command \
  run_approved_hermes_inspection \
  --payload-json '{"objective": "Inspect the installed CAPT v0.5 candidate for public version declarations that disagree with product version 0.5.0. Return evidence-backed mismatches only. Do not modify files.", "targetRoot": "/tmp/capt-final-integration"}' \
  --idempotency-key model-task-1 \
  --sock /tmp/capt-release-state/rt.sock --token-file /tmp/capt-release-state/token
```
Expect: status accepted; receipt carries missionId/taskId/driverRunId/
claimId/verificationId/artifactPath/artifactDigest/observations. This
invokes a REAL Hermes process (~1-2 min). NOTE: targetRoot must be a
CLEAN worktree (git status --porcelain empty) or verification fails.

### 6. Idempotent replay (same key, no re-execution)
```
# re-run EXACTLY the same command as step 5
```
Expect: status idempotent, classification duplicate, same receipt,
ledger head unchanged.

### 7. Checkpoint / stop / restart / resume
```
PYTHONPATH= /tmp/capt-release-venv/bin/capt --json harness command checkpoint_runtime \
  --payload-json '{}' --idempotency-key cp-1 \
  --sock /tmp/capt-release-state/rt.sock --token-file /tmp/capt-release-state/token
PYTHONPATH= /tmp/capt-release-venv/bin/capt --json harness stop \
  --sock /tmp/capt-release-state/rt.sock --token-file /tmp/capt-release-state/token \
  --idempotency-key stop-1
# restart with the SAME ledger (step 3 command)
PYTHONPATH= /tmp/capt-release-venv/bin/capt --json harness command resume_runtime \
  --payload-json '{}' --idempotency-key resume-1 \
  --sock /tmp/capt-release-state/rt.sock --token-file /tmp/capt-release-state/token
```
Expect: checkpoint manifest with ledgerDigest + integrityDigest;
stop accepted (server exits 0); after restart health shows headSequence
matching the checkpoint with SAME ledgerChainDigest; resume returns
execution "not_repeated".

### 8. Adversarial authority matrix (optional re-run)
```
python /tmp/capt-release-evidence-<SHA>/installed/adversarial-battery.py
```
Expect: 7/7 forgery rejections (unauthorized/malformed) with head
unchanged; conflicting idempotency payload rejected
(class=idempotency); HEALTHY_AFTER_ADVERSARIAL.

### 9. Clean shutdown
```
PYTHONPATH= /tmp/capt-release-venv/bin/capt --json harness stop \
  --sock /tmp/capt-release-state/rt.sock --token-file /tmp/capt-release-state/token \
  --idempotency-key stop-final
```

## Governance notes for the operator
- Objective authority: the persisted Task aggregate (EventStore) is the
  single source of truth. The frozen wire contracts carry only
  missionId/taskId references; TaskResolver resolves inside CAPT.
- Driver inventory: UNKNOWN must equal zero. hermes and openharness are
  KNOWN; registry/interface modules are classified non-driver.
- No release verdict from dirty/uncommitted code or a wheel from a
  different SHA. Preserve the evidence dir; keep tokens [REDACTED] and
  isolated under the state dirs.
