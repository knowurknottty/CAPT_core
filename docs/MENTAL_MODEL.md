# Mental Model — How CAPT Works

The shortest correct model is:

> **Inference is replaceable; CAPT continuity is durable.**

```text
Human / operator
      |
      +--> capt CLI
      +--> Textual TUI
      +--> desktop / compatibility client
      |
      v
Authenticated RuntimeService
      |
      +--> Governance / capability / lease boundaries
      +--> EventStore authoritative runtime history
      +--> Memory + Runtime Memory Governor + ContextPack
      +--> Evidence -> Verification -> ClaimGuard
      +--> Checkpoint / replay / recovery / idempotency
      +--> DriverHost -> bounded drivers
                        |
                        v
                 Replaceable models
```

## What owns what

| Concern | Owner |
|---|---|
| authoritative runtime transitions | RuntimeService |
| ordered durable runtime history | EventStore |
| persistent local knowledge | CAPT Solo Memory Engine |
| working-context policy | Runtime Memory Governor / ContextPack |
| operational transaction/recovery journaling | CTP |
| in-process coordination | KHSB |
| external execution | DriverHost + bounded drivers |
| presentation/operator intent | CLI / TUI / desktop |
| claim support discipline | evidence + verification + ClaimGuard |

## Important non-equivalences

Do not collapse these states:

```text
source exists
!= packaged
!= operator reachable
!= executed
!= recorded as evidence
!= verified
!= claim accepted
!= task complete
!= mission complete
!= release proven
```

That distinction is central to CAPT.

## Model relationship

Models may reason, generate, inspect, summarize, or propose actions. Their output remains input to the governed system. A model response does not mint capability, write authoritative state, or verify itself merely by sounding confident.

## Operator surfaces

The Textual TUI, CLI, Tk operator surface, native `CAPTNativeMac`, and MCP compatibility client all preserve the same operator/runtime boundary. Merged PR #117 and later native/TUI golden authority work provide cockpit/provider/provenance and governed Settings/Skills/scope controls without creating a second authority plane. The semantic operator-control API coordinates revisioned configuration and prompt review; read projections expose runtime state. Native model-answer text and execution receipts remain separate.

## Cohorts

The merged Cohort layer includes durable EventStore persistence/reconstruction, evidence admission, governed steering, epoch handling, and Chamber projection. It is still not a second runtime; quorum or consensus cannot manufacture verification or capability.

Model Council alpha adds durable Council state, launch contracts, deterministic claim analysis, and Chamber projection. Neither Council consensus nor declared topology proves verification, live-provider quality, or achieved concurrency.

Prompt intelligence produces reviewable proposals; it cannot authorize its own execution. `context_pipeline` and `context_merkle` remain unshipped experiments/design paths, not live context authority.

## Security gate

The merged SecurityGate/Security Closure Cockpit evaluates the 47-control catalog fail-closed. It does not grant capabilities or self-authorize release; release authorization requires applicable exact-head evidence; historical receipts do not authorize the current HEAD.

For exact state classifications, use [`CURRENT_STATE.md`](CURRENT_STATE.md).
