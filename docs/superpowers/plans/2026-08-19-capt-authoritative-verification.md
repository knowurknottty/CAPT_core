# CAPT Authoritative Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a CAPT task already in `awaiting_verification` into an independently verified/guarded terminal task without allowing the GPT or any surface adapter to supply the verification outcome.

**Architecture:** Capture a durable CAPT-owned pre-dispatch verification baseline, record it as evidence beside the provider artifact, then add one RuntimeService-owned `verify_pending_task` command that reconstructs all verification inputs from EventStore/evidence. Surface adapters only request that command and report its authoritative receipt.

**Tech Stack:** Python 3.14, CAPT EventStore/RuntimeService, frozen v1 contracts, Unix-domain-socket IPC, pytest, capt-workspace-mcp Actions/MCP surfaces.

**Spec:** `docs/superpowers/specs/2026-08-19-capt-gpt-governed-verification-local-tools-design.md`

## Global Constraints

- RuntimeService/EventStore remain the sole authoritative state path.
- The GPT may request verification but may never submit `verified`, `rejected`, a ClaimGuard verdict, or supporting evidence chosen by the GPT.
- Baseline and result artifacts must resolve inside the approved target scope or the exact CAPT staging root bound to the task/driver run.
- Model/provider output remains evidence only until the verification command records a VerificationResult.
- Contradicted verification follows existing frozen claim semantics; it must never be upgraded by ClaimGuard.
- RuntimeService is not restarted until unit/integration tests pass.
- Existing approval semantics and frozen event/contract schemas are not replaced.

---
### Task 1: Durable verification-baseline artifact

**Files:**
- Create: `capt_runtime/verification_baseline.py`
- Test: `tests/capt_runtime/test_verification_baseline.py`

**Interfaces:**
- Produces: `capture_verification_baseline(target_root, staging_root, mission_id, task_id, driver_run_id, captured_at) -> dict`
- Produces: `load_verified_baseline(path, expected_digest, staging_root, mission_id, task_id, driver_run_id, target_root) -> dict`
- Uses: `capt_runtime.driver_host.tree_digest`, `capt_runtime.verification.capture_git_status`, `capt_runtime.contracts.digest`

- [ ] **Step 1: Write failing capture/load tests**

```python
def test_baseline_round_trip_is_content_addressed(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir(); (repo / "a.txt").write_text("A")
    staging = tmp_path / "staging"
    rec = capture_verification_baseline(str(repo), staging, "m1", "t1", "dr1", "2026-08-19T12:00:00Z")
    assert Path(rec["artifactPath"]).name == "verification-baseline.json"
    loaded = load_verified_baseline(rec["artifactPath"], rec["artifactDigest"], staging, "m1", "t1", "dr1", str(repo))
    assert loaded["beforeDigest"].startswith("sha256:")
```

- [ ] **Step 2: Run the new test and verify RED**

Run: `python3 -m pytest tests/capt_runtime/test_verification_baseline.py -q`
Expected: FAIL because `capt_runtime.verification_baseline` does not exist.
- [ ] **Step 3: Implement the minimal baseline module**

```python
def capture_verification_baseline(target_root, staging_root, mission_id, task_id, driver_run_id, captured_at):
    root = Path(target_root).resolve()
    staging = Path(staging_root).resolve(); staging.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schemaVersion": "1.0.0", "kind": "verification_baseline",
        "missionId": mission_id, "taskId": task_id, "driverRunId": driver_run_id,
        "targetRoot": str(root), "beforeDigest": tree_digest(str(root)),
        "beforeGitStatus": capture_git_status(str(root)), "capturedAt": captured_at,
    }
    raw = canonical_json(manifest).encode("utf-8")
    path = staging / "verification-baseline.json"
    path.write_bytes(raw)
    return {"artifactPath": str(path), "artifactDigest": "sha256:" + hashlib.sha256(raw).hexdigest(), "manifest": manifest}
```

`load_verified_baseline` must hash before parsing, require `kind=verification_baseline`, compare all supplied identities/root, and reject symlink/path mismatch.

- [ ] **Step 4: Add tamper/identity/path tests and run GREEN**

Run: `python3 -m pytest tests/capt_runtime/test_verification_baseline.py -q`
Expected: all tests PASS, including digest tamper, wrong task/run/root, and symlink-escape rejection.

- [ ] **Step 5: Commit Task 1**

```bash
git add capt_runtime/verification_baseline.py tests/capt_runtime/test_verification_baseline.py
git commit -m "feat(runtime): persist verification baselines"
```
### Task 2: Record the pre-dispatch baseline as authoritative claim evidence

**Files:**
- Modify: `desktop/capt_runtime_service.py` in `_execute_approved_hermes`
- Modify: `tests/capt_runtime/test_ouroboros_lifecycle.py`

**Interfaces:**
- Consumes: `capture_verification_baseline(...)`
- Produces: provider/model completion claim with both baseline and result artifact evidence IDs

- [ ] **Step 1: Add a failing model-operator test**

```python
def test_happy_driver_lifecycle_records_baseline_and_result_evidence(tmp_path: Path) -> None:
    repo, exe, suffix = _git_repo(tmp_path, dirty=True), _fake_hermes(tmp_path), "baseline"
    client, _ledger, proc = _start_runtime(tmp_path / "runtime")
    try:
        payload = _authorize_model_run(client, _payload(repo, exe, suffix), suffix)
        receipt = client.command("run_approved_hermes_inspection", payload, "idem-ouro-baseline")
        claim = _state(client, "cl", suffix)
        evidence = project_evidence(client, "m-ouro-" + suffix)
        assert receipt["status"] == "accepted"
        assert len([e for e in evidence if e["claimId"] == claim["claimId"]]) == 2
        assert any(Path(e["artifactPath"]).name == "verification-baseline.json" for e in evidence)
        assert claim["promotionState"] == "proposed"
    finally:
        _stop_runtime(client, proc)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python3 -m pytest tests/capt_runtime/test_ouroboros_lifecycle.py::test_happy_driver_lifecycle_records_baseline_and_result_evidence -q`
Expected: FAIL because only the provider artifact is currently recorded.

- [ ] **Step 3: Capture baseline immediately before reservation/dispatch**

Use the existing per-run staging directory; replace the receipt-only `before/tree + git status` capture with `capture_verification_baseline(...)`. Do not move capture after the external boundary.
- [ ] **Step 4: Record both artifact hashes after claim creation**

Create deterministic IDs such as `ev-baseline-<digest>` and `ev-result-<digest>`, build both with `build_artifact_hash_evidence`, and call `svc.record_evidence` twice. Preserve `verificationId=None` and `awaiting_verification`.

The completion receipt may retain `beforeDigest` for compatibility but must also expose `verificationBaselinePath`, `verificationBaselineDigest`, and `verificationBaselineEvidenceId`; verification logic must not depend on the receipt.

- [ ] **Step 5: Run model operator and claim regression tests**

Run: `python3 -m pytest tests/capt_runtime/test_ouroboros_lifecycle.py tests/capt_runtime/test_claim.py tests/capt_runtime/test_verification_baseline.py -q`
Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add desktop/capt_runtime_service.py tests/capt_runtime/test_ouroboros_lifecycle.py
git commit -m "feat(runtime): record verification baseline evidence"
```

### Task 3: Authoritative `verify_pending_task` orchestration

**Files:**
- Create: `capt_runtime/pending_verification.py`
- Modify: `capt_runtime/services.py` only if a narrow service helper is required
- Create: `tests/capt_runtime/test_pending_verification.py`

Test file defines `_seed_pending_verification_fixture(tmp_path, *, mutate=False)` using `create_runtime`, canonical mission/task/claim/evidence service calls, and a real baseline/result artifact pair. It returns a small namespace with `store`, `svc`, `task_id`, `claim_id`, `now`, and a `meta(step)` CommandMetadata factory.

**Interfaces:**
- Produces: `verify_pending_task(store, service, task_id, claim_id, metadata, now) -> dict`
- Consumes: claim/task EventStore state, recorded EvidenceRecorded payloads, `load_verified_baseline`, `build_verification_result`, `build_contradicted_verification_result`, `RuntimeService.record_verification`, `RuntimeService.decide_claim`, `RuntimeService.transition_task`
- [ ] **Step 1: Write RED orchestration tests**

Cover: missing task, task not `awaiting_verification`, claim/task mismatch, no evidence, duplicate verification, tampered baseline, tampered result artifact, successful verified/accepted path, and idempotent replay.

```python
def test_verify_pending_task_accepts_only_after_independent_checks(tmp_path):
    fixture = _seed_pending_verification_fixture(tmp_path)
    receipt = verify_pending_task(fixture.store, fixture.svc, fixture.task_id, fixture.claim_id, fixture.meta("verify"), fixture.now)
    assert receipt["verification"]["status"]["kind"] == "verified"
    assert receipt["claim"]["promotionState"] == "accepted"
    assert receipt["task"]["state"] == "succeeded"
```

- [ ] **Step 2: Run RED tests**

Run: `python3 -m pytest tests/capt_runtime/test_pending_verification.py -q`
Expected: FAIL because orchestration does not exist.

- [ ] **Step 3: Implement evidence reconstruction and preconditions**

Read the task and claim aggregate by exact IDs. Read only the claim stream's `EvidenceRecorded` events, restrict them to IDs actually attached to the claim, identify the baseline by validated manifest `kind`, and identify the result artifact from the remaining artifact-hash evidence. Reject ambiguous/multiple candidate result artifacts rather than guessing.

- [ ] **Step 4: Implement verification and terminalization**

For a verified result: record VerificationResult, create a `ClaimGuardDecision` with `verdict="accept"`, exact verification ID, claim-authority actor, then transition task `awaiting_verification -> succeeded`.

For a failed invariant/artifact check: persist a contract-valid contradicted verification referencing the evidence whose assertion was contradicted; existing `ClaimAggregate.record_verification` terminally rejects that claim, so do not call ClaimGuard afterward. Transition task to `failed` and return `guardDisposition="not_run_claim_already_rejected"`.

- [ ] **Step 5: Verify idempotency and full focused suite**

Run: `python3 -m pytest tests/capt_runtime/test_pending_verification.py tests/capt_runtime/test_claim.py tests/capt_runtime/test_model_operator.py -q`
Expected: PASS with no duplicate ClaimVerified/ClaimGuardDecided events on replay.
- [ ] **Step 6: Commit Task 3**

```bash
git add capt_runtime/pending_verification.py tests/capt_runtime/test_pending_verification.py capt_runtime/services.py
git commit -m "feat(runtime): verify pending tasks authoritatively"
```

### Task 4: RuntimeService socket command and capability advertisement

**Files:**
- Modify: `desktop/capt_runtime_service.py`
- Create or modify: `tests/capt_runtime/test_desktop_verification_command.py`

**Interfaces:**
- Adds command operation: `verify_pending_task`
- Input payload: `{taskId: str, claimId: str}` only; no status/verdict/evidence fields accepted
- Output: authoritative receipt from `capt_runtime.pending_verification.verify_pending_task`

- [ ] **Step 1: Write RED IPC/service tests**

Assert `capabilities.commandOperations` contains `verify_pending_task`; unknown extra outcome fields are rejected; a valid command drives a seeded awaiting task to the expected terminal state; replay returns the same verification ID.

- [ ] **Step 2: Run RED tests**

Run: `python3 -m pytest tests/capt_runtime/test_desktop_verification_command.py -q`
Expected: FAIL because the operation is not advertised/routed.

- [ ] **Step 3: Add the command handler**

Validate payload key set exactly, build command metadata from the authenticated connection-bound operator/session through the existing command-service path, call the orchestration function, and return its receipt. Never accept actor IDs from the client.

- [ ] **Step 4: Run service/security regressions**

Run: `python3 -m pytest tests/capt_runtime/test_desktop_verification_command.py tests/capt_runtime/test_desktop_m1_adversarial.py tests/capt_runtime/test_model_operator.py -q`
Expected: PASS.
- [ ] **Step 5: Commit Task 4**

```bash
git add desktop/capt_runtime_service.py tests/capt_runtime/test_desktop_verification_command.py
git commit -m "feat(runtime): expose pending verification command"
```

### Task 5: MCP/Actions verification surface

**Files (repo `/Users/knowurknot/capt-workspace-mcp`):**
- Modify: `src/capt_workspace_mcp/runtime_client.py`
- Modify: `src/capt_workspace_mcp/gateway_tools.py`
- Modify: `src/capt_workspace_mcp/chatgpt_tools.py`
- Modify: `src/capt_workspace_mcp/actions_gateway.py`
- Modify: `tests/test_gateway.py`
- Modify: `tests/test_chatgpt_tools.py`
- Modify: `tests/test_actions_gateway.py`

**Interfaces:**
- RuntimeClient operation: `verify_pending_task`
- MCP tool: `capt_verify_pending_task`
- GPT Action: `captVerifyPendingTask`
- HTTP: `POST /v1/tasks/{taskId}/verify` with `{claimId, clientRequestId}`

- [ ] **Step 1: Add RED surface tests**

Tests must prove the surface sends only task/claim identity and idempotency metadata, rejects client-supplied `status`, `verdict`, `verificationId`, or `evidenceIds`, and fails closed if RuntimeService does not advertise `verify_pending_task`.

- [ ] **Step 2: Run RED tests**

Run in `/Users/knowurknot/capt-workspace-mcp`: `.venv/bin/python -m pytest tests/test_gateway.py tests/test_chatgpt_tools.py tests/test_actions_gateway.py -q`
Expected: FAIL on missing operation/tool/route.
- [ ] **Step 3: Implement RuntimeClient/MCP routing**

Add `verify_pending_task` to the canonical governed operation map. `capt_verify_pending_task` accepts only `taskId`, `claimId`, and client idempotency metadata and forwards through RuntimeClient. Do not call Core service methods directly from the MCP surface.

- [ ] **Step 4: Implement the Actions route/OpenAPI operation**

`actions_gateway.py` checks live `capabilities.commandOperations` before mutation, then calls `command("verify_pending_task", {"taskId": task_id, "claimId": claim_id}, client_id)`. Add `captVerifyPendingTask` to the served OpenAPI with a response schema that distinguishes verified/accepted from contradicted/rejected.

- [ ] **Step 5: Run gateway/MCP GREEN suite**

Run: `.venv/bin/python -m pytest tests/test_gateway.py tests/test_chatgpt_tools.py tests/test_actions_gateway.py tests/test_chatgpt_profile.py -q`
Expected: PASS; update expected tool counts intentionally where the new tool is added.

- [ ] **Step 6: Commit the surface changes in `capt-workspace-mcp`**

```bash
git add src/capt_workspace_mcp tests
git commit -m "feat(capt): expose authoritative task verification"
```

### Task 6: Full regression and live dogfood gate

**Files:** no new source unless a failing regression requires a reviewed fix.

- [ ] **Step 1: Run CAPT Core full non-slow suite**

Run with the known-good dependency path:

```bash
RUNTIME_SITE=$($HOME/.capt/runtime-venv/bin/python -c 'import site; print(site.getsitepackages()[0])')
PYTHONPATH="$RUNTIME_SITE${PYTHONPATH:+:$PYTHONPATH}" python3 -m pytest -q
```

Expected: at least baseline `949 passed` plus new tests, zero failures.
- [ ] **Step 2: Run `capt-workspace-mcp` full suite**

Run: `cd /Users/knowurknot/capt-workspace-mcp && .venv/bin/python -m pytest -q`
Expected: zero failures.

- [ ] **Step 3: Verify source tree and managed-service paths before restart**

Confirm the running RuntimeService command/CWD resolves to `/Users/knowurknot/.capt-worktrees/inversion-labs-current-r2`, and the Actions LaunchAgent resolves to `/Users/knowurknot/capt-workspace-mcp/.venv/bin/python -m capt_workspace_mcp.actions_gateway`.

- [ ] **Step 4: Restart RuntimeService only through its existing managed mechanism**

Capture PID, runtime version, ledger head, and integrity before/after. Do not touch sibling Inversion Labs/test runtimes. Restart the Actions gateway independently only after its suite is green.

- [ ] **Step 5: Live Custom-GPT verification smoke**

Use the already-proven model smoke task `m-model-7489247b4e78de39b684b8ad-task-1` / claim `cl-model-cmd-e24591641e84036a` only if it is still exactly `awaiting_verification`, `verificationId=null`, and claim `proposed`. Otherwise prepare a new harmless smoke and stop for exact human approval before execution.

From a fresh Custom GPT conversation, request `captVerifyPendingTask`. The GPT supplies task/claim identity only. Accept ChatGPT's external-call consent once if prompted.

Expected authoritative end state on success: verification status `verified`, ClaimGuard `accept`, claim `accepted`, task `succeeded`, one stable `verificationId`. If baseline/result evidence is contradicted, expected state is claim rejected/task failed; do not force success.

- [ ] **Step 6: Verify ledger/idempotency and no duplicate verification**

Read runtime status, task state, claim stream, and event counts. Repeating the same Action with the same clientRequestId must not create a second `ClaimVerified` or `ClaimGuardDecided` event.

- [ ] **Step 7: Update the Custom GPT Action schema/instructions only after live API acceptance**

Publish `captVerifyPendingTask`; instructions must say the GPT requests verification but never supplies an outcome. Create a fresh conversation after Update because old chats can retain stale Action manifests.

- [ ] **Step 8: Final evidence report**

Report Core commit(s), gateway commit, test totals, exact live runtime head/integrity, task/claim/verification/ClaimGuard state, and any distinction between implemented, live-proven, and still-unproven behavior.
