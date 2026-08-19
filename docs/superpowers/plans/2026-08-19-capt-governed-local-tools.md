# CAPT Governed Local Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give CAPT's Custom GPT/MCP operator bounded local filesystem/git/test/process capabilities through RuntimeService-owned grants, leases, reservations, ToolResults, evidence, verification, and ClaimGuard rather than through a direct shell/workspace bypass.

**Architecture:** Prepare and freeze canonical ToolRequests before execution; consequential requests bind a one-use human approval to the exact tool digest. RuntimeService materializes the mission/task only at execution, issues the capability lifecycle, invokes a server-side registered adapter, persists ToolResult/output artifacts, records evidence, and stops at `awaiting_verification` for Plan 1's authoritative verification command.

**Tech Stack:** Python 3.14, CAPT frozen v1 ToolRequest/ToolResult/Capability contracts, EventStore/RuntimeService, pytest, capt-workspace-mcp MCP/Actions surfaces.

**Spec:** `docs/superpowers/specs/2026-08-19-capt-gpt-governed-verification-local-tools-design.md`

**Dependency:** `docs/superpowers/plans/2026-08-19-capt-authoritative-verification.md` must be implemented and GREEN first.

## Global Constraints

- No string-shell command interface exists.
- The caller never supplies an executable path; process execution uses server-side registry IDs.
- First process registry entry is exactly `system.echo -> /bin/echo` with the limits from the spec.
- Every operation in this bridge is a governed CAPT task; read-only differs only in approval policy.
- Consequential approvals bind operation, normalized arguments, root/scope, tool request digest, task/run IDs, and one use.
- Approval consumption occurs immediately before the external boundary.
- Unknown post-boundary outcomes become `indeterminate`; no silent retry.
- CAPT-governed GPT/MCP profiles may not retain direct filesystem/process mutation or execution bypasses.

---
### Task 1: Immutable prepared-tool request and approval binding

**Files:**
- Create: `capt_runtime/prepared_tool_execution.py`
- Create: `capt_runtime/tool_approval_binding.py`
- Create: `tests/capt_runtime/test_tool_approval_binding.py`

**Interfaces:**
- Produces: `PreparedApprovedToolExecution`
- Produces: `build_bound_tool_approval(tool_request, mission_id, task_id, driver_run_id, target_root, staging_root) -> dict`
- Produces: `tool_request_digest(normalized_request) -> str`

- [ ] **Step 1: Write RED binding tests**

```python
def test_tool_binding_changes_when_any_execution_input_changes():
    base = build_bound_tool_approval(request("filesystem.write"), "m1", "t1", "dr1", "/repo", "/stage")
    changed = build_bound_tool_approval(request("filesystem.write", path="b.txt"), "m1", "t1", "dr1", "/repo", "/stage")
    assert base["toolRequestDigest"] != changed["toolRequestDigest"]
    assert base["approvalBinding"]["kind"] == "tool_request"
```

Also test argument order normalization, immutable nested data, target-root/run/task changes, and that no credential/executable material enters the digest object.

- [ ] **Step 2: Run RED tests**

Run: `python3 -m pytest tests/capt_runtime/test_tool_approval_binding.py -q`
Expected: FAIL because modules do not exist.

- [ ] **Step 3: Implement the prepared binding**

`PreparedApprovedToolExecution` mirrors `PreparedApprovedModelExecution`: frozen deterministic fields, `tool_request_digest`, `prepared_execution_digest`, optional approval request ID, and no external secrets. For frozen v1 compatibility, consequential HumanApproval uses `promptAssemblyDigest=toolRequestDigest` while `scope.approvalBinding.kind="tool_request"` makes semantics explicit.
- [ ] **Step 4: Run GREEN binding tests**

Run: `python3 -m pytest tests/capt_runtime/test_tool_approval_binding.py -q`
Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add capt_runtime/prepared_tool_execution.py capt_runtime/tool_approval_binding.py tests/capt_runtime/test_tool_approval_binding.py
git commit -m "feat(runtime): bind prepared local tool requests"
```

### Task 2: Server-side local tool registry and adapters

**Files:**
- Create: `capt_runtime/local_tool_registry.py`
- Create: `capt_runtime/local_tool_adapters.py`
- Create: `tests/capt_runtime/test_local_tool_adapters.py`

**Interfaces:**
- Produces: `ToolRegistry.resolve(tool_id, operation) -> ToolRegistration`
- Produces: `execute_local_tool(registration, operation, arguments, root, staging_root, timeout_s) -> dict`
- First process registration: `system.echo` only

- [ ] **Step 1: Write RED registry/security tests**

Cover: unknown tool ID, caller executable path rejected, shell/interpreter IDs absent, traversal and symlink escape rejected, output/timeout bounds, and exact `system.echo` constraints (32 args, 4096 input chars, 5 s, 64 KiB, no network/write).

- [ ] **Step 2: Write RED operation tests**

Cover `filesystem.read/write/append/patch/delete`, `git.status`, `git.diff`, `test.pytest`, and `process.argv(system.echo)`. Mutation tests require expected digest / exact old-string preconditions where applicable.
- [ ] **Step 3: Run RED adapter tests**

Run: `python3 -m pytest tests/capt_runtime/test_local_tool_adapters.py -q`
Expected: FAIL because registry/adapters do not exist.

- [ ] **Step 4: Implement rooted filesystem operations**

Canonicalize root and target with `Path.resolve()`, reject target outside root after resolution, and reject symlink escapes. `write` uses atomic replacement; `append`/`patch`/`delete` require an `expectedSha256` of the current file. `patch` additionally requires exactly one `oldString` match. Return bounded view data plus resulting content digest.

- [ ] **Step 5: Implement git/test/process adapters without shell strings**

Use `subprocess.run([...], shell=False, cwd=root, timeout=...)` with fixed argv templates:
- git status: `git status --porcelain=v1`
- git diff: `git diff --no-ext-diff --` plus validated optional relative paths
- pytest: current Python executable `-m pytest` plus a strict allowlist of test-node/path/options; no `-c`, plugin injection, Python `-c`, shell, or environment override
- process: registration executable plus validated arguments; initial registration only `/bin/echo`

- [ ] **Step 6: Persist bounded output artifacts**

When output is too large or semantically important (file read, git diff, test/process stdout/stderr), write deterministic CAPT staging artifacts and return their paths/digests in the adapter view. Never write staging artifacts under the target repository.

- [ ] **Step 7: Run GREEN adapter/security tests**

Run: `python3 -m pytest tests/capt_runtime/test_local_tool_adapters.py -q`
Expected: PASS, including all escape-hatch denial tests.

- [ ] **Step 8: Commit Task 2**

```bash
git add capt_runtime/local_tool_registry.py capt_runtime/local_tool_adapters.py tests/capt_runtime/test_local_tool_adapters.py
git commit -m "feat(runtime): add bounded local tool adapters"
```
### Task 3: RuntimeService prepare/execute orchestration

**Files:**
- Create: `capt_runtime/governed_tools.py`
- Modify: `capt_runtime/services.py` only for narrow reusable capability/approval helpers
- Create: `tests/capt_runtime/test_governed_tools.py`

**Interfaces:**
- Produces: `prepare_tool_request(store, service, request, metadata, now, staging_root) -> dict`
- Produces: `execute_prepared_tool_request(runtime, prepared, metadata, now) -> dict`
- Consumes: Plan 1 `verify_pending_task` later, but execute stops at `awaiting_verification`

- [ ] **Step 1: Write RED preparation tests**

Assert deterministic IDs/digests, no mission/task aggregate before execution, read-only operations return `requiresApproval=False`, consequential operations create one HumanApproval aggregate with `scope.approvalBinding.kind="tool_request"`, `remainingUses=1`, and exact target/operation/args binding.

- [ ] **Step 2: Write RED execution lifecycle tests**

Assert `TaskCreated -> ready -> assigned -> running -> awaiting_verification`, PolicyEvaluated, CapabilityGranted, CapabilityLeaseActivated, CapabilityUseReserved, adapter execution, CapabilityUseFinalized, TaskResultSubmitted, ClaimCreated, and EvidenceRecorded occur in the authoritative ledger.

- [ ] **Step 3: Run RED tests**

Run: `python3 -m pytest tests/capt_runtime/test_governed_tools.py -q`
Expected: FAIL because orchestration does not exist.

- [ ] **Step 4: Implement preparation**

Normalize the caller request into a frozen ToolRequest-shaped binding. For consequential operations call existing HumanApproval request machinery with the tool digest in the frozen legacy digest slot; preparation never invokes an adapter or touches the target filesystem.
- [ ] **Step 5: Implement exact approval admission for consequential tools**

At execution, re-derive the binding from the immutable prepared object, require the matching approval state/digest/operation/task/run/root, and atomically consume the one-use approval at the same transaction boundary that persists the DriverRun dispatch intent. A stale/mismatched/consumed approval fails before adapter execution.

- [ ] **Step 6: Implement capability lifecycle and adapter dispatch**

Create the governed mission/task, evaluate policy, issue grant, activate lease, reserve use, then call the resolved adapter. Finalize `succeeded`, `failed`, or `indeterminate` exactly once. If the external boundary may have been crossed and no result is known, mark DriverRun lost/suspend task for reconciliation; never redispatch.

- [ ] **Step 7: Persist canonical ToolResult and evidence**

Serialize the frozen-contract ToolResult to `<staging>/tool-result.json`, hash it, call `submit_result(task_id, {"status":"succeeded","resultRef":"artifact://sha256/<hex>"}, ...)`, propose the bounded completion claim `Governed local tool operation completed with recorded ToolResult evidence.`, record ToolResult artifact evidence, plus operation-specific evidence (target artifact hash or command-exit/output digest), and leave task `awaiting_verification`.

- [ ] **Step 8: Add tool claim to bounded ClaimGuard vocabulary**

Modify `capt_runtime/verification.py` so `guard_claim` accepts exactly the bounded local-tool completion statement above; add a test proving stronger claims such as “command safely changed the repository” remain rejected.

- [ ] **Step 9: Run GREEN lifecycle tests**

Run: `python3 -m pytest tests/capt_runtime/test_governed_tools.py tests/capt_runtime/test_claim.py tests/capt_runtime/test_local_tool_adapters.py -q`
Expected: PASS.

- [ ] **Step 10: Commit Task 3**

```bash
git add capt_runtime/governed_tools.py capt_runtime/services.py capt_runtime/verification.py tests/capt_runtime/test_governed_tools.py tests/capt_runtime/test_claim.py
git commit -m "feat(runtime): govern local tool execution lifecycle"
```
### Task 4: RuntimeService socket commands and capability inventory

**Files:**
- Modify: `desktop/capt_runtime_service.py`
- Create: `tests/capt_runtime/test_desktop_tool_commands.py`

**Interfaces:**
- Adds command: `prepare_tool_request`
- Adds command: `execute_prepared_tool_request`
- Reuses: `submit_approval_decision`, `verify_pending_task`

- [ ] **Step 1: Write RED command tests**

Assert capability advertisement, exact payload schemas, authenticated connection-owned operator/session identity, read-only preparation without approval, consequential preparation with approval, and execution failure if `executionBinding` differs by one argument/root/task/run/tool digest.

- [ ] **Step 2: Run RED tests**

Run: `python3 -m pytest tests/capt_runtime/test_desktop_tool_commands.py -q`
Expected: FAIL because commands are missing.

- [ ] **Step 3: Add prepare command routing**

Accept only documented operation/arguments/root/toolId/client-supplied task continuity fields. Build deterministic command metadata from the authenticated session and return the prepared receipt/approval summary; do not execute.

- [ ] **Step 4: Add execute command routing**

Require the complete execution binding returned by preparation. Recreate `PreparedApprovedToolExecution` only through the trusted preparation function, compare its digest to the supplied binding, then pass the immutable object to execution. Do not execute from the raw HTTP/MCP payload.

- [ ] **Step 5: Run command/security suite GREEN**

Run: `python3 -m pytest tests/capt_runtime/test_desktop_tool_commands.py tests/capt_runtime/test_desktop_m1_adversarial.py tests/capt_runtime/test_governed_tools.py -q`
Expected: PASS.
- [ ] **Step 6: Commit Task 4**

```bash
git add desktop/capt_runtime_service.py tests/capt_runtime/test_desktop_tool_commands.py
git commit -m "feat(runtime): expose governed local tool commands"
```

### Task 5: CAPT-governed MCP and GPT Actions surfaces

**Files (repo `/Users/knowurknot/capt-workspace-mcp`):**
- Modify: `src/capt_workspace_mcp/runtime_client.py`
- Modify: `src/capt_workspace_mcp/operator_contract.py`
- Modify: `src/capt_workspace_mcp/gateway_tools.py`
- Modify: `src/capt_workspace_mcp/chatgpt_tools.py`
- Modify: `src/capt_workspace_mcp/chatgpt_profile.py`
- Modify: `src/capt_workspace_mcp/actions_gateway.py`
- Modify: `src/capt_workspace_mcp/tools.py`
- Modify: `tests/test_gateway.py`
- Modify: `tests/test_chatgpt_profile.py`
- Modify: `tests/test_chatgpt_tools.py`
- Modify: `tests/test_actions_gateway.py`

**Interfaces:**
- MCP: `capt_prepare_tool`, `capt_execute_tool`
- Actions: `captPrepareTool`, `captExecuteTool`
- Existing `captDenyApproval` / approval lookup are reused for consequential tool approvals

- [ ] **Step 1: Write RED governed-profile tests**

Assert the CAPT-governed ChatGPT profile does not expose direct `file_write`, `file_append`, `file_patch`, `file_delete`, `run_command`, or `run_pytest` paths that bypass RuntimeService. Read-only legacy workspace operations must either route through the governed bridge or be absent from this profile.
- [ ] **Step 2: Write RED prepare/execute surface tests**

`captPrepareTool`/`capt_prepare_tool` must return `requiresApproval`, exact digest/IDs, and `executionBinding`; `captExecuteTool`/`capt_execute_tool` must reject altered binding, missing approval for consequential operations, or unsupported RuntimeService capability. Surfaces never accept executable paths or shell command strings.

- [ ] **Step 3: Run RED surface tests**

Run in `/Users/knowurknot/capt-workspace-mcp`: `.venv/bin/python -m pytest tests/test_gateway.py tests/test_chatgpt_profile.py tests/test_chatgpt_tools.py tests/test_actions_gateway.py -q`
Expected: FAIL on missing governed tool surface/profile restrictions.

- [ ] **Step 4: Route the canonical operations through RuntimeClient**

Extend RuntimeClient's governed operation map for `prepare_tool_request` and `execute_prepared_tool_request`. Both fail closed when the live RuntimeService capability inventory lacks the command.

- [ ] **Step 5: Lock down the CAPT-governed profile**

In `chatgpt_profile.py` / `chatgpt_tools.py`, replace direct workspace write/process/test exposure with the governed CAPT tools. Keep ordinary non-CAPT workspace profiles unchanged. Do not delete the underlying legacy implementations if other profiles still use them.

- [ ] **Step 6: Add Actions routes/OpenAPI**

Add `POST /v1/tools/prepare` and `POST /v1/tools/execute` with operation IDs `captPrepareTool` and `captExecuteTool`. `captPrepareTool` may create a one-use approval but never execute; `captExecuteTool` requires the exact returned binding and approval identity where required.

- [ ] **Step 7: Run GREEN surface suite**

Run: `.venv/bin/python -m pytest tests/test_gateway.py tests/test_chatgpt_profile.py tests/test_chatgpt_tools.py tests/test_actions_gateway.py -q`
Expected: PASS with intentional tool-count updates and no hidden legacy bypass in the CAPT-governed profile.
- [ ] **Step 8: Commit Task 5 in `capt-workspace-mcp`**

```bash
git add src/capt_workspace_mcp tests
git commit -m "feat(capt): route local tools through runtime governance"
```

### Task 6: Full regression and live tool dogfood

**Files:** no new source unless a verified regression requires a reviewed fix.

- [ ] **Step 1: Run CAPT Core full non-slow suite**

```bash
cd /Users/knowurknot/.capt-worktrees/inversion-labs-current-r2
RUNTIME_SITE=$($HOME/.capt/runtime-venv/bin/python -c 'import site; print(site.getsitepackages()[0])')
PYTHONPATH="$RUNTIME_SITE${PYTHONPATH:+:$PYTHONPATH}" python3 -m pytest -q
```

Expected: zero failures and all new verification/tool tests included.

- [ ] **Step 2: Run `capt-workspace-mcp` full suite**

Run: `cd /Users/knowurknot/capt-workspace-mcp && .venv/bin/python -m pytest -q`
Expected: zero failures.

- [ ] **Step 3: Managed restart and capability readback**

Verify the exact live RuntimeService source/CWD, restart only through the existing managed mechanism, then read `capabilities` and prove `verify_pending_task`, `prepare_tool_request`, and `execute_prepared_tool_request` are advertised. Restart only the repo-backed Actions gateway after its suite is green.
- [ ] **Step 4: Live read-only tool smoke through the Custom GPT**

From a fresh post-Update GPT chat, prepare and execute `git.status` against the allowlisted CAPT root. No separate human approval should be created, but RuntimeService must materialize the governed task/capability/ToolResult/evidence path. Then call `captVerifyPendingTask` and prove terminal success.

- [ ] **Step 5: Live consequential mutation smoke through the Custom GPT**

Use a disposable file under an explicitly allowlisted test directory, not production source. Prepare `filesystem.write` with exact content and expected precondition. Stop at `approval_required` and present the exact approval ID/digest/binding to the human. Execute only after explicit approval, once, then independently verify and terminalize.

Expected proof: one approval use, one DriverRun, one reservation/consumption, target digest matches ToolResult, task moves through `awaiting_verification` to terminal state, and replay does not duplicate the side effect.

- [ ] **Step 6: `system.echo` process-boundary smoke**

Prepare `process.argv` with `toolId=system.echo` and a harmless token. Because process execution is consequential in this tranche, stop for exact human approval; after approval prove argv-only dispatch, bounded stdout artifact/digest, no shell process, and independent terminal verification.

- [ ] **Step 7: Negative escape tests against the live surface**

Prove denial of caller executable path, `zsh -c`, `bash -c`, Python `-c`, path traversal, symlink escape, unsupported tool IDs, changed execution binding, stale/consumed approval, and an out-of-allowlist root. Confirm none creates an external side effect.

- [ ] **Step 8: Publish Custom GPT schema/instruction update**

Add `captPrepareTool`/`captExecuteTool`; preserve `captVerifyPendingTask`. Instructions must require exact human approval for consequential tools, forbid shell/executable invention, and require verification before claiming completion. Use a fresh conversation after Update.

- [ ] **Step 9: Final evidence report**

Report both repo commit stacks, full test totals, current runtime head/integrity, exact live task/approval/driver/evidence/verification/ClaimGuard states for the read-only and consequential smokes, and explicitly list SSH/Docker/browser/RDC as still out of scope until their adapter tranche.
