# 03 — Governed Execution Lifecycle

## One path, one authority

For provider work the implemented path is:

```text
capt tui / capt run
  → RuntimeClient authenticated Unix socket request
  → RuntimeCommandService.execute
  → RuntimeService-backed approved runner closure
  → mission + task + policy decision + capability grant
  → capability lease + reservation
  → DriverRun created/submitted/running/completed
  → ProviderDriver or HermesDriver
  → untrusted observation + candidate artifact
  → lease/reservation finalization
  → claim proposal + artifact-hash evidence
  → independent verification record
  → ClaimGuard decision
  → task terminalization + checkpoint + durable command receipt
```

Primary code:

```text
desktop/m1_command_service.py
 desktop/capt_runtime_service.py
 capt_runtime/services.py
 capt_runtime/store.py
 capt_runtime/composition.py
 capt_runtime/driver_host.py
 capt_runtime/drivers/provider.py
 capt_runtime/verification.py
```

## Admission and idempotency

Every command has a command ID, idempotency key, fingerprint, correlation ID, actor, and issued timestamp. `EventStore.claim_command()` makes SQLite the durable authority for command admission.

Rules:

- same key + same operation fingerprint: returns original durable receipt / current state; no second execution is authorized.
- same key + different fingerprint: idempotency conflict.
- persisted `in_progress`: is surfaced as `in_progress`, never cosmetically as accepted.
- durable receipts replace provisional in-progress admission on completion.
- process-local receipt maps are not lifecycle authority.
- SQLite busy timeout/retry and startup reconciliation support multi-process contention/restart behavior.

## CAPT state objects

| Object | Owner | Meaning |
|---|---|---|
| Mission | `MissionAggregate` | Operator objective, constraints, success/termination criteria |
| Task | `TaskAggregate` | Executable work unit and terminal/suspension state |
| PolicyDecision | Core service | Decision authorizing constrained work |
| CapabilityGrant | `CapabilityAggregate` | Granted authorized operations/scope |
| CapabilityLease | `CapabilityAggregate` | Time-bounded dispatch authority |
| Reservation/consumption | `CapabilityAggregate` | Exactly-once authority consumption/finalization |
| DriverRun | `DriverRunAggregate` | External-driver lifecycle/reconciliation state |
| Claim | `ClaimAggregate` | Proposed completion/assertion, not automatically truth |
| Evidence | Core event/evidence pipeline | CAPT-authoritative record about an artifact/observation |
| VerificationResult | verification plane | Support/contradiction status for a claim |
| ClaimGuardDecision | claim authority | Decision whether verified claim can be accepted |
| checkpoint | checkpoint manifest/event | Recovery boundary and ledger identity |

## Execution drivers

All drivers follow the `ExecutionDriver` protocol in `capt_runtime/drivers/__init__.py`:

```text
describe()
submit(work_order)
inspect(driver_run_id)
cancel(driver_run_id, reason)
resume(driver_run_id, resume_input)
reconcile(driver_run_id)
```

Drivers are untrusted. Their output is validated by `capt_runtime.ingestion`; they cannot create authoritative EventStore, Evidence, VerificationResult, or ClaimGuard state.

### ProviderDriver

`capt_runtime/drivers/provider.py` is a bounded driver selected only when the payload names a provider. It resolves the objective from authoritative `TaskResolver`, not a free driver-provided prompt field. It supports:

- `ollama`: native non-streaming `/api/generate`
- `openrouter`: OpenAI-compatible non-streaming `/chat/completions`
- provider model and base URL supplied from validated operator preference
- credential supplied only in memory from a secret reference
- artifact digest and safe diagnostics returned to the governed service

It does not resume an external provider run. Reconciliation returns `external_state_unknown`, forcing the higher-level conservative lifecycle.

### HermesDriver

`capt_runtime/drivers/hermes.py` launches Hermes as a bounded external ExecutionDriver. Its environment is allow-listed/minimized and credential-shaped variables are removed. Hermes retains its own provider configuration; CAPT does not claim it owns Hermes provider settings.

### OpenHarnessDriver

`capt_runtime/drivers/openharness.py` is the deterministic/reference driver path used for controlled runtime proof and tests.

## Leases and reservations

`capt_runtime/capability.py` verifies lease validity, scope, operation allowlist, time window, and operation mapping. A capability reservation is created before external dispatch. After a returned driver result, consumption finalizes before downstream verification. This matters: even if verification later contradicts/rejects a claim, external authority was consumed and cannot be casually replayed.

## Terminal and uncertain states

| Situation | DriverRun/Task handling |
|---|---|
| Proven no dispatch (`created`/`submitted` with ordering proof) | may fail without claiming external execution |
| running/suspended process lost after restart | DriverRun `lost`; Task `suspended` or indeterminate; reconciliation required |
| driver returns accepted result | DriverRun completed; reservation finalized; then evidence/verification proceeds |
| verification contradiction | negative verification persists; task fails; no ClaimGuard accept |
| governed cancel | `RuntimeService.cancel_task()` provides a Core-owned cancellation route |
| crash at test fault seam | state recovery reads EventStore and reconciles before accepting duplicates |

Never infer “provider probably did not run” from a missing local process. Treat uncertainty conservatively.

## Work order and ContextSlice

`contracts/schema/driver.schema.json` freezes the work-order/context-slice boundary. ContextSlice has `additionalProperties: false` and excludes governance, policy, claim, ledger, and aggregate references. `capt_runtime/context_slice.build_context_slice()` rejects over-disclosure. The authoritative task objective is resolved within CAPT composition; a driver only receives the bounded work order/context it is entitled to receive.

## Evidence semantics

```text
observed ≠ evidenced ≠ verified ≠ ClaimGuard accepted ≠ task complete
```

A provider response is observed/untrusted. CAPT can hash its produced artifact and record evidence. Verification independently checks artifact and repository invariants. ClaimGuard controls whether a bounded claim is accepted. Consult `capt evidence` after a run instead of promoting words in the output to fact.
