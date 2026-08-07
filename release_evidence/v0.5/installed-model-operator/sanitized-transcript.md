# Sanitized Model-Operator Command Transcript

**Purpose:** preserve the exact commands and receipts from the installed model-operator lifecycle proof, with credentials/tokens redacted.

Environment: macOS, installed wheel (from SHA 4005809), external venv at `/tmp/capt-test-venv8`, `PYTHONPATH` unset.

---

## Step 0 — Start authenticated service

```
# token redacted in this transcript
PYTHONPATH= /tmp/capt-test-venv8/bin/python3 -m desktop.capt_runtime_service \
  --ledger /tmp/capt-test-ledger/ledger.db \
  --sock /tmp/capt-test.sock \
  --token-file /tmp/capt-test.token --seed
```

Result: `CAPT_RUNTIME_SERVICE_READY sock=/tmp/capt-test.sock ledger=/tmp/capt-test-ledger/ledger.db`

Health check:

```
PYTHONPATH= /tmp/capt-test-venv8/bin/capt harness health --sock /tmp/capt-test.sock --token-file /tmp/capt-test.token
→ status: HEALTHY, headSequence: 13, integrity: ok
```

---

## Step 1 — First governed model-operator action

```
PYTHONPATH= /tmp/capt-test-venv8/bin/capt harness command run_approved_hermes_inspection \
  --payload-json '<objective: inspect CAPT v0.5 version declarations>' \
  --idempotency-key idem-version-audit-7 \
  --sock /tmp/capt-test.sock --token-file /tmp/capt-test.token
```

Result: `status: accepted, classification: accepted`
- missionId: m-model-version-audit-7
- driverRunId: dr-model-version-audit-7
- claimId: cl-model-version-audit-7
- verificationId: vr-sha256:44c5f6eef
- artifactDigest: sha256:13ab095c591f23fb94c0f0187cdbf3bf73cd4f30afafe563b85d69eb4c5eab21
- ledgerHead: 29
- Hermes observation: `HTTP 429 free-models-per-day-high-balance` (rate-limited but normatively captured)

---

## Step 2 — Idempotent repeat (same key)

```
PYTHONPATH= /tmp/capt-test-venv8/bin/capt harness command run_approved_hermes_inspection \
  --payload-json '<same objective>' \
  --idempotency-key idem-version-audit-7 \
  --sock /tmp/capt-test.sock --token-file /tmp/capt-test.token
```

Result: `status: idempotent, classification: duplicate`
- Same driverRunId, verificationId, artifactDigest returned
- ledgerHead: 29 (unchanged)
- No second Hermes process

---

## Step 3 — Checkpoint

```
PYTHONPATH= /tmp/capt-test-venv8/bin/capt harness checkpoint --idempotency-key idem-checkpoint-1 ...
→ status: accepted, checkpointId: cp-cmd-3e02c666f8c60dcb, ledgerHead: 29
```

---

## Step 4 — Stop + socket cleanup

```
PYTHONPATH= /tmp/capt-test-venv8/bin/capt harness stop --idempotency-key idem-stop-1 ...
→ status: accepted, shutdown: accepted
```
Socket `/tmp/capt-test.sock` confirmed removed.

---

## Step 5 — Restart with same ledger

```
PYTHONPATH= /tmp/capt-test-venv8/bin/python3 -m desktop.capt_runtime_service \
  --ledger /tmp/capt-test-ledger/ledger.db --sock /tmp/capt-test.sock --token-file /tmp/capt-test.token
→ HEALTHY, headSequence: 29 (preserved)
```

---

## Step 6 — Resume

```
PYTHONPATH= /tmp/capt-test-venv8/bin/capt harness resume --idempotency-key idem-resume-1 ...
→ status: accepted, execution: not_repeated
```
- checkpoint verified
- original driverRunId + verificationId unchanged

---

## Step 7 — Second distinct governed action

```
PYTHONPATH= /tmp/capt-test-venv8/bin/capt harness command run_approved_hermes_inspection \
  --payload-json '<objective: verify capt_runtime package presence>' \
  --idempotency-key idem-verify-2 ...
→ status: accepted, missionId: m-model-verify-2, verificationId: vr-sha256:c63c410cc, ledgerHead: 45
```
Result included a substantive model response (33-module package inspection).

---

## Step 8 — Final checkpoint + stop

```
→ checkpoint accepted (ledgerHead 45), stop accepted, socket removed
```

---

## VerificationResult persistence evidence

`ClaimVerified` event (global seq 28) for claim cl-model-version-audit-7 persisted:
- claimId, strategy (artifact_hashing), verifiedAt, supportingEvidenceIds — all present
- _view, trust, checks, observedBy — all excluded from persisted payload
- passes frozen VerificationResult contract validation

## Classifications

This proof is:
- locally executed
- installed-wheel (from SHA 4005809)
- real Hermes process
- externally dependent model/provider
- NOT rerun by hosted CI
- subject to a provider rate-limit condition (HTTP 429) during mission-audit-7; second mission had a full response
