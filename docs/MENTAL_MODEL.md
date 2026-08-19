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

The Textual TUI, CLI, Tk operator surface, native `CAPTNativeMac`, and MCP compatibility client all preserve the same operator/runtime boundary. Terminal PR #117 reconciles the cockpit/provider/provenance projections without creating a second authority plane.

## Cohorts

The terminal convergence Cohort layer now includes durable EventStore persistence/reconstruction, evidence admission, governed steering, epoch handling, and Chamber projection. It is still not a second runtime; quorum or consensus cannot manufacture verification or capability.

## Security gate

The terminal convergence SecurityGate/Security Closure Cockpit evaluates the 47-control catalog fail-closed. It does not grant capabilities or self-authorize release; current release-security status remains BLOCKED until applicable exact-head evidence closes.

For exact state classifications, use [`CURRENT_STATE.md`](CURRENT_STATE.md).