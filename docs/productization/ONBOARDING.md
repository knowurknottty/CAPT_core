# CAPT First-Run Onboarding Flow (D9)

Goal: a first-time technically capable user goes from fresh install to their
first governed mission + evidence, **without reading architecture docs or asking
the author**. No documentation required during first run.

## The flow

```text
Welcome
  -> Choose provider (Local or Cloud)
  -> Test connection
  -> Choose model
  -> Health check
  -> Store first memory
  -> Run demo mission
  -> Checkpoint
  -> Resume
  -> Inspect evidence
  -> Done
```

## Screen-by-screen

### 1. Welcome

```text
Welcome to CAPT
"Your AI runtime keeps its memory, decisions, and proof —
  the model is just the engine."

[Continue]
```
One- or two-sentence CAPT explanation. No architecture nouns.

### 2. Choose provider

```text
Choose how CAPT runs models
( ) Local  — LM Studio  [Detected · Connected]
( ) Local  — Ollama     [Detected · Connected]
( ) Local  — llama.cpp  [Configure endpoint]
( ) Cloud  — OpenRouter [add API key]
( ) Later  — I'll decide later (use demo mode)

[Back]  [Continue]
```
Local providers auto-detected (`/v1/models`, `/api/tags`). Cloud requires an
API key. "Later" allows a no-model path (seeded demo mission).

### 3. Test connection

Runs provider health (reachable/auth/models/context/latency) → traffic light
+ text. If RED, show one-line remediation + retry.

### 4. Choose model

```text
Active model:  [ Qwen2.5-7B-Instruct  v ]   [LOCAL]
Context: 32768    [Use this model]
```

### 5. Health check

```text
CAPT runtime:       HEALTHY (green)
Provider:           Connected (green)
Model:              Qwen2.5-7B [LOCAL]
Memory:             ready
[Continue]
```

### 6. Store first memory

Pre-filled, editable:

```text
Store a memory:
[ CAPT keeps durable state outside the model.            ]
[Store & Continue]
```

### 7. Run demo mission

```text
Run a quick mission to see CAPT govern work:
  "Inspect this repository read-only and summarize it."
[Run]      (requires approval)
Approval:  Approve this read-only inspection?  [Approve]
```
Progress shown; model output vs CAPT status distinguished.

### 8. Checkpoint

```text
Checkpoint saved. (cp-…)
[Continue]
```

### 9. Resume

```text
Restart simulation: runtime state resumed from checkpoint.
No completed work repeated.   [Continue]
```

### 10. Inspect evidence

```text
Why is this complete?
  Claim    -> Evidence (3 artifacts)
  -> Verification: verified
  -> ClaimGuard: accepted
  -> EventStore: 14 events
[Show evidence]  [Done]
```

### 11. Done

```text
You're ready.
You can: start a mission, switch models, review evidence, change verbosity.
[Open CAPT]
```

## First-run requirements

- All steps use **supported command/query interfaces** — no raw JSON, no
  driver/socket knowledge.
- "Later / demo mode" must be a first-class option so hardware without a model
  never dead-ends.
- Every failure offers a recommended next action and a retry.
- The flow can be re-run from Settings → Onboarding without losing state.
