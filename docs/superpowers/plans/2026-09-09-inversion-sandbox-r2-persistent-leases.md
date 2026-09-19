# InversionSandbox R2 Persistent Governed Leases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add expiring, crash-reconcilable persistent InversionSandbox resources while preserving CAPT's existing capability lease and ToolExecution authority boundaries.

**Architecture:** Introduce a durable `SandboxLeaseAggregate` for resource facts only. Extend the proven R1 Docker substrate with stopped-container and exact-identity lifecycle primitives, then route create/exec/close through typed sandbox-specific RuntimeService multi-stream transactions so SandboxLease, ToolExecution, and capability consumption settle atomically at the boundaries CAPT already owns.

**Tech Stack:** Python 3.12+, pytest, SQLite EventStore, Docker CLI/Engine, JSON Schema 2020-12, generated Python/TypeScript contracts, stdlib hashing/time/dataclasses.

**Spec:** `docs/superpowers/specs/2026-09-09-inversion-sandbox-r2-persistent-leases-design.md`

## Global Constraints

- Base commit: `e35635b74f24cfda6c60ee4904e57567ee8aa30b`; spec commit: `b39d5d2`.
- `SandboxLease` is resource lifetime only; unqualified `leaseId` remains capability authority.
- R1 one-shot `terminal.inversion_sandbox` and `terminal.docker` behavior remain unchanged.
- No implicit image pulls, privileged exec, root exec, Docker socket passthrough, mutable mounts, or mutable egress policy.
- No execd, Jupyter, PTY, credentials, snapshots, browser/VNC, Kubernetes, gVisor, Kata, or Firecracker in R2.
- Every external create/exec/close remains a separately governed ToolExecution with capability reservation/consumption.
- Unknown external state becomes `indeterminate`; no automatic replacement, adoption, retry, or fuzzy-name deletion.
- Persistent TTL defaults to 1800 seconds and operator-configurable profile maxima may not exceed 86400 seconds.

---

### Task 1: Add the SandboxLease contract and aggregate state machine

**Files:**
- Create: `contracts/schema/sandbox.schema.json`
- Modify: `contracts/schema/common.schema.json`
- Modify: `contracts/schema/index.json`
- Regenerate: `contracts/generated/python/capt_contracts/*`, `contracts/generated/typescript/src/*`
- Create: `capt_runtime/aggregates/sandbox_lease.py`
- Modify: `capt_runtime/aggregates/__init__.py`
- Create/Test: `tests/capt_runtime/test_sandbox_lease_aggregate.py`
- Modify/Test: `tests/capt_runtime/test_contracts.py`

**Interfaces:**
- Produces `SandboxLeaseAggregate.stream_id(sandbox_lease_id: str) -> str` using `sandbox_lease-<id>`.
- Produces `SandboxLeaseAggregate.reserve(record)`, `.record_created(state, patch)`, `.record_running(state, patch)`, `.begin_close(state, patch)`, `.record_closed(state, patch)`, `.mark_indeterminate(state, patch)`, `.reconcile(state, target_state, patch)`.
- Contract state enum: `reserved|created|running|closing|closed|indeterminate`.

- [ ] **Step 1: Write RED contract tests** asserting `StreamId` accepts `sandbox_lease-*`, `SandboxLease` rejects unqualified capability fields as authority, TTL >86400, missing immutable digests, illegal state values, and malformed Docker IDs.

```python
def test_sandbox_lease_contract_separates_resource_from_capability_authority():
    lease = sandbox_lease_fixture(state="reserved")
    lease["leaseId"] = "capability-lease-must-not-live-here"
    with pytest.raises(ContractViolation):
        require("SandboxLease", lease)
```

- [ ] **Step 2: Run the new contract/aggregate tests and verify RED.**

Run: `/Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q tests/capt_runtime/test_contracts.py tests/capt_runtime/test_sandbox_lease_aggregate.py`
Expected: failures for unknown `SandboxLease`, unsupported stream prefix, and missing aggregate implementation.

- [ ] **Step 3: Add the schema and aggregate with strict transitions.** `closed` is terminal; `indeterminate` may reconcile only to `running`, `closing`, or `closed`; `reserved -> closed` requires `closeReason=create_failed_no_effect`; no transition can change immutable object/profile/owner/daemon identities once bound.

```python
TRANSITIONS = {
    "reserved": {"created", "closed", "indeterminate"},
    "created": {"running", "closing", "indeterminate"},
    "running": {"closing", "indeterminate"},
    "closing": {"closed", "indeterminate"},
    "indeterminate": {"running", "closing", "closed"},
    "closed": set(),
}
```

- [ ] **Step 4: Regenerate contracts and check drift.**

Run: `/Users/knowurknot/CAPT_core/.venv/bin/python contracts/tools/generate.py && /Users/knowurknot/CAPT_core/.venv/bin/python contracts/tools/check_drift.py`
Expected: generated Python/TypeScript include `SandboxLease`; drift check exits 0.

- [ ] **Step 5: Re-run focused tests GREEN and commit.**

Commit: `feat(sandbox): add persistent lease aggregate`

### Task 2: Add authoritative RuntimeService lifecycle commands and atomic settlement

**Files:**
- Modify: `capt_runtime/authority.py`
- Modify: `capt_runtime/services.py`
- Create/Test: `tests/capt_runtime/test_sandbox_lease_service.py`
- Modify/Test: `tests/capt_runtime/test_authority.py`

**Interfaces:**
- Produces `RuntimeService.reserve_sandbox_lease(lease, metadata)`.
- Produces `RuntimeService.observe_sandbox_create_effect(tool_execution_id, sandbox_lease_id, side_effect_identity, created_patch, metadata)` that atomically advances ToolExecution `dispatching -> effect_observed` and SandboxLease `reserved -> created`.
- Produces `RuntimeService.settle_sandbox_create(grant_id, consumption, tool_execution_id, sandbox_lease_id, result, running_patch, metadata)` that atomically finalizes capability consumption, ToolExecution settlement/termination, and SandboxLease `created -> running` or `indeterminate`.
- Produces lifecycle commands `begin_sandbox_close`, `record_sandbox_closed`, `mark_sandbox_indeterminate`, and `reconcile_sandbox_lease`.

- [ ] **Step 1: Write RED authority tests** proving cognition/human/external-driver cannot author sandbox lifecycle transitions, while execution/system can; cleanup still requires a real capability-backed ToolExecution rather than a direct system mutation shortcut.

```python
@pytest.mark.parametrize("actor", [COGNITION, HUMAN, EXTERNAL_DRIVER])
def test_sandbox_lifecycle_mutation_rejects_wrong_authority(actor):
    with pytest.raises(AuthorityViolation):
        require_authority("transition_sandbox_lease", actor)
```

- [ ] **Step 2: Write RED service tests** for optimistic versioning, idempotent reserve, atomic created/effect-observed commit, atomic running/capability/ToolExecution settlement, and refusal to settle when ToolExecution IDs, capability lease IDs, or sandbox IDs disagree.

Run: `/Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q tests/capt_runtime/test_authority.py tests/capt_runtime/test_sandbox_lease_service.py`
Expected: FAIL because sandbox authority acts and service methods do not yet exist.

- [ ] **Step 3: Implement deny-by-default authority acts.** Add `reserve_sandbox_lease` and `transition_sandbox_lease` for execution/system only. Do not add a `cleanup_without_capability` act.

- [ ] **Step 4: Implement lifecycle event envelopes and multi-stream commits.** Use `AppendRequest` for SandboxLease + ToolExecution + CapabilityAggregate inside the same `_commit(...)` call at the logical settlement boundary; validate every current ID/state before constructing next states.

```python
return self._commit(
    [
        AppendRequest(cap_stream, CapabilityAggregate.KIND, cap_version, cap_event, cap_state),
        AppendRequest(tool_stream, ToolExecutionAggregate.KIND, tool_version, tool_event, tool_state),
        AppendRequest(sandbox_stream, SandboxLeaseAggregate.KIND, sandbox_version, sandbox_event, sandbox_state),
    ],
    metadata,
)
```

- [ ] **Step 5: Re-run authority/service tests GREEN plus `test_tool_execution.py` and `test_capability_service_idempotency.py` to prove no settlement regression.**

- [ ] **Step 6: Commit.**

Commit: `feat(sandbox): add durable lease lifecycle service`

### Task 3: Add persistent-capable profile fields and exact Docker lifecycle primitives

**Files:**
- Modify: `capt_runtime/tools/backends/docker.py`
- Modify: `capt_runtime/tools/backends/inversion_sandbox.py`
- Modify/Test: `tests/capt_runtime/test_docker_tool_backend.py`
- Create/Test: `tests/capt_runtime/test_inversion_sandbox_persistence_backend.py`

**Interfaces:**
- Extend `InversionSandboxProfile` with `persistent_entrypoint_argv: tuple[str, ...] | None = None`, `default_ttl_seconds: int = 1800`, `max_ttl_seconds: int = 1800`.
- Produce immutable `SandboxRuntimeIdentity` containing workload/guardian/network IDs, image IDs, daemon endpoint identity, digests, and attestation.
- Produce backend methods `create_persistent_stopped(...)`, `start_persistent(...)`, `inspect_persistent(...)`, `exec_persistent(...)`, and `close_persistent(...)`; these return evidence only and never touch EventStore.
- Existing `InversionSandboxProcessBackend.execute()` remains the R1 one-shot implementation and retains cleanup-always behavior.

- [ ] **Step 1: Write RED profile tests** proving persistence is opt-in, entrypoint argv cannot be empty, TTL is `[1, 86400]`, default TTL cannot exceed max TTL, and the persistent entrypoint contributes to the immutable profile digest.

```python
with pytest.raises(AuthorityViolation, match="TTL"):
    InversionSandboxProfile(..., persistent_entrypoint_argv=("/keeper",), max_ttl_seconds=86401)
```

- [ ] **Step 2: Write RED backend tests** proving persistent create leaves the workload stopped after attestation, labels exact lease/profile/policy digests, never enables generic cleanup-always, and rejects daemon/image/security drift before start.

- [ ] **Step 3: Add the smallest additive Docker primitives needed by the sandbox backend.** Keep them private/internal to the backend layer: exact stopped create, inspect, start, non-privileged exec with explicit `--user`, and remove-by-container-ID. Existing `DockerProcessBackend.execute()` must call the same helpers without changing its public behavior.

- [ ] **Step 4: Implement persistent R1-derived creation.** Reuse local-image/seccomp checks, stopped applied-state attestation, guardian construction, and internal-network topology. Add deterministic CAPT labels such as `capt.sandboxLeaseId`, `capt.profileDigest`, `capt.securityProfileDigest`, `capt.networkPolicyDigest`, and `capt.filesystemScopeDigest` before creation.

- [ ] **Step 5: Implement `exec_persistent`.** Require an already-proven `SandboxRuntimeIdentity`; invoke Docker exec with the profile numeric UID:GID, literal argv, explicit cwd/environment, output limits, and no privileged/detach flags. Return `termination_proven: bool`; a host timeout sets it false unless Docker/process evidence positively proves termination.

- [ ] **Step 6: Implement exact-ID close.** Remove workload, guardian, then internal network only after IDs/labels match the expected lease; absence may count as positive evidence only when inspect proves `not found` for that exact ID. Never delete by name prefix.

- [ ] **Step 7: Run focused backend tests GREEN and the existing R1 Docker/security/network suites.**

Run: `/Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q tests/capt_runtime/test_docker_tool_backend.py tests/capt_runtime/test_inversion_sandbox_security.py tests/capt_runtime/test_inversion_sandbox_network.py tests/capt_runtime/test_inversion_sandbox_persistence_backend.py`

- [ ] **Step 8: Commit.**

Commit: `feat(sandbox): add persistent docker lifecycle primitives`

### Task 4: Wire typed SandboxLease transactions through ToolBroker and lifecycle adapters

**Files:**
- Create: `capt_runtime/tools/sandbox_broker_hooks.py`
- Create: `capt_runtime/tools/adapters/inversion_sandbox_lifecycle.py`
- Modify: `capt_runtime/tool_broker.py`
- Modify: `capt_runtime/tools/builtins.py`
- Modify: `capt_runtime/tools/adapters/__init__.py`
- Modify: `capt_runtime/composition.py`
- Create/Test: `tests/capt_runtime/test_inversion_sandbox_lifecycle_tool.py`
- Modify/Test: `tests/capt_runtime/test_tool_broker.py`
- Modify/Test: `tests/capt_runtime/test_runtime_tool_wiring.py`

**Interfaces:**
- Add descriptor `SANDBOX_INVERSION_DESCRIPTOR` with operations `sandbox.create`, `sandbox.inspect`, `sandbox.close`; `inspect` is pure read-only, create/close are consequential.
- Define typed `SandboxBrokerHooks` protocol; hooks return schema-validated SandboxLease records/patches, never arbitrary aggregate maps.
- Lifecycle adapter owns request parsing/backend evidence only; ToolBroker remains the coordinator that invokes RuntimeService durable methods.

- [ ] **Step 1: Write RED broker tests** proving a create reserves capability first, then durably reserves SandboxLease before Docker mutation; effect observation commits ToolExecution + `reserved -> created` together; terminal settlement commits capability + ToolExecution + `created -> running` together.

- [ ] **Step 2: Write RED lifecycle adapter tests** for create/inspect/close argument validation, explicit profile/lease targeting, no cross-backend fallback, read-only inspect producing no side-effect identity, requested TTL capped by both profile `max_ttl_seconds` and the creating capability lease `validUntil`, close from `created`/`running`/`indeterminate`, repeated close returning the durable closure receipt without Docker mutation, and system cleanup succeeding only when backed by a dedicated `sandbox.close` cleanup CapabilityGrant/lease.

- [ ] **Step 3: Implement typed broker hooks.** The protocol exposes only sandbox-specific methods such as `reserve_sandbox_lease_record(...)`, `begin_sandbox_close_patch(...)`, `sandbox_created_patch(...)`, and `sandbox_terminal_patch(...)`; absence means ordinary ToolBroker behavior. Do not add a generic aggregate-participant payload channel.

- [ ] **Step 4: Modify ToolBroker at its existing boundaries.** After capability reservation but before `dispatching`, apply create reserve or close-begin through RuntimeService. Inside `observe_effect`, use `observe_sandbox_create_effect(...)` when a create hook is present; otherwise preserve the existing ToolExecution-only transition. At terminal settlement, route sandbox-aware outcomes through the matching RuntimeService multi-stream method.

- [ ] **Step 5: Implement lifecycle adapter operations.** `create` validates persistent-capable profile + requested TTL and computes `expiresAt = min(requested/profile bound, capabilityLease.validUntil)`; `inspect` loads durable state/read-only observation only; `close` targets exact lease IDs, supports `created|running|indeterminate`, returns the stored closure receipt idempotently for `closed`, and never performs discovery by name.

- [ ] **Step 6: Register lifecycle tool independently in `create_runtime()`.** `terminal.inversion_sandbox` remains separately registered; no implicit routing or substitution.

- [ ] **Step 7: Run broker/lifecycle/wiring tests GREEN.**

Run: `/Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q tests/capt_runtime/test_tool_broker.py tests/capt_runtime/test_inversion_sandbox_lifecycle_tool.py tests/capt_runtime/test_runtime_tool_wiring.py`

- [ ] **Step 8: Commit.**

Commit: `feat(sandbox): govern persistent lifecycle through tool broker`

### Task 5: Add persistent terminal exec with owner/TTL/identity revalidation

**Files:**
- Modify: `capt_runtime/tools/adapters/inversion_sandbox_terminal.py`
- Modify: `capt_runtime/tools/backends/inversion_sandbox.py`
- Modify: `capt_runtime/tool_broker.py`
- Create/Test: `tests/capt_runtime/test_inversion_sandbox_persistent_exec.py`
- Modify/Test: `tests/capt_runtime/test_inversion_sandbox_runtime.py`

**Interfaces:**
- `terminal.inversion_sandbox` accepts optional typed string argument `sandbox_lease_id`; absence retains the exact R1 path.
- Persistent path resolves the durable SandboxLease from EventStore and requires `running`, unexpired state, same operator/session, matching profile, and exact current Docker/guardian/network observation before dispatch.
- Persistent exec side-effect identity binds `sandboxLeaseId`, workload container ID, creation attestation digest, operation fingerprint, command digest, and fresh resource-observation digest.

- [ ] **Step 1: Write RED tests** for owner mismatch, session mismatch, expired lease, non-running lease, profile mismatch, replaced container/image, extra network attachment, guardian drift, root/privileged exec prevention, and absence of parent environment secrets.

- [ ] **Step 2: Write RED compatibility test** showing a request without `sandbox_lease_id` still invokes one-shot R1 creation/cleanup and produces the same evidence keys as before.

- [ ] **Step 3: Implement persistent request selection and live reinspection.** Never infer persistence from profile settings alone; only the explicit lease argument selects it. Load EventStore state through the adapter's injected read-only lease resolver and compare every immutable field before invoking backend exec.

- [ ] **Step 4: Implement timeout quarantine.** When backend exec returns `termination_proven=False`, adapter result is `indeterminate`; ToolBroker uses the sandbox terminal hook to atomically finalize capability/ToolExecution and mark the SandboxLease `indeterminate` with reason `exec_termination_unknown`. Further exec is denied.

- [ ] **Step 5: Preserve ordinary success/failure lifecycle.** A positively terminated command may succeed or fail without changing SandboxLease `running`; only the ToolExecution/capability pair settles.

- [ ] **Step 6: Re-run persistent exec tests plus R1 runtime/security/network tests GREEN.**

Run: `/Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q tests/capt_runtime/test_inversion_sandbox_persistent_exec.py tests/capt_runtime/test_inversion_sandbox_runtime.py tests/capt_runtime/test_inversion_sandbox_security.py tests/capt_runtime/test_inversion_sandbox_network.py`

- [ ] **Step 7: Commit.**

Commit: `feat(sandbox): add governed persistent exec`

### Task 6: Add startup reconciliation, expiry handling, and orphan reporting

**Files:**
- Create: `capt_runtime/sandbox_reconciliation.py`
- Modify: `capt_runtime/composition.py`
- Modify: `capt_runtime/services.py`
- Create/Test: `tests/capt_runtime/test_inversion_sandbox_reconciliation.py`
- Modify/Test: `tests/capt_runtime/test_runtime_tool_process_restart.py`

**Interfaces:**
- Produce `SandboxLeaseReconciler.reconcile_all() -> list[dict[str, Any]]` and `.reconcile_one(sandbox_lease_id) -> dict[str, Any]`.
- `RuntimeComposition.reconcile_sandbox_leases()` exposes the reconciler; `create_runtime()` invokes non-destructive startup reconciliation after sandbox backend construction.
- Reconciliation starts from EventStore non-closed leases; Docker inventory is used only to locate objects labeled with an already-durable lease ID when exact IDs were not yet committed during a create crash.
- Orphan CAPT-labeled objects with no matching aggregate are reported as `orphan` evidence only in R2.

- [ ] **Step 1: Write RED restart tests** covering crashes at `reserved`, `created`, `running`, `closing`, and `indeterminate`; exact matching resources may advance truth, but missing/replaced/mutated resources never trigger recreation or adoption.

- [ ] **Step 2: Write RED expiry tests** proving expired running leases deny exec immediately and reconcile toward cleanup eligibility without extending TTL. No background scheduler is required for correctness.

- [ ] **Step 3: Implement exact-identity reconciliation.** Verify image/container/daemon/profile/security/filesystem/network/guardian labels and live state. A lease with `reconciliationReason=exec_termination_unknown` stays `indeterminate` unless positive termination evidence exists; R2 may conservatively require close when such evidence is unavailable.

- [ ] **Step 4: Implement create-crash discovery by durable lease label.** Search only for `capt.sandboxLeaseId=<known-id>` and require exactly one complete matching object set before recording identities; zero, multiple, or mismatched candidates remain `indeterminate`.

- [ ] **Step 5: Implement orphan reporting without mutation.** Inventory CAPT sandbox labels, subtract EventStore-known lease IDs, and return bounded evidence records. Do not delete or adopt them automatically.

- [ ] **Step 6: Wire startup reconciliation and explicit composition method.** Startup must not throw away the runtime because Docker is unavailable; instead preserve durable leases and record/report unproven reconciliation state fail-closed.

- [ ] **Step 7: Run reconciliation/restart tests GREEN.**

Run: `/Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q tests/capt_runtime/test_inversion_sandbox_reconciliation.py tests/capt_runtime/test_runtime_tool_process_restart.py tests/capt_runtime/test_composition.py`

- [ ] **Step 8: Commit.**

Commit: `feat(sandbox): reconcile persistent leases after restart`

### Task 7: Real-Docker adversarial acceptance and full repository gate

**Files:**
- Create/Test: `tests/capt_runtime/test_inversion_sandbox_persistent_real_docker.py`
- Modify: `docs/superpowers/specs/2026-09-09-inversion-sandbox-r2-persistent-leases-design.md` only if real evidence forces a contract correction
- Create: `docs/superpowers/verification/2026-09-09-inversion-sandbox-r2.md`

**Interfaces:**
- Real tests use already-local immutable images only through `CAPT_DOCKER_TEST_IMAGE` and `CAPT_INVERSION_GUARDIAN_IMAGE`; no test may pull.
- The final verification note records exact image IDs/digests, test counts, skips, crash points exercised, and any deliberately conservative reconciliation cases.

- [ ] **Step 1: Write real-Docker create/exec/close acceptance** proving the container remains running across two separately governed execs, tmpfs state persists between them, each command has a distinct ToolExecution/capability consumption, and close proves exact object absence.

- [ ] **Step 2: Add adversarial ownership/authority cases** for revoked capability, expired TTL, wrong operator/session, profile mismatch, root/privileged exec attempts, parent-secret noninheritance, dedicated platform-cleanup grant enforcement, live network-policy widening attempts, and proof that close removes container tmpfs but does not delete authorized host bind-mount contents.

- [ ] **Step 3: Add crash/uncertainty cases** for crash after stopped create before `created`, crash after `created` before keeper start, crash during close, container replacement, guardian replacement, extra network attachment, and exec timeout with unknown termination quarantining the lease.

- [ ] **Step 4: Run focused R2 suites with local images only.**

Run:
```bash
CAPT_DOCKER_TEST_IMAGE=python:3.13-slim CAPT_INVERSION_GUARDIAN_IMAGE=python:3.13-slim \
/Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q \
  tests/capt_runtime/test_sandbox_lease_aggregate.py \
  tests/capt_runtime/test_sandbox_lease_service.py \
  tests/capt_runtime/test_inversion_sandbox_persistence_backend.py \
  tests/capt_runtime/test_inversion_sandbox_lifecycle_tool.py \
  tests/capt_runtime/test_inversion_sandbox_persistent_exec.py \
  tests/capt_runtime/test_inversion_sandbox_reconciliation.py \
  tests/capt_runtime/test_inversion_sandbox_persistent_real_docker.py
```
Expected: all enabled R2 tests pass; any skip must name a genuinely missing local prerequisite.

- [ ] **Step 5: Run R1/non-regression suites.**

Run: `/Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q tests/capt_runtime/test_docker_tool_backend.py tests/capt_runtime/test_inversion_sandbox_security.py tests/capt_runtime/test_inversion_sandbox_runtime.py tests/capt_runtime/test_inversion_sandbox_network.py tests/capt_runtime/test_inversion_sandbox_real_docker.py tests/capt_runtime/test_tool_broker.py tests/capt_runtime/test_tool_execution.py`

- [ ] **Step 6: Run contract generation/drift and hygiene.**

Run:
```bash
/Users/knowurknot/CAPT_core/.venv/bin/python contracts/tools/generate.py
/Users/knowurknot/CAPT_core/.venv/bin/python contracts/tools/check_drift.py
git diff --check
```
Then run Ruff only on changed Python files and compare diagnostics against base `e35635b`; R2 may add zero new Ruff debt.

- [ ] **Step 7: Run the complete repository suite from the project venv.**

Run: `CAPT_DOCKER_TEST_IMAGE=python:3.13-slim CAPT_INVERSION_GUARDIAN_IMAGE=python:3.13-slim /Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q -rs`
Expected: zero failures; skips must be enumerated and classified.

- [ ] **Step 8: Prove no leaked R2 resources.** Check for CAPT sandbox containers/guardians/internal networks by exact labels/names and require none from completed tests. Do not touch unrelated host containers.

- [ ] **Step 9: Record verification evidence and commit.**

Commit: `test(sandbox): prove persistent governed lease boundary`

## Execution Order

Tasks 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 are sequential because each task consumes typed interfaces and authority guarantees created by the previous gate. Do not parallelize implementation across these boundaries. Independent RED test authoring inside one task may be parallelized only after the task's consumed interfaces are fixed.