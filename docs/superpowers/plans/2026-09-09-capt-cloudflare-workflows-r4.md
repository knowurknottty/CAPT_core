# CAPT Cloudflare Workflows R4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add bounded Cloudflare Workflows orchestration to CAPT's free-native execution plane without moving authority or terminal truth into Cloudflare.

**Architecture:** Extend the existing Cloudflare free-tier router/ledger with a Workflow step budget, extend read-only resource provenance/adoption with Workflow resources, then add a typed existing-resource API bridge and orchestrator. CAPT precomputes instance identity for reconciliation and keeps `ARBITRARY_COMPUTE` unroutable.

**Tech Stack:** Python 3.12, dataclasses/enums, urllib, SQLite usage ledger, CAPT EventStore bindings, pytest, Ruff.

**Spec:** `docs/architecture/CAPT_BOT_CLOUDFLARE_WORKFLOWS_R4.md`

## Global Constraints

- RuntimeService + EventStore remain authoritative.
- Workflows is orchestration only; arbitrary compute remains unroutable.
- Sandbox and Containers remain dark.
- CAPT internal Workflow ceiling is 2,700 steps/day against provider 3,000/day.
- No Workflow create/update/delete/deploy methods.
- No live Workflow start/event/deployment during implementation.
- Every Workflow dispatch requires an adopted EventStore binding.
- Ambiguous external effects reconcile; they are never blind-retry permission.
- No raw provider secrets in config/evidence.
- Start params <= 32 KiB; event body <= 16 KiB.
- Step binary evidence reuses `CloudflareBinaryArtifactSpool`.

---

### Task 1: Free-tier Workflow quota and routing

**Files:**
- Modify: `capt_runtime/tools/backends/cloudflare_free_tier.py`
- Modify: `capt_runtime/tools/backends/cloudflare_free_router.py`
- Modify: `capt_runtime/tools/backends/cloudflare_usage.py`
- Test: `tests/capt_runtime/test_cloudflare_workflows_budget.py`

**Interfaces:**
- Produces `CloudflareSurface.WORKFLOWS`, `CloudflareWorkClass.DURABLE_ORCHESTRATION`, `CloudflareFreeEstimate.workflow_steps`, and `CloudflareUsageSnapshot.workflow_steps`.
- `CloudflareFreeTierEnvelope.require_workflow(steps, usage)` enforces the 2,700 CAPT ceiling.
- `ARBITRARY_COMPUTE` remains unroutable.

- [x] **Step 1: Write failing routing/budget tests**
  Test 2,700 admitted; 2,701 denied; durable orchestration routes to Workflows; arbitrary compute remains denied; concurrent reservations cannot double-spend the same remaining steps.
- [x] **Step 2: Run the Workflow budget test file and verify RED**
  Run: `/Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q tests/capt_runtime/test_cloudflare_workflows_budget.py`
  Expected: failures for missing enum/fields/method.
- [x] **Step 3: Implement the minimal quota/router/ledger fields**
  Keep the existing 10% headroom pattern and SQLite `BEGIN IMMEDIATE` admission recheck.
- [x] **Step 4: Rerun the test file and verify GREEN**
- [x] **Step 5: Run existing free-tier/router/usage tests for non-regression**

### Task 2: Read-only Workflow inventory and adoption compatibility

**Files:**
- Modify: `capt_runtime/tools/backends/cloudflare_resource_inventory.py`
- Modify: `capt_runtime/tools/backends/cloudflare_native_api.py`
- Test: `tests/capt_runtime/test_cloudflare_workflow_inventory.py`
- Test: `tests/capt_runtime/test_cloudflare_resource_adoption.py`

**Interfaces:**
- Adds `CloudflareResourceKind.WORKFLOW`.
- `parse_cloudflare_resource_inventory(..., workflow_rows=...)` accepts paginated Workflow rows.
- `CloudflareNativeAPIBridge.resource_inventory()` performs GET-only `/workflows` pagination.
- Existing `CloudflareResourceAdoptionProposal` supports Workflow with no endpoint.

- [x] **Step 1: Write failing inventory tests**
  Require exact UUID/name identity, complete pagination, duplicate detection, and `adopted=false`.
- [x] **Step 2: Run tests and verify RED**
- [x] **Step 3: Implement Workflow inventory parsing and API pagination**
  Do not add create/update/delete operations.
- [x] **Step 4: Add an adoption test proving Workflow proposal/approval/binding round-trip**
  `targetEndpoint` must remain `None`.
- [x] **Step 5: Run inventory/adoption tests and verify GREEN**

### Task 3: Typed Workflow API bridge

**Files:**
- Modify: `capt_runtime/tools/backends/cloudflare_native_api.py`
- Create: `capt_runtime/tools/backends/cloudflare_workflows.py`
- Test: `tests/capt_runtime/test_cloudflare_workflows_api.py`

**Interfaces:**
- `workflow_instance_id(account_id, workflow_resource_id, operation_id) -> str`
- Bridge methods:
  - `workflow_instance_start(operation_id, workflow, params, max_steps)`
  - `workflow_instance_status(workflow, instance_id)`
  - `workflow_instance_event(operation_id, workflow, instance_id, event_type, body)`
  - `workflow_instance_step_evidence(operation_id, workflow, instance_id)`
- Every method resolves `CloudflareResourceKind.WORKFLOW` via the binding registry before secret lookup.
- API layer contains no Workflow definition mutation methods.

- [x] **Step 1: Write failing identity and pre-dispatch binding tests**
  Assert deterministic `capt_` instance ID and zero network calls without a binding.
- [x] **Step 2: Write failing HTTP-shape tests**
  Verify exact GET/POST paths, explicit `instance_id`, bounded payloads, closed statuses, and event envelope operation ID.
- [x] **Step 3: Run and verify RED**
- [x] **Step 4: Implement minimal typed bridge methods**
  Normalize JSON step evidence; spool octet-stream step evidence through `CloudflareBinaryArtifactSpool`.
- [x] **Step 5: Run and verify GREEN**
- [x] **Step 6: Add malformed/oversized/identity-mismatch tests**
  All malformed pre-dispatch inputs must fail before secret/network access.

### Task 4: Governed Workflow orchestrator lifecycle

**Files:**
- Modify: `capt_runtime/tools/backends/cloudflare_native.py`
- Test: `tests/capt_runtime/test_cloudflare_workflows_orchestrator.py`

**Interfaces:**
- `CloudflareWorkflowOrchestrator.start(...) -> CloudflareWorkflowStartResult`
- `status(...) -> CloudflareWorkflowStatusResult`
- `event(...) -> CloudflareWorkflowEventResult`
- `step_evidence(...) -> CloudflareWorkflowStepEvidenceResult`
- Start uses planner reservation; releases only on `CloudflareDispatchNotStarted`; ambiguous dispatch raises `CloudflareWorkflowIndeterminate` and leaves reservation locked.

- [x] **Step 1: Write failing start lifecycle tests**
  Cover reserve/commit, proven-not-started release, post-dispatch indeterminate lock, and instance-ID mismatch.
- [x] **Step 2: Run and verify RED**
- [x] **Step 3: Implement minimal result types + orchestrator**
- [x] **Step 4: Add status/event/evidence tests**
  Provider status remains evidence only. Ambiguous event delivery is indeterminate and not retried.
- [x] **Step 5: Run and verify GREEN**

### Task 5: Runtime composition and architecture closure

**Files:**
- Modify: `capt_runtime/composition.py`
- Modify: `capt_runtime/tools/backends/cloudflare_native.py`
- Modify: `docs/architecture/CAPT_BOT_CLOUDFLARE_R3.md`
- Test: `tests/capt_runtime/test_cloudflare_native_composition.py`

**Interfaces:**
- `CloudflareNativeSurfaces.workflows: CloudflareWorkflowOrchestrator`
- `create_runtime()` injects the same planner, bridge, binding registry, and artifact spool already owned by the native Cloudflare runtime.

- [x] **Step 1: Write failing composition test**
  Verify Workflow surface exists only with native profile and shares the bridge/registry/planner.
- [x] **Step 2: Run and verify RED**
- [x] **Step 3: Wire runtime composition**
- [x] **Step 4: Update R3 architecture document to reference the R4 orchestration extension**
  Record Sandbox/Containers as paid-only/unavailable and Workflows as orchestration-only.
- [x] **Step 5: Run all Cloudflare tests**
- [x] **Step 6: Run targeted Ruff, contract drift, and `git diff --check`**
- [x] **Step 7: Run `tests/capt_runtime` through CAPT Node**
- [x] **Step 8: Run the full repository suite through CAPT Node**
  Reconcile by operation ID if the outer channel times out; do not duplicate.
- [x] **Step 9: Inspect exact diff/staged set and commit**
  Commit only after the exact verified tree is green.
