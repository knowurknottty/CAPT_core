# CAPT Core Architecture

CAPT Core is local-first governed cognitive infrastructure around replaceable inference models. Durable responsibility stays outside any transient model session.

## Authority topology

```text
Human / application / compatibility client
              |
   CLI / TUI / native macOS / MCP
              |
      shared Operator/control layer
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

No presentation surface, MCP client, external model, Hermes client, Cohort coordinator, discovery scanner, prompt enhancer, provider manager, or security checker becomes a parallel runtime.

## Terminal convergence architecture

PR #117 reconciles the formerly stacked runtime, provider, native, security, authored-skill, and UPG-001→019 lines into one candidate. This is semantic reconciliation rather than a mechanical mega-merge.

Key integrated properties:

- exact historical replay reconstructs the ledger prefix rather than seeding old state with present snapshots;
- governed replay forks create new history without reactivating historical approvals/capabilities;
- Cohorts own durable EventStore state, evidence admission, epoch/round semantics, and governed steering;
- artifact promotion has its own authoritative transaction rather than filesystem side effects pretending to be verification;
- capability leases remain bounded/revocable authority;
- authored skill bytes are verified and bound into the exact model-visible approval identity before one-use execution;
- provider/model changes are session-isolated in the native client;
- MCP and native macOS remain compatibility/control surfaces over the same RuntimeService/EventStore authority.

## Durable layers

### EventStore

Authoritative ordered runtime history, replay, sequence identity, stream versions, and integrity chain.

### CTP

Operational transaction/recovery journal; it does not replace EventStore authority.

### Durable memory / ContextPack

Durable knowledge storage and governed bounded model context are separate layers. Context selection/provenance is frozen at the approval/execution boundary where required.

### KHSB

In-process coordination and compatibility substrate. It remains non-authoritative; cross-process/distributed authority is not inferred from it.

### Cohorts

The convergence line includes durable Cohort persistence/reconstruction, evidence admission, governed steering, epoch handling, and Chamber projection. Cohort majority/quorum is not verification and cannot bypass RuntimeService authority.

## Governed execution

RuntimeService admits commands under explicit authority. DriverHost executes bounded external work. A provider/model result yields observations/artifact candidates and leaves verification/ClaimGuard/task completion distinct.

If CAPT cannot prove whether consequential external dispatch occurred, it does not blindly redispatch; the recovery path is lost/suspended/reconciliation-required as appropriate.

## Provider layer

The convergence provider spine includes Ollama plus local/authenticated OpenAI-compatible execution, endpoint provenance, resource ceilings, bounded prewarm, and coherent global/session provider selection. The generic direct native MLX placeholder is not represented as a working adapter unless materially configured.

## Native macOS layer

`CAPTNativeMac` is a real executable target, not merely a Swift contract package. It remains a thin RuntimeService client with typed projections, governed approvals, encrypted session-cache persistence, and session-isolated async configuration updates.

## Security layer

SecurityGate/Security Closure Cockpit is a fail-closed projection over the 47-control catalog. It does not self-authorize release and does not convert general test success into control evidence. Current release-security state remains blocked until exact-head evidence closes every applicable release-blocking control.

## Truth classes

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

See [`CURRENT_STATE.md`](CURRENT_STATE.md) for the exact protected-main / convergence-candidate / release-security split.
