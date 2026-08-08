# CAPT UI Wireframes (UI-0 spec)

Surfaces: Settings (D4), Runtime Dashboard (D5), TUI layout (D6), Desktop
layout (D7). These are ASCII wireframes for the shared operator view-model.
Presentation is intentionally framework-agnostic; the TUI and Desktop render
the same concepts.

---

## 1. Settings screen (D4) — Provider / Model

Primary: Settings → Providers.

```text
+------------------------------------------------------------------+
|  CAPT Settings                                            [Save] |
+-----------------------------+------------------------------------+
| General                     | Provider: [ LM Studio        v ]  |
|   CaveCAPT verbosity        | Kind:     [LOCAL]                 |
|   [Minimal|Normal|Detailed  | Endpoint: [http://localhost:1234/v1]
|    |Diagnostic]             |   [Detect]  [Test connection]     |
| Providers / Models          |-----------------------------------|
|   - Provider list [edit]    | Status:  [GREEN] Connected        |
|   - Active model            | Context: 32768  Latency: 42ms     |
| Appearance                  | Auth:    ok                       |
|   - Theme  [System]         |-----------------------------------|
|   - Font size []            | Models (from provider):           |
| Runtime                     |  ( ) Qwen2.5-7B-Instruct  32768  |
|   - State dir (expert)      |  ( ) llama3.2-3b         8192    |
|   - Socket/token (expert)   |-----------------------------------|
|                             | Advanced (progressive disclosure) |
|                             |  temperature [0.7]  top_p [1.0]   |
+-----------------------------+------------------------------------+
```

Key behaviors:

- **Detect** auto-fills endpoint for known local providers.
- **[Test connection]** runs provider health (reachable/auth/models/context/
  latency) and shows the traffic light.
- **[Use as active model]** sets the default model scope.
- **LOCAL/CLOUD** badge is always visible (privacy UX).
- Expert fields (state dir, socket/token) behind progressive disclosure, never
  required for ordinary use.

### General / verbosity summary

```text
CaveCAPT verbosity ........... [ Minimal | (Normal) | Detailed | Diagnostic ]
```

Persisted, visible in every surface.

---

## 2. Runtime dashboard (D5)

```text
+------------------------------------------------------------------+
| CAPT | Runtime: HEALTHY | Model: Qwen2.5-7B [LOCAL] | 18k/32k ctxt |
+----------------------+-------------------------------------------+
| Missions             |  Runtime Dashboard                        |
| + New mission        |  Status         HEALTHY (green)           |
| Project A  [RUNNING] |  Active model   Qwen2.5-7B [LOCAL]        |
| Project B  [IDLE]    |  Mission        Project A - "summarize"   |
|                      |  Task state     executing (2/5)           |
|                      |  Context budget 18,432 / 32,768 tokens    |
|                      |  Memory         active | next trigger 120 |
|                      |  Checkpoint     available (cp-3e02…)      |
|                      |  Evidence       3 artifacts | verified    |
|                      |  Verification   verified @ 15:03:39Z      |
|                      |  Approval queue 1 pending  (approve/deny) |
|                      |  Provider       LM Studio - Connected     |
|                      |  Ledger head    00142 | chain digest ✓    |
|  Memory | Evidence | Runtime | Approvals | Settings             |
+------------------------------------------------------------------+
| [Checkpoint] [Resume] [Stop] [Cancel current]    CaveCAPT[Det]  |
+------------------------------------------------------------------+
```

### No hidden state

Every field is a projection of authoritative runtime state via `RuntimeClient`
(`identity`, `list_aggregates`, `get_state`, `event_timeline`, `verification`,
`get_memory_policy`, `get_memory_state`, approval queue). The dashboard never
holds a local "true" copy.

---

## 3. TUI layout (D6)

Textual-based, keyboard-first, SSH-friendly.

```text
┌ CAPT ──────────────────────────────────────────────────────────┐
│ Runtime: ●HEALTHY  Model: Qwen2.5-7B[LOCAL]  18k/32k   ← tabs  │
├────────┬──────────────────────────────────────┬───────────────┤
│ Models │  Chat / Mission                      │ Runtime       │
│ ●Qwen  │                                     │ Status HEALTHY │
│ llama3 │  user> summarize the repo           │ Mission A...   │
│        │  capt> [doing..]                    │ Context 18k    │
│        │       evidence recorded ✓           │ Memory active  │
├────────┼──────────────────────────────────────┼───────────────┤
│ Mission│  [approval] approve? y/n            │ Evid 3|verify ✓│
│ A [●]  │  ─────────────────────────────────  │ Checkpoint ✓   │
│ B [ ]  │  input:  ………………  [enter]           │ Approvals 1    │
└────────┴──────────────────────────────────────┴───────────────┘
  F1 Help  F5 Memory F6 Evidence F7 Events  Ctrl-C cancel
```

Keyboard-first: full key mapping for mission select, approvals, provider/model
switch, memory/evidence/events panels, checkpoint/resume/cancel, verbosity.
Mouse optional. Works over SSH (no GUI dependency).

---

## 4. Desktop layout (D7)

ChatGPT-familiar shell, CAPT-native progressive disclosure. macOS-first.

```text
+------------------------------------------------------------------+
| CAPT | ● Runtime Healthy | Model: Qwen2.5-7B [LOCAL] | 18k/32k  |
+----------------------+-------------------------------------------+
| Sessions / Missions  |  Conversation / mission transcript        |
|  + New mission       |  user>  …                                |
|  Project A   ●       |  capt>  …                                |
|  Project B           |         [evidence]  [why complete?]      |
| ─────────────────    |                                          |
| Memory   [3 pinned]  |                                          |
| Evidence [verified]  |                                          |
| Runtime  [detail]    |                                          |
| Approvals[1]         |                                          |
+----------------------+-------------------------------------------+
| [Checkpoint][Resume][Stop]      CaveCAPT: Normal [v]  | Send >  |
+------------------------------------------------------------------+
```

Desktop specifics:

- Native shell per stack decision (see OSS survey + roadmap). The thin Tk MVP
  already exists and satisfies v0.6; a SwiftUI thin client is the macOS upgrade
  path.
- Sidebar: sessions/missions, memory, evidence, runtime, approvals.
- Approval flow is a modal/badge: requested capability, operation, scope, risk,
  reason, `[Approve] [Deny] [note]`.
- Streaming state distinguishes model output from CAPT status/evidence.
- Full keyboard navigation, readable contrast, scalable text, reduced-motion,
  no color-only status (traffic light has a text label).

---

## 5. Shared status / affordance tokens

| Token | Meaning | Render |
|---|---|---|
| Runtime healthy | identity.integrity == ok | green + "HEALTHY" |
| Provider reachable | health probe | green/yellow/red + label |
| Approval pending | approval queue non-empty | badge + label |
| Evidence verified | verification status | ✓ verified |
| Context budget | tokens used / limit | progress + "18k/32k" |
| Checkpoint | checkpoint available | ✓ available |
