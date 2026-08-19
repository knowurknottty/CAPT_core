# ToolBroker Slice A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver CAPT's governed ToolBroker substrate with truthful tool readiness, durable execution settlement/recovery, and real Local Terminal, File Operations, and Python Code Execution.

**Architecture:** RuntimeService/EventStore remain authoritative. Authenticated callers admit a typed tool request; ToolBroker validates descriptor/readiness/capability/effect policy, persists execution intent before external dispatch, invokes a typed adapter, and settles result/effect state durably. Local process/file/code adapters never become an alternate runtime or authority path.

**Tech Stack:** Python 3.12+, SQLite EventStore, generated JSON-Schema contracts with Python/TypeScript parity, POSIX subprocess/process groups, pytest, SwiftPM regression gate.

**Spec:** `docs/superpowers/specs/2026-08-19-release-tool-broker-terminal-v1-design.md`

## Global Constraints

- Initial terminal backend set is exactly `local`, `ssh`, `docker`; Slice A implements `local` only and must not introduce another backend.
- RuntimeService and EventStore remain authoritative; UI/CLI/TUI/native surfaces remain renderer/controllers.
- Normal tool execution path is authenticated RuntimeService admission -> ToolBroker -> adapter -> settlement/evidence.
- No normal operator path may invoke an adapter directly.
- Tool permissions are operation- and target-scoped, never a monolithic `tools` grant.
- Readiness states are exactly `available`, `degraded`, `unavailable`, `unverified`.
- Effect classes remain distinct: pure/read-only, ephemeral external, durable local, durable remote, resource creation.
- Persist sufficient execution state before external dispatch; never blindly redispatch an ambiguous effect.
- Exact settled replay returns the prior settled result; conflicting idempotency reuse fails closed.
- Local filesystem/cwd checks are canonical and symlink-aware before spawn or write.
- Child environment is explicit/allowlisted; CAPT never inserts `sudo`.
- stdout/stderr capture is memory-bounded while the process is running, not merely truncated after `communicate()`.
- Tool output/evidence is not verification; no task/mission completion is implied.
- No mocks/stubs/fake integrations in acceptance paths.

---## File Structure

**Contracts / durable state**
- Modify `contracts/schema/tool.schema.json`: descriptor, readiness, effect, execution/request/result contracts.
- Modify `contracts/schema/event.schema.json`: closed ToolExecution event variants.
- Regenerate `contracts/generated/python/capt_contracts/*` and `contracts/generated/typescript/src/*`.
- Create `capt_runtime/aggregates/tool_execution.py`: monotonic ToolExecution state transitions only.
- Modify `capt_runtime/aggregates/__init__.py`: export ToolExecutionAggregate.
- Modify `capt_runtime/services.py`: authoritative append/transition methods for tool execution.

**Broker / registry**
- Create `capt_runtime/tools/__init__.py`: public Slice-A tool types/exports.
- Create `capt_runtime/tools/registry.py`: typed descriptor registry, uniqueness, lookup, readiness.
- Create `capt_runtime/tools/scope.py`: filesystem canonicalization/containment helpers.
- Create `capt_runtime/tool_broker.py`: admission, capability reservation, dispatch, settlement, replay, recovery.
- Modify `capt_runtime/composition.py`: own one ToolRegistry + ToolBroker per RuntimeComposition.

**Execution adapters**
- Create `capt_runtime/tools/backends/local.py`: bounded local process runner.
- Create `capt_runtime/tools/adapters/file.py`: scoped read/write operations.
- Create `capt_runtime/tools/adapters/code.py`: real Python execution over LocalProcessBackend.
- Create `capt_runtime/tools/builtins.py`: Slice-A descriptors and adapter registration.

**Governed command path**
- Modify `desktop/m1_command_service.py`: authenticated `run_tool` routing only; no adapter logic.
- Modify `desktop/capt_runtime_service.py`: bind RuntimeCommandService to composition-owned ToolBroker.

**Tests**
- Create focused tests under `tests/capt_runtime/test_tool_*.py` as specified below.

---### Task 1: Contract the ToolBroker vocabulary

**Files:**
- Modify: `contracts/schema/tool.schema.json`
- Modify: `contracts/schema/event.schema.json`
- Test: `tests/capt_runtime/test_tool_contracts.py`
- Regenerate: `contracts/generated/python/capt_contracts/*`, `contracts/generated/typescript/src/*`

**Interfaces:**
- Produces: `ToolDescriptor`, `ToolReadiness`, `ToolEffectClass`, `ToolExecutionState`, `ToolExecution`, extended `ToolRequest`, and closed ToolExecution event payloads.
- Consumes: existing `ToolArgument`, `ToolResult`, `Identifier`, `Digest`, `Timestamp`, and EventEnvelope machinery.

- [ ] **Step 1: Write contract tests before schema changes**

```python
from capt_runtime.contracts import require


def test_tool_descriptor_and_execution_contracts_are_closed():
    require("ToolDescriptor", {
        "schemaVersion": "1.0.0", "toolId": "terminal.local", "displayName": "Terminal & Processes",
        "family": "terminal", "operations": ["terminal.exec"], "requiredCapabilities": ["terminal.exec"],
        "effectByOperation": {"terminal.exec": "ephemeral_external"}, "terminalBackends": ["local"],
        "platforms": ["macos", "linux"], "supportsTimeout": True, "supportsCancellation": True,
        "idempotencySupport": "broker_settled_replay", "artifactOutputs": [],
    })
```

- [ ] **Step 2: Run the focused test and observe RED because the new contract types are unknown**

Run: `python -m pytest tests/capt_runtime/test_tool_contracts.py -q`
Expected: FAIL naming `ToolDescriptor`/`ToolExecution` as unknown types.- [ ] **Step 3: Add the minimal normative schemas**

Add enums with exact values:
```json
"ToolReadinessStatus": {"type":"string","enum":["available","degraded","unavailable","unverified"]},
"ToolEffectClass": {"type":"string","enum":["pure_read_only","ephemeral_external","durable_local","durable_remote","resource_creation"]},
"ToolExecutionState": {"type":"string","enum":["prepared","admitted","dispatching","effect_observed","settling","completed","failed","cancelled","indeterminate"]}
```

Extend `ToolRequest` with nullable `grantId`, `backendId`, `targetIdentity`, and explicit `filesystemScope`. Add `ToolExecution` fields for execution id, request/fingerprint, descriptor/adapter/backend identity, capability/lease identity, effect class, dispatch boundary, result/error digest, resource ids, settlement, cancellation, and timestamps. Add closed events `ToolExecutionPrepared`, `ToolExecutionAdmitted`, `ToolExecutionDispatching`, `ToolExecutionEffectObserved`, `ToolExecutionSettling`, and `ToolExecutionTerminated`.

- [ ] **Step 4: Regenerate and verify generated parity**

Run:
```bash
python3 contracts/tools/generate.py
python3 contracts/tools/check_drift.py
```
Expected: generation succeeds; drift check prints OK.

- [ ] **Step 5: Run focused contracts and existing contract suite**

Run: `python -m pytest tests/capt_runtime/test_tool_contracts.py tests/capt_runtime/test_contracts.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add contracts tests/capt_runtime/test_tool_contracts.py
git commit -m "feat(tool): define governed ToolBroker contracts"
```

---### Task 2: Registry and truthful readiness

**Files:**
- Create: `capt_runtime/tools/__init__.py`
- Create: `capt_runtime/tools/registry.py`
- Create: `capt_runtime/tools/builtins.py`
- Test: `tests/capt_runtime/test_tool_registry.py`

**Interfaces:**
- Produces: `ToolRegistry.register(descriptor, adapter, readiness_probe)`, `require(tool_id)`, `readiness(tool_id)`, `list_descriptors()`.
- Produces Slice-A ids: `terminal.local`, `file.operations`, `code.execution`.

- [ ] **Step 1: RED duplicate/readiness tests**
```python
def test_registry_rejects_duplicate_tool_id():
    reg = ToolRegistry(); reg.register(DESC, object(), lambda: ToolReadiness.available())
    with pytest.raises(DuplicateToolId): reg.register(DESC, object(), lambda: ToolReadiness.available())


def test_probe_failure_is_unavailable_not_pass():
    reg = ToolRegistry(); reg.register(DESC, object(), lambda: (_ for _ in ()).throw(OSError("missing")))
    assert reg.readiness(DESC["toolId"]).status == "unavailable"
```
- [ ] **Step 2:** Run focused test; expect import/type failures.
- [ ] **Step 3:** Implement registry as metadata/control only; registry never executes adapters during `register()` and probe errors become reason-bearing truthful readiness.
- [ ] **Step 4:** Add exact Slice-A descriptors with operation/effect mappings: `terminal.exec -> ephemeral_external`, `file.read -> pure_read_only`, `file.write -> durable_local`, `code.execute_python -> ephemeral_external`.
- [ ] **Step 5:** Run `python -m pytest tests/capt_runtime/test_tool_registry.py -q`; expect PASS.
- [ ] **Step 6:** Commit `feat(tool): add descriptor registry and readiness`.

---

### Task 3: Durable ToolExecution aggregate

**Files:**
- Create: `capt_runtime/aggregates/tool_execution.py`
- Modify: `capt_runtime/aggregates/__init__.py`
- Modify: `capt_runtime/services.py`
- Test: `tests/capt_runtime/test_tool_execution.py`

**Interfaces:**
- Produces: `ToolExecutionAggregate.prepare`, `.transition`, `.stream_id`.
- Produces RuntimeService methods `prepare_tool_execution(execution, metadata)` and `transition_tool_execution(execution_id, to_state, patch, metadata)`.- [ ] **Step 1: RED lifecycle tests**
```python
def test_tool_execution_lifecycle_is_monotonic():
    state = ToolExecutionAggregate.prepare(EXECUTION)
    state = ToolExecutionAggregate.transition(state, "admitted", {})
    state = ToolExecutionAggregate.transition(state, "dispatching", {"dispatchBoundary": "started"})
    state = ToolExecutionAggregate.transition(state, "settling", {"resultDigest": DIGEST})
    state = ToolExecutionAggregate.transition(state, "completed", {"settlementStatus": "settled"})
    with pytest.raises(IllegalTransition): ToolExecutionAggregate.transition(state, "dispatching", {})


def test_dispatching_execution_can_be_marked_indeterminate_after_restart():
    state = ToolExecutionAggregate.transition(ToolExecutionAggregate.prepare(EXECUTION), "admitted", {})
    state = ToolExecutionAggregate.transition(state, "dispatching", {"dispatchBoundary": "started"})
    assert ToolExecutionAggregate.transition(state, "indeterminate", {"settlementStatus": "reconciliation_required"})["state"] == "indeterminate"
```
- [ ] **Step 2:** Run focused test; expect RED because aggregate/service methods do not exist.
- [ ] **Step 3:** Implement explicit allowed-transition table. Terminal states are immutable. `completed` requires settled result identity; `indeterminate` requires reconciliation reason. Aggregate contains facts only, no adapter calls.
- [ ] **Step 4:** Add RuntimeService event append methods using only the closed events from Task 1.
- [ ] **Step 5:** Run `python -m pytest tests/capt_runtime/test_tool_execution.py tests/capt_runtime/test_ledger.py -q`; expect PASS and valid hash chain.
- [ ] **Step 6:** Commit `feat(tool): persist ToolExecution lifecycle`.

---

### Task 4: ToolBroker admission, settlement, replay, and recovery

**Files:**
- Create: `capt_runtime/tool_broker.py`
- Modify: `capt_runtime/composition.py`
- Test: `tests/capt_runtime/test_tool_broker.py`

**Interfaces:**
- Produces: `ToolBroker.execute(request, *, operator_id, session_id) -> dict`.
- Produces: `ToolBroker.reconcile_stranded() -> list[dict]`.
- Consumes: ToolRegistry, RuntimeService live capability checks/reservations/finalization, EventStore idempotency, registered adapter `execute(request) -> AdapterResult`.

- [ ] **Step 1: RED exact-replay and conflict tests**
```python
def test_exact_settled_replay_never_invokes_adapter_twice(broker, adapter):
    first = broker.execute(REQUEST, operator_id="op", session_id="s")
    second = broker.execute(REQUEST, operator_id="op", session_id="s")
    assert first["toolExecutionId"] == second["toolExecutionId"]
    assert adapter.calls == 1


def test_same_idempotency_key_changed_request_fails_closed(broker):
    broker.execute(REQUEST, operator_id="op", session_id="s")
    with pytest.raises(IdempotencyConflict): broker.execute({**REQUEST, "operation": "other.op"}, operator_id="op", session_id="s")
```
- [ ] **Step 2:** Run focused test; expect RED because ToolBroker does not exist.- [ ] **Step 3: RED capability/effect tests**
```python
def test_consequential_tool_requires_live_bound_lease(broker):
    with pytest.raises(CapabilityDenied): broker.execute(CONSEQUENTIAL_WITHOUT_LEASE, operator_id="op", session_id="s")


def test_indeterminate_adapter_result_consumes_reservation_without_redispatch(broker, adapter):
    adapter.result_status = "indeterminate"
    result = broker.execute(CONSEQUENTIAL_REQUEST, operator_id="op", session_id="s")
    assert result["status"] == "indeterminate"
    replay = broker.execute(CONSEQUENTIAL_REQUEST, operator_id="op", session_id="s")
    assert replay["status"] == "indeterminate"
    assert adapter.calls == 1
```
- [ ] **Step 4:** Implement broker order exactly: descriptor/readiness -> request/fingerprint binding -> durable prepared -> live lease check -> reservation for consequential use -> admitted -> dispatching -> adapter -> effect/result observation -> settling -> capability finalization -> terminal ToolExecution -> complete idempotency receipt.
- [ ] **Step 5:** Ensure adapter exceptions after dispatch boundary settle `failed` only when the adapter can prove no ambiguous effect; otherwise settle `indeterminate`.
- [ ] **Step 6: RED restart recovery test**
```python
def test_restart_marks_unreconciled_dispatching_execution_indeterminate(tmp_path):
    # persist state through dispatching, construct a new broker on the same ledger
    recovered = restarted_broker.reconcile_stranded()
    assert recovered[0]["state"] == "indeterminate"
    assert adapter.calls == 0
```
- [ ] **Step 7:** Implement `reconcile_stranded()` by scanning durable `tool_execution` aggregates. `prepared` can remain non-dispatched; `dispatching/effect_observed/settling` calls adapter reconciliation only when supported, otherwise transitions to `indeterminate`; never invokes adapter execution.
- [ ] **Step 8:** Run `python -m pytest tests/capt_runtime/test_tool_broker.py tests/capt_runtime/test_capability.py -q`; expect PASS.
- [ ] **Step 9:** Commit `feat(tool): add governed ToolBroker settlement boundary`.

---

### Task 5: Local process backend with bounded resources

**Files:**
- Create: `capt_runtime/tools/scope.py`
- Create: `capt_runtime/tools/backends/__init__.py`
- Create: `capt_runtime/tools/backends/local.py`
- Test: `tests/capt_runtime/test_local_tool_backend.py`

**Interfaces:**
- Produces `LocalProcessRequest(argv, cwd, env_allowlist, env_overrides, timeout_seconds, stdout_limit_bytes, stderr_limit_bytes, filesystem_root)`.
- Produces `LocalProcessResult(exit_code, stdout, stderr, stdout_total_bytes, stderr_total_bytes, stdout_truncated, stderr_truncated, started_at, completed_at, pid, process_group_id, timed_out, cancelled)`.
- Produces `require_scoped_path(root, target, *, for_write=False) -> Path`.

- [ ] **Step 1: RED scope escape tests**
```python
def test_symlink_cwd_escape_is_denied(tmp_path):
    root = tmp_path / "root"; root.mkdir(); outside = tmp_path / "outside"; outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(AuthorityViolation): require_scoped_path(root, root / "escape")
```
- [ ] **Step 2:** Run focused test; expect RED because scope helper does not exist.
- [ ] **Step 3:** Implement containment using resolved canonical paths and `os.path.commonpath`; for a nonexistent write target, strictly resolve the parent and reject existing symlink target escapes.- [ ] **Step 4: RED streaming-output and timeout tests**
```python
def test_stdout_is_bounded_during_execution(local_backend, tmp_path):
    r = local_backend.execute(LocalProcessRequest(argv=[sys.executable, "-c", "print('x'*200000)"], cwd=tmp_path, filesystem_root=tmp_path, stdout_limit_bytes=4096))
    assert len(r.stdout.encode()) <= 4096
    assert r.stdout_total_bytes > 4096 and r.stdout_truncated is True


def test_timeout_kills_process_group(local_backend, tmp_path):
    r = local_backend.execute(LocalProcessRequest(argv=[sys.executable, "-c", "import time; time.sleep(30)"], cwd=tmp_path, filesystem_root=tmp_path, timeout_seconds=0.2))
    assert r.timed_out is True
```
- [ ] **Step 5:** Implement `Popen(..., start_new_session=True)` with reader threads that drain pipes continuously while retaining at most configured bytes and counting total bytes. Do not use unlimited `communicate()` capture. On timeout/cancel send SIGTERM to the process group, wait a bounded grace interval, then SIGKILL if needed.
- [ ] **Step 6:** Build child env from a small safe base (`PATH`, `HOME`, `USER`, locale/temp variables) intersected with the request allowlist plus explicit non-secret overrides. Never copy arbitrary parent secrets.
- [ ] **Step 7:** Run `python -m pytest tests/capt_runtime/test_local_tool_backend.py -q`; expect PASS.
- [ ] **Step 8:** Commit `feat(tool): add bounded local process backend`.

---

### Task 6: File Operations adapter

**Files:**
- Create: `capt_runtime/tools/adapters/__init__.py`
- Create: `capt_runtime/tools/adapters/file.py`
- Modify: `capt_runtime/tools/builtins.py`
- Test: `tests/capt_runtime/test_file_tool.py`

**Interfaces:**
- Produces `FileToolAdapter.execute(request) -> AdapterResult` for `file.read` and `file.write`.
- Uses `require_scoped_path`; writes return before/after SHA-256 identity and byte count.

- [ ] **Step 1: RED read/write and symlink tests**
```python
def test_write_is_atomic_and_digest_bound(adapter, scoped_request, tmp_path):
    result = adapter.execute(scoped_request("file.write", path=tmp_path/"a.txt", content="abc"))
    assert (tmp_path/"a.txt").read_text() == "abc"
    assert result.side_effect_identity["afterDigest"].startswith("sha256:")


def test_write_through_escape_symlink_is_denied(adapter, scoped_request, escape_link):
    with pytest.raises(AuthorityViolation): adapter.execute(scoped_request("file.write", path=escape_link/"x", content="bad"))
```
- [ ] **Step 2:** Run focused test; expect RED because FileToolAdapter does not exist.
- [ ] **Step 3:** Implement bounded reads and atomic same-directory temp-file + `os.replace()` writes. Capture prior digest when a file exists; do not follow a target symlink outside admitted scope.
- [ ] **Step 4:** Register adapter/descriptors without exposing a direct operator path.
- [ ] **Step 5:** Run `python -m pytest tests/capt_runtime/test_file_tool.py tests/capt_runtime/test_tool_broker.py -q`; expect PASS.
- [ ] **Step 6:** Commit `feat(tool): add governed file operations adapter`.

---### Task 7: Real Python Code Execution adapter

**Files:**
- Create: `capt_runtime/tools/adapters/code.py`
- Modify: `capt_runtime/tools/builtins.py`
- Test: `tests/capt_runtime/test_code_execution_tool.py`

**Interfaces:**
- Produces `CodeExecutionAdapter.execute(request) -> AdapterResult` for `code.execute_python`.
- Consumes LocalProcessBackend; no nested Hermes RPC, provider call, or direct subprocess bypass.

- [ ] **Step 1: RED real-execution tests**
```python
def test_python_code_executes_in_scoped_cwd(adapter, request, tmp_path):
    result = adapter.execute(request(code="from pathlib import Path; print(Path.cwd().name)", cwd=tmp_path))
    assert result.status == "succeeded"
    assert tmp_path.name in result.output["stdout"]


def test_parent_secret_is_not_visible(adapter, request, monkeypatch, tmp_path):
    monkeypatch.setenv("CAPT_TEST_SECRET_TOKEN", "should-not-leak")
    result = adapter.execute(request(code="import os; print(os.getenv('CAPT_TEST_SECRET_TOKEN'))", cwd=tmp_path))
    assert result.output["stdout"].strip() == "None"
```
- [ ] **Step 2:** Run focused test; expect RED because adapter does not exist.
- [ ] **Step 3:** Write submitted Python to a CAPT-owned temporary script with `0600` permissions, execute `sys.executable <script>` via LocalProcessBackend, and always remove the script afterward. Cwd is the admitted scoped cwd; the temp script itself is not an authority-bearing artifact.
- [ ] **Step 4:** Preserve LocalProcessBackend timeout/output/cancel/env semantics. Return real exit code/stdout/stderr digests and never claim sandbox isolation beyond what is actually enforced.
- [ ] **Step 5:** Run `python -m pytest tests/capt_runtime/test_code_execution_tool.py tests/capt_runtime/test_local_tool_backend.py -q`; expect PASS.
- [ ] **Step 6:** Commit `feat(tool): add governed Python code execution`.

---

### Task 8: Authenticated RuntimeService command wiring

**Files:**
- Modify: `desktop/m1_command_service.py`
- Modify: `desktop/capt_runtime_service.py`
- Modify: `capt_runtime/composition.py`
- Test: `tests/capt_runtime/test_tool_runtime_command.py`

**Interfaces:**
- Adds authenticated command operation `run_tool`.
- RuntimeCommandService calls composition-owned `ToolBroker`; it never imports FileToolAdapter/CodeExecutionAdapter/LocalProcessBackend.
- Runtime capability discovery advertises `run_tool` only when the ToolBroker is wired.

- [ ] **Step 1: RED routing and unavailable-broker tests**
```python
def test_run_tool_routes_only_through_bound_broker(command_service, broker):
    command_service.tool_broker = broker
    receipt = command_service.execute(_envelope("run_tool", REQUEST))
    assert receipt["status"] == "accepted"
    assert broker.calls == 1


def test_run_tool_without_broker_fails_closed(command_service):
    receipt = command_service.execute(_envelope("run_tool", REQUEST))
    assert receipt["status"] == "rejected"
    assert receipt["error"]["code"] == "TOOL_BROKER_UNAVAILABLE"
```
- [ ] **Step 2:** Run focused test; expect RED because `run_tool` is not an allowed command.
- [ ] **Step 3:** Add the smallest command-service branch that validates payload shape, delegates to the broker, and maps broker domain failures to typed command receipts. Do not place adapter selection or effect logic in command service.
- [ ] **Step 4:** Ensure `create_runtime()` owns ToolRegistry/ToolBroker and `capt_runtime_service.py` binds that exact instance to authenticated command services.
- [ ] **Step 5:** Add a negative test proving a caller cannot request an unregistered tool or a backend other than `local` in Slice A.
- [ ] **Step 6:** Run `python -m pytest tests/capt_runtime/test_tool_runtime_command.py tests/capt_runtime/test_desktop_m1_security.py -q`; expect PASS.
- [ ] **Step 7:** Commit `feat(tool): expose ToolBroker through authenticated runtime`.

---### Task 9: Slice-A falsification and release evidence

**Files:**
- Create: `tests/capt_runtime/test_tool_slice_a_acceptance.py`
- Create: `reports/tool-broker/SLICE_A_ACCEPTANCE.md`
- Create: `reports/tool-broker/SLICE_A_ACCEPTANCE.json`

**Interfaces:**
- Produces a machine-readable acceptance matrix; it is evidence, not VerificationResult authority.

- [ ] **Step 1: Add end-to-end tests against a real temporary repository**

```python
def test_slice_a_real_local_chain(runtime, tmp_path):
    # authenticated request -> ToolBroker -> real file write/read -> real Python -> durable settled ToolExecution
    write = run_governed_tool(runtime, tool="file.operations", operation="file.write", root=tmp_path, path=tmp_path/"marker.txt", content="CAPT")
    code = run_governed_tool(runtime, tool="code.execution", operation="code.execute_python", root=tmp_path, code="print(open('marker.txt').read())")
    assert write["status"] == "succeeded"
    assert "CAPT" in code["output"]["stdout"]
    assert runtime.store.verify_chain().startswith("sha256:")
```

- [ ] **Step 2: Add crash/restart disproof**

Persist a ToolExecution at `dispatching`, close the runtime, reopen the same ledger, call `reconcile_stranded()`, and assert it becomes `indeterminate` or adapter-proven settled without any second adapter execution.

- [ ] **Step 3: Run the Slice-A focused gate**

```bash
python -m pytest \
  tests/capt_runtime/test_tool_contracts.py \
  tests/capt_runtime/test_tool_registry.py \
  tests/capt_runtime/test_tool_execution.py \
  tests/capt_runtime/test_tool_broker.py \
  tests/capt_runtime/test_local_tool_backend.py \
  tests/capt_runtime/test_file_tool.py \
  tests/capt_runtime/test_code_execution_tool.py \
  tests/capt_runtime/test_tool_runtime_command.py \
  tests/capt_runtime/test_tool_slice_a_acceptance.py -q
```
Expected: all PASS.- [ ] **Step 4: Run normative contract and full Python gates**

```bash
python3 contracts/tools/check_drift.py
python -m pytest tests/capt_runtime -q
python -m pytest tests/ -q
```
Expected: drift PASS and zero test failures. Record exact pass/skip/deselect counts; do not copy historical counts.

- [ ] **Step 5: Run Swift regression/build gate**

```bash
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```
Expected: zero failures and successful product build. The four opt-in live tests may remain skipped only if their existing skip contract still applies.

- [ ] **Step 6: Run CAPT/Qwen adversarial review after implementation**

Use the installed governed CAPT runtime with `mtplx/qwen3.8-27b-mtplx` to inspect the exact branch diff for authority bypass, idempotency/recovery errors, scope escapes, subprocess leakage, and false release claims. Preserve returned mission/task/DriverRun IDs and `verificationId`; treat output as unverified review evidence until separately proven by tests/code inspection.

- [ ] **Step 7: Write acceptance evidence from observed commands only**

`SLICE_A_ACCEPTANCE.json` must include exact source SHA, commands, return codes, test counts, contract drift result, real local tool cases, negative cases, CAPT/Qwen review provenance, and explicit `verificationId` boundary. `SLICE_A_ACCEPTANCE.md` summarizes the same facts and limitations.

- [ ] **Step 8: Verify the branch diff**

```bash
git diff --check
git status --short
git log --oneline --decorate -12
```
Expected: diff check PASS; only intended evidence files may remain before the final evidence commit.

- [ ] **Step 9: Commit evidence**

```bash
git add reports/tool-broker tests/capt_runtime/test_tool_slice_a_acceptance.py
git commit -m "test(tool): prove ToolBroker Slice A acceptance"
```

- [ ] **Step 10: Push branch; do not merge**

```bash
git push origin feat/release-tool-broker-terminal-v1
```

## Plan Self-Review Checklist

- Spec coverage for Slice A: descriptor/readiness, capability/effect contracts, durable lifecycle, no-blind-replay recovery, Local process backend, File Operations, Code Execution, authenticated RuntimeService path, and evidence gate are each assigned to a task.
- Slice B/C/D work is not smuggled into Slice A; SSH, Docker, CDP, web/media/orchestration/native tool UI remain later plans.
- Every production-code task starts with an explicit failing test and RED observation.
- Interface names are consistent across tasks: `ToolRegistry`, `ToolExecutionAggregate`, `ToolBroker`, `LocalProcessBackend`, `FileToolAdapter`, `CodeExecutionAdapter`, and `run_tool`.
- No task authorizes direct adapter calls from a normal operator path.
- No environmental limitation is allowed to become a fabricated PASS.
- No TODO/TBD/placeholder implementation step is permitted.
