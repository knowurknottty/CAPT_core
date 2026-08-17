# CAPT Demos

These demos separate what is runnable on merged `main` from what remains an acceptance target.

## Demo 1 — Durable memory

```zsh
capt memory store "Demo: memory survives model sessions." --tag demo
capt memory search "survives model sessions"
```

**Shows:** persistent CAPT memory is not a model transcript.

## Demo 2 — Runtime lifecycle

```zsh
capt start
capt status
capt evidence
```

**Shows:** authenticated local runtime + inspectable authoritative state.

## Demo 3 — Checkpoint/restart/no-repeat continuation

```zsh
capt checkpoint --idempotency-key demo-cp
capt stop
capt start
capt resume --idempotency-key demo-resume
capt status
```

**Shows:** continuation is reconstructed from CAPT state.

## Demo 4 — Operator TUI

```zsh
capt-ui dashboard
```

Inspect runtime, mission, memory/context, providers/models, approvals, evidence, and logs. Approve/deny and lifecycle controls remain governed RuntimeService operations.

## Demo 5 — Evidence truth chain

```zsh
capt start --seed
capt --json evidence
```

Use the output to distinguish recorded evidence, verification result, ClaimGuard disposition, and authoritative mission/task state.

## Hermes local TUI/workspace evidence

The `HERMES_LOCAL_002_COMPLETE` branch/report is a focused integration evidence record rather than a normal-user demo. It records the faithful Hermes Agent TUI workspace state map and its 98/0/0 and 174/0/2 test results. See [`CURRENT_STATE.md`](CURRENT_STATE.md).

## Acceptance target — real provider execution

The active PR #47 path adds bounded Ollama/OpenAI-compatible inference transport and an upgraded TUI run surface. When the stack is merged and exact-head live-provider acceptance is available, a demo should exercise the actual provider rather than a synthetic provider/model name.

## Flagship acceptance target — true cross-model continuity

```text
Model A
 -> governed mission/work
 -> evidence persisted
 -> checkpoint
 -> Model A process exits

Model B
 -> attaches to same CAPT state
 -> reconstructs authorized context
 -> does not repeat completed work
 -> performs new governed work
 -> evidence -> verification -> claim/completion state
```

**Current status: not yet release-proven.**

A seeded deterministic mission, synthetic model IDs, or changing a provider label demonstrates pieces of the architecture but does not prove this full claim.