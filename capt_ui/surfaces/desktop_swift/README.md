# CAPT Native macOS Desktop (SwiftUI)

**Status:** NATIVE_DESKTOP_INTERNAL_DOGFOOD_CANDIDATE — runnable `CAPT.app`
with authenticated RuntimeService IPC, governed multi-turn model execution,
cold-start runtime bootstrap, encrypted restartable chat sessions, and live
mission/approval/evidence/memory/ledger projections.

**Purpose:** a thin SwiftUI macOS client over the authenticated CAPT runtime
boundary. It does NOT port RuntimeService to Swift and does NOT duplicate
authority.

```
SwiftUI (this app)
   |
CAPT Desktop Client Contract (CAPTDesktopClientContract)
   |
authenticated local IPC (Unix socket, token)
   |
RuntimeService
   |
EventStore / Memory / Governance / Drivers
```

## Client contract

`CAPTDesktopClientContract.swift` defines a Swift value-type projection of the
SAME operator concepts the CLI/TUI/desktop consume, so the native app is a thin
renderer, not a second runtime. Fields map to the shared operator layer
(`capt_ui/operator/contract.py`):

- `OperatorStatus` (health, version, integrity, head, active provider/model,
  context used/limit, approvals pending, checkpoint available)
- `ProviderState` (id, name, kind LOCAL/REMOTE, transport, health, latency,
  models, keyRef)
- `ModelSelection` (default / mission / temporary / workflow overrides)
- `Dashboard` (missions, tasks, approvals, driver runs, events, evidence,
  verification, ledger digest, memory)
- `CaveCAPTVerbosity` (minimal / normal / detailed / diagnostic)
- `ApprovalRequest` (requestId, missionId, taskId, capability, operation,
  scope, risk, state)

Every value type is derived from runtime queries. The app never holds a "true"
copy of authoritative state.

## RuntimeClient bridge

The Swift app talks to RuntimeService over the same authenticated local
Unix-domain socket + token that `desktop/desktop_runtime_client.py` uses. There
is deliberately NO port of the runtime to Swift; Swift only issues the query/
command ops and renders projections.

## Current native slice

Implemented and exercised on macOS:

- native ChatGPT-style sidebar/detail/inspector chat shell with New Chat + recent conversations;
- AES-GCM encrypted presentation-session cache at `~/.capt/ui/native_sessions.enc` with a device-only macOS Keychain key and `0600` file permissions;
- process-death/relaunch restoration of transcript, mission binding, provider/model/target preferences, and exact native-origin pending approval;
- multi-turn governed continuation: one durable mission, a fresh authoritative Task per turn, prior model evidence selected by CAPT with trust labels preserved;
- authenticated connection to `~/.capt/runtime.sock` + `runtime.token`;
- cold-start recovery through the private `~/.capt/runtime-venv/bin/capt` CLI;
- global approval-decision queue with explicit decision-vs-dispatch separation;
- live provider inventory/health with test + activate controls via the packaged operator layer;
- live model inventory/default-model control and CaveCAPT verbosity preference;
- provider credential-reference setup (`env:` / `keychain:` only; raw tokens rejected);
- explicit target-root selection;
- governed `request_model_prompt_approval` flow;
- visible approve/deny decision card;
- exact bound `run_approved_hermes_inspection` execution after approval only;
- immutable approved dispatch text decoupled from bounded Task titles while retaining the final pre-network digest gate;
- returned model observations rendered in the transcript;
- authoritative task state shown without automatic verification/promotion;
- read-only mission/task lineage, claim/evidence state, and last-250 EventStore timeline projections;
- authoritative memory-policy/ContextPack inspector via RuntimeService;
- governed checkpoint/resume controls with checkpoint, ledger, and integrity digests surfaced;
- bounded 4 MiB framed Unix-socket transport;
- `script/install_local_runtime.sh` builds/installs the exact local CAPT wheel into a private venv;
- `script/build_and_run.sh --verify` installs that runtime if needed, stages, and launches `dist/CAPT.app`.

Remaining core-surface parity work is intentionally bounded to current RuntimeService
capabilities: active task/DriverRun cancellation, memory-policy mutation,
ClaimGuard/verification drill-down, and explicit runtime shutdown. After those
controls are wired, remaining work is productization: onboarding polish, deeper
artifact/provenance browsing, signing/notarization, icon/visual polish, and
provider-specific advanced settings. None of those may create alternate runtime authority.

## Behavioral reference

Use the current Tk client (`capt_ui/surfaces/desktop/surface.py`) and
`capt_ui/operator` as behavioral references. Do not duplicate authority.

## Layout (per UI_WIREFRAMES.md)

- Sidebar: Sessions / Missions / Memory / Providers / Evidence / Settings /
  Logs / Help
- Conversation: familiar chat shell; messages represent mission work, runtime
  state, approvals, evidence, recovery, memory (not just chat)
- Right inspector (dynamic): current model, provider, mission, checkpoint,
  ledger, evidence, verification, memory, context budget, driver, latency
- Bottom status (always visible): Runtime / Connected / Healthy / Checkpoint /
  Context / Provider / Model / Memory / EventStore
