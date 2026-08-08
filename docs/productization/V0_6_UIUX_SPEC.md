# CAPT v0.6 UI/UX Productization Specification (UI-0 + UI-1)

**Status:** canonical implementation specification for the v0.6 UI/UX workstream
**Parent authority:** `docs/V0_6_PRODUCTIZATION_SOURCE_OF_TRUTH.md`,
`docs/V0_6_UI_UX_PRODUCTIZATION.md` (PR #39)
**Scope:** UI-0 (UX architecture + OSS survey) and UI-1 (unified provider layer)
**Decision:** design/planning only — no UI implementation in this document.

This document is the complete implementation specification. It is companion to
the OSS survey report (`docs/productization/UI0_OSS_SURVEY.md`) and the
wireframe/component kit (`docs/productization/UI_WIREFRAMES.md`).

---

## 0. Architecture invariant (non-negotiable)

> The UI is a **thin projection and control surface**. It is **not** a second
> runtime. All mutation and authority remain in CAPT RuntimeService and its
> governed command/query surfaces. No UI may fabricate authoritative state
> locally, and no UI may introduce a second authority path.

Audited facts the architecture must preserve (verified against the codebase):

- **RuntimeService** (`desktop/capt_runtime_service.py`) owns the authoritative
  runtime: EventStore, memory governor, evidence/verification, DriverHost,
  checkpoint/recovery, and the governed command/query IPC surface.
- **AuthN/AuthZ**: the runtime is reached over an authenticated local
  Unix-domain socket; each connection binds an operator and session identity.
  `desktop/desktop_runtime_client.py` (`RuntimeClient`) is the existing
  framework-agnostic client — it is the correct shared transport for every UI.
- **Command ops available today** (from `capabilities`): `create_mission`,
  `submit_approval_decision`, `cancel_task`, `cancel_driver_run`,
  `update_memory_trigger_policy`, `run_fixed_openharness_inspection`,
  `run_approved_hermes_inspection`, `checkpoint_runtime`, `shutdown`,
  `resume_runtime`.
- **Query ops available today**: `identity`, `capabilities`, `list_aggregates`,
  `get_state`, `get_stream_events`, `event_timeline`, `claimguard`,
  `verification`, `get_memory_policy`, `get_memory_state`.
- **Existing desktop client** (`desktop/desktop_app.py`) is a thin Tk GUI +
  headless projection over `RuntimeClient`. It already implements
  `project_mission_view`, `project_approval_queue`, `project_authoritative_state`,
  `project_cancellation_state`, memory-policy controls, trust-tagging, and
  untrusted-content sanitization. **This is the migration base, not a restart.**
- **Driver registry** (`capt_runtime/drivers/registry.py`) is the runtime's
  *execution-driver* registry (hermes, openharness). It is **not** a
  user-facing model-provider config. The UI-1 provider layer is a separate,
  higher-level abstraction for end-user model/provider selection.

---

## 1. Recommended UI architecture

### 1.1 Shape: three thin surfaces over one shared view-model

```text
       CLI (capt)          TUI (Textual)        Desktop (SwiftUI or Tk MVP)
          |                    |                       |
          +--------------------+-----------------------+   same concepts
                           |
                  Shared Operator View-Model / Contract
                       (capt_ui.operator.contract)
                           |
                  RuntimeClient (authenticated local IPC)
                           |
                   CAPT RuntimeService  <-- AUTHORITY
                    (EventStore, governance, memory,
                     evidence, verification, drivers)
```

Rules:

- **CLI, TUI, and Desktop consume the same operator view-model.** Only
  presentation differs. There is **no duplicated runtime logic** in any UI.
- The **shared contract** is a Python view-model layer
  (`capt_ui/operator/`) that wraps `RuntimeClient` and exposes a stable,
  human-typed set of read projections + governed command helpers. All three
  surfaces call it.
- Every mutation goes through a **governed command op** (`create_mission`,
  `submit_approval_decision`, `checkpoint_runtime`, ...). UI never writes the
  ledger directly.
- `capt start/status/stop/checkpoint/resume` (already shipped in P0) remain the
  lifecycle entry points; the TUI and Desktop reuse them under the hood.

### 1.2 The shared operator view-model (capt_ui/operator)

A new packages tree `capt_ui/` (presentation + view-model), with **no runtime
authority**:

```text
capt_ui/
  operator/
    contract.py      # typed operator state model + enums
    runtime.py       # thin facade over RuntimeClient (health, missions,...)
    providers.py     # provider registry facade (UI-1)
    verbosity.py     # CaveCAPT verbosity enum + resolution (UI-2)
    onramp.py        # first-run flow orchestration
  surfaces/
    cli/             # (thin) CLI extensions
    tui/             # Textual app
    desktop/         # desktop app
  wireframes/        # ASCII wireframes + screens
```

This mirrors the existing proven pattern in `desktop/` (thin client +
framework-agnostic view-model) and generalizes it so TUI and Desktop share it.

### 1.3 No hidden state

Every operator surface must render from the same authoritative projections:
runtime status, active mission, task state, approval queue, active
provider/model, context/token budget, memory-trigger state, checkpoint state,
evidence/verification state, EventStore timeline. A UI never holds a
"true" copy of these; it always re-derives from `RuntimeClient`.

---

## 2. Provider abstraction specification (UI-1)

### 2.1 Gap

There is **no user-facing provider configuration today**. `DriverHost` +
`DriverRegistry` (hermes, openharness) are bounded *execution* drivers, not
end-user model providers. UI-1 introduces one provider abstraction so a normal
user configures providers/models without seeing DriverHost internals.

### 2.2 Provider model

A **Provider** is a configured back-end for model inference or bounded
execution. A **Model** is a selectable inference entry point within a provider.

```text
Provider
  id            e.g. "openrouter", "ollama", "lmstudio", "llamacpp", "mlx",
                "vllm", "openai-*", "hermes"
  kind          LOCAL | CLOUD | HYBRID          (drives privacy UX)
  transport     openai_compatible | native | subprocess
  base_url      (endpoint) or local discovery rule
  api_key_ref   (key-id reference, NEVER the raw key in UI/logs/evidence)
  context_limit (safe context window)
  enabled
  auth_status   unknown | ok | missing           (health sub-field)

Model
  id, provider_id, name, context_size, capabilities
  parameters     (temperature, top_p, top_k, min_p, max_tokens, seed, reasoning)
  active scope   default | mission | temporary | per-workflow
Affinity/health
  reachable, authenticated, model_list_ok, latency_ms, last_success_at
```

### 2.3 Provider categories to support (UI-1 supported set)

| Provider | Transport | Discovery | Notes |
|---|---|---|---|
| OpenRouter | OpenAI-compatible REST | API key + `/models` | CLOUD |
| Ollama | OpenAI-compatible + native | local service + `/api/tags` | LOCAL |
| LM Studio | OpenAI-compatible | local service + `/v1/models` | LOCAL |
| llama.cpp-server | OpenAI-compatible | explicit endpoint | LOCAL |
| vLLM | OpenAI-compatible | explicit endpoint | LOCAL/HYBRID |
| MLX / mlx_lm | native/subprocess | enumerate installed | LOCAL |
| Hermes | subprocess (bounded driver) | present if Hermes available | LOCAL |

All OpenAI-compatible providers share one adapter; the base_url and auth differ.

### 2.4 User workflow (single, provider-agnostic)

```text
Settings -> Providers
  Provider:  [ LM Studio  v ]        # or Detect
  Endpoint:  http://localhost:1234/v1  [Detect]
  Status:    <Green/Yellow/Red>         "Connected"
  Models:    [ Qwen2.5-7B v ]          (populated from provider)
  Context:   32768
  Local/Cloud: [LOCAL]
  [Test connection]  [Use as active model]  [Save]
```

The equivalent CLI surface (from UI_UX doc):

```zsh
capt models providers
capt models discover
capt models list
capt models test <provider/model>
capt models use <provider/model>
```

### 2.5 Provider health (the Green/Yellow/Red contract)

Every provider exposes:

- **reachable** — endpoint/discovery answered;
- **authenticated** — credential valid (where applicable);
- **model list** — models enumerable;
- **context size** — known safe window;
- **capabilities** — what the provider/model supports;
- **latency** — last probe round-trip;
- **last successful call**.

Computed traffic-light:

| Signal | Meaning |
|---|---|
| GREEN | reachable + authenticated + models listed + a recent successful call |
| YELLOW | reachable but credential unverified or model list partial/absent |
| RED | unreachable, missing credential, or last call failed |

No log files required.

### 2.6 Model selection scopes

| Scope | Meaning |
|---|---|
| Default model | provider/model used unless overridden |
| Mission override | a mission pins a provider/model |
| Temporary override | ad-hoc for the current task only |
| Per-workflow override | a saved workflow pins a provider/model |

**The active model is always visible** in every surface (top bar / status line).

### 2.7 Privacy

- Never silently send prompts to a cloud provider when a local provider is
  selected.
- Clearly display **LOCAL** vs **CLOUD**.
- Before first cloud use, explain that prompts/context for inference leave the
  machine.
- API keys are stored by key-id reference; raw keys never appear in settings
  recall, logs, evidence, or exported diagnostics.

### 2.8 Persistence

Provider config persists under the CAPT home (see `capt_solo/core/config.py`
pattern: `~/.capt-solo` root; runtime `~/.capt` from P0). A
`providers.json` (or a small SQLite section) holds provider/model/scope
records. Wire protocols are never stored with secrets.

---

## 3. Shared operator contract (CLI/TUI/Desktop/common concepts)

The single contract both UIs and the CLI expose. Presentation differs only.

| Concept | CLI (P0) | TUI | Desktop |
|---|---|---|---|
| Runtime status | `capt status` | status panel | top-bar indicator |
| Start/Stop/Checkpoint/Resume | `capt start/stop/checkpoint/resume` | controls | controls |
| Health/Doctor | `capt doctor` | panel | settings/diagnostic |
| Memory | `capt memory store/search/list` | memory panel | memory panel |
| Evidence/Verification | `capt evidence` | evidence viewer | evidence button |
| Approvals | `capt harness command ...` (op) | approval panel | approval badge+modal |
| Provider/Model | `capt models ...` (UI-1) | model panel | provider settings |
| CaveCAPT verbosity | `--verbosity` flag + setting | setting | setting |
| Events/Ledger | `capt evidence`/raw | events tab | runtime inspector |

No UI duplicates runtime logic; all concepts resolve to the same commands/ops.

---

## 4. CaveCAPT verbosity specification (UI-2, designed here so UI-1 screens can honor it)

A stable operator-controlled setting affects **presentation/explanation only**.
It never weakens governance, evidence, policy, or verification.

| Mode | What the user sees |
|---|---|
| **Minimal** | final answer + essential operator prompts only (e.g. "Approve this? (y/n)") |
| **Normal** (default) | useful progress, decisions, approvals, important evidence summaries |
| **Detailed** | richer runtime explanation, memory/context actions, verification summaries |
| **Diagnostic** | engineering-level detail: IDs, policy/evidence/runtime diagnostics, EventStore, ClaimGuard, timing, structured traces |

Behavior:

- `--verbosity {minimal,normal,detailed,diagnostic}` on CLI; persistent setting
  in TUI/Desktop.
- The setting persists locally and is visible in every surface.
- If CaveCAPT currently conflates verbosity with internal reasoning/policy
  behavior, separate those concerns — verbosity is output only.

---

## 5. Remaining deliverables

See companion documents:

- `docs/productization/UI0_OSS_SURVEY.md` — D1 OSS comparison + recommendation.
- `docs/productization/UI0_OSS_CHAT_UI_FACTSHEETS.md` — detailed chat-UI factsheets.
- `docs/productization/UI0_OSS_TUI_EVAL.md` — detailed TUI framework evaluation.
- `docs/productization/UI_WIREFRAMES.md` — D4 settings, D5 dashboard, D6 TUI
  layout, D7 desktop layout wireframes.
- `docs/productization/ONBOARDING.md` — D9 first-run flow.
- `docs/productization/COMPONENT_INVENTORY.md` — D10 component inventory.
- `docs/productization/ROADMAP.md` — D11 roadmap, D12 acceptance, D13 migration.
