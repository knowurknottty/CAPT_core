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

The merged Textual TUI, CLI, and Tk operator MVP share the same operator/runtime boundary. The active PR #47 cockpit adds prompt-enhancement selection, response mode, requested context budget, human review, and cognitive provenance while preserving the same authority boundary.

## Cohorts

The active PR #48 Cohort layer coordinates bounded multi-perspective contributions. It is not a second runtime and currently does not claim durable RuntimeService/EventStore reconstruction, restart cursors, evidence admission, or installed-runtime TUI dogfood.

## Security gate

The active PR #49 SecurityGate evaluates evidence fail-closed. It does not grant capabilities or make its own result authoritative. Security evidence must still enter CAPT through normal governed evidence/verification paths.

For exact state classifications, use [`CURRENT_STATE.md`](CURRENT_STATE.md).