# CAPT UI Roadmap, Acceptance, and Migration (D11–D13)

## D11 — Implementation roadmap (UI-0 … UI-5)

Ordering follows `docs/V0_6_UI_UX_PRODUCTIZATION.md` §19 and minimizes
engineering effort by standing on the existing desktop client and the P0 CLI.

### UI-0 — UX architecture + OSS survey (this sprint)

- Audit `desktop/` (done — thin Tk client + RuntimeClient is the base).
- Define shared operator view-model (`capt_ui/operator`) and supported
  command/query contract.
- OSS chat UI / TUI survey + license review (see
  `docs/productization/UI0_OSS_SURVEY.md`).
- Choose native desktop stack and TUI framework (recommendation in survey).
- Wireframes (see `docs/productization/UI_WIREFRAMES.md`).

### UI-1 — Model/provider configuration core

- Provider registry + config model (Provider/Model/scope records) under CAPT
  home.
- `discover` / `list` / `test` / `use` operations.
- Provider health (reachable/auth/models/context/latency) → traffic light.
- Local vs Cloud labeling; key-id reference storage.
- Settings persistence.
- **Delivery:** `capt models providers|discover|list|test|use` (CLI) +
  provider settings screen (TUI/Desktop).

### UI-2 — CaveCAPT verbosity preference

- Stable verbosity enum (`minimal|normal|detailed|diagnostic`), persist setting.
- Wire presentation behavior; separate verbosity from policy/reasoning.
- Controls in CLI (`--verbosity`), TUI, Desktop.

### UI-3 — TUI MVP (Textual)

- Runtime state, chat/task input, model selector, approvals, memory/context,
  evidence, checkpoint/stop/resume.
- Keyboard-first, SSH-friendly, reuses `capt_ui/operator` + `RuntimeClient`.

### UI-4 — Native desktop MVP

- ChatGPT-familiar shell (from P0 base / stack decision).
- Mission/session sidebar, provider/model selector, verbosity control,
  approvals, runtime/memory/evidence panels, checkpoint/cancel/resume,
  first-run provider setup.

### UI-5 — Independent usability test

- Give a new technically capable user only the shipped app + docs; measure
  completion of the v0.6 UI acceptance gate (D12) without author assistance.

## D12 — Acceptance criteria

Maps to `docs/V0_6_UI_UX_PRODUCTIZATION.md` §18 v0.6 UI acceptance.

A first-time technically capable user can, **without terminal-only knowledge or
author assistance**:

1. launch CAPT via desktop or TUI;
2. see whether runtime is healthy;
3. select/configure a supported model provider;
4. select a model;
5. set CaveCAPT verbosity;
6. submit a governed task;
7. respond to an approval request;
8. observe model/runtime progress;
9. inspect context/memory status;
10. checkpoint / cancel / resume;
11. inspect evidence/verification;
12. recover from common provider/runtime failures using surfaced guidance.

**Demo requirement:** at least one TUI path and one desktop path must be
demonstrated end-to-end against the real RuntimeService.

**Non-goal for this sprint:** the full v0.6 *release* gate (which also requires
a governed real-model mission and the cross-model continuity proof) is broader
than the UI gate; the UI acceptance is satisfied independently.

## D13 — Migration strategy from the current desktop client

The current `desktop/desktop_app.py` is a **thin Tk GUI + headless projection**
over `RuntimeClient`. It is not a dead-end; it is the reference for the shared
view-model and a working v0.6 Tk desktop MVP. Strategy:

### Keep (reuse as-is)

- `desktop/desktop_runtime_client.py` — the shared authenticated transport and
  projection functions (`project_mission_view`, `project_approval_queue`,
  `project_authoritative_state`, `project_cancellation_state`).
- `desktop/capt_runtime_service.py` — authority; untouched.
- `sanitize_for_display`, `trust_tag`, `render_m1_text` — proven rendering/
  anti-spoof helpers.
- Governed operator methods (`create_mission`, `submit_approval_decision`,
  `cancel_*`, memory-policy controls, checkpoint/resume/stop).

### Generalize (move into `capt_ui/operator`)

Lift the framework-agnostic projection/command helpers out of the Tk-bound
`DesktopApp` into a shared view-model so TUI and Desktop both consume them. The
`DesktopApp` GUI handler logic (`gui_*`) becomes a thin adapter over the shared
view-model.

### Add (new, thin)

- `capt_ui/operator/providers.py` (UI-1) — provider abstraction on top of
  `RuntimeClient` (health, discovery, model list, active scope).
- `capt_ui/operator/verbosity.py` (UI-2).
- `capt_ui/surfaces/tui/` (Textual) and `capt_ui/surfaces/desktop/`.

### Phase the desktop surface

| Phase | Result |
|---|---|
| Now | Current Tk `desktop_app.py` = v0.6 desktop MVP (already runs headless + GUI) |
| UI-0/1 | Extract shared view-model; add provider abstraction; keep Tk MVP working |
| UI-4 | Ship Tk MVP + optionally a thin SwiftUI client per stack decision |
| v0.7 | Native macOS polish, notarized packaging, richer design |

### Authority guardrails during migration

- Do not embed/fork CAPT authority into any UI.
- No UI writes the ledger or promotes driver output.
- Every UI mutation routes through a governed command op.
- The active model, memory, evidence, and runtime state are always projections.

---

## Stack selection summary (rationale in OSS survey)

- **TUI framework:** Textual (Python, keyboard-first, async, ssh-safe; fits the
  existing Python runtime and the operator-console panel model).
- **Desktop MVP now:** the existing thin Tk client (no restart).
- **macOS native target:** thin SwiftUI client over the same `RuntimeClient`
  contract; evaluate Tauri as a cross-platform webview alternative. Detail and
  licensing in the OSS survey.
- **Chat-shell patterns:** borrow information architecture / interaction
  patterns from a compatible-license OSS chat UI (see survey); do **not** fork a
  whole product or copy code without license confirmation.
