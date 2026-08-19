# CAPT Core Architecture

CAPT Core is local-first governed cognitive infrastructure around replaceable inference models. The architecture deliberately keeps durable responsibility outside a model session.

## Authority topology

```text
Human / application / compatibility client
              |
      CLI / TUI / desktop
              |
      shared Operator facade
              |
      authenticated local IPC
              v
        RuntimeService
              |
   +----------+-----------+----------------+
   |                      |                |
EventStore            Governance       Memory/context
ordered authority     grants/leases    durable memory
history               approvals        + ContextPack
   |                      |                |
   +---------- governed execution ----------+
              |
          DriverHost
              |
      bounded model/tool drivers
              |
      replaceable inference
```

No presentation surface, external model, Hermes client, Cohort coordinator, discovery scanner, prompt enhancer, or security checker becomes a parallel runtime.

## Durable layers

### EventStore

Authoritative ordered runtime history, replay, sequence identity, and integrity evidence.

### CTP

Operational transaction/recovery journal. CTP is useful for begin/validate/commit/abort/idempotency/receipt semantics, but it does not replace EventStore as runtime authority.

### CAPT Solo Memory Engine

Persistent local knowledge with provenance/metadata and local integrity/backup facilities.

### Runtime Memory Governor / ContextPack

Separate from durable storage. It owns context policy, token/budget accounting, bounded context construction/rotation, stale-state rejection, and dispatch gating.

### KHSB

In-process coordination. It is not currently durable, cross-process, or distributed.

## Governed execution

RuntimeService admits commands under explicit authority. DriverHost executes bounded external work. A completed driver call is an observation/artifact candidate, not automatic evidence acceptance, verification, task completion, or mission completion.

The active #46 lifecycle hardening strengthens durable idempotency, lease consumption, dispatch-boundary accounting, cancellation, and indeterminate-execution recovery. When dispatch status cannot be proven, the safe behavior is suspension/reconciliation rather than silent replay.

## Operator layer

`capt_ui.operator` is the shared projection/control abstraction used by the Textual TUI and desktop/operator surfaces. It may render state and submit governed requests; it does not write EventStore directly.

The merged TUI is an operator MVP. PR #47 adds prompt assembly/cognitive provenance and provider-run integration without changing the authority topology.

## Provider layer

Merged `main` contains provider registration, health/model discovery where supported, and model-selection foundations.

PR #47 adds a bounded ProviderDriver for Ollama native generation and OpenAI-compatible chat-completions transport. Exact head `4334657a919f74803e65d9b01aa5054d6d7b9a61` has clean source/editable full-suite verification, including the governed approval/dispatch path; intended live-provider and installed-runtime acceptance remain separate proof classes.

## Hermes boundary

Hermes is a compatibility/execution client, not CAPT authority. Historical v0.5 evidence established bounded installed-wheel behavior. Separately, operator-supplied LOCAL-002 metadata referenced `evidence/hermes-local-002-r6` / `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`, but Terra could not retrieve that branch, commit, or report from the current GitHub remote/API. `HERMES_LOCAL_002_COMPLETE` and its supplied workspace counts/no-blocker statement are therefore currently unverified and are not architectural evidence.

## Discovery

PR #44 adds read-only bounded discovery/SEAL scanning. Discovery may observe source/state; it does not grant capabilities or mutate authoritative runtime state.

## Cohorts

PR #48 defines bounded multi-perspective contribution/quorum/dissent coordination over CAPT authority. Current Cohort work does not yet claim durable reconstruction, restart-safe cursors, evidence admission, or installed-runtime TUI dogfood.

## SecurityGate

PR #49 turns security requirements into fail-closed infrastructure evidence. Its verdict is advisory/governance input, not a self-authorizing state transition. Applicable controls without evidence keep the gate blocked.

## Truth classes

Use precise terms:

```text
SOURCE_PRESENT
PACKAGED
OPERATOR_REACHABLE
EXECUTED
EVIDENCE_RECORDED
VERIFIED
CLAIM_ACCEPTED
TASK_COMPLETED
MISSION_COMPLETED
RELEASE_PROVEN
```

They are not interchangeable.

## Current state

See [`CURRENT_STATE.md`](CURRENT_STATE.md) for the exact package/main/integration/evidence split.