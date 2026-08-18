# Inversion Labs CAPT Native macOS Desktop (SwiftUI)

**Status:** INVERSION_LABS_R1_DOGFOOD_READY_WITH_BOUNDED_LIMITS — runnable
`Inversion Labs CAPT.app` with authenticated RuntimeService IPC, governed
multi-turn model execution, additive specialist Labs, cold-start bootstrap,
encrypted restartable chat sessions, and the meaningful operator surface of the
frozen CAPT-core base. All 15 R1 acceptance gates passed; exact evidence and
bounded exclusions are recorded under `reports/lab/` and `docs/lab/`.

**Purpose:** a separate Inversion Labs edition built on the frozen CAPT runtime
boundary. The SwiftUI app is still a thin renderer/controller: it does NOT port
RuntimeService to Swift, execute Lab engines directly, or duplicate authority.

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
- AES-GCM encrypted presentation-session cache at `~/.capt-inversion-labs/ui/native_sessions.enc` with a device-only macOS Keychain key and `0600` file permissions;
- process-death/relaunch restoration of transcript, mission binding, provider/model/target preferences, and exact native-origin pending approval;
- multi-turn governed continuation: one durable mission, a fresh authoritative Task per turn, prior model evidence selected by CAPT with trust labels preserved;
- authenticated connection to `~/.capt-inversion-labs/runtime.sock` + `runtime.token`;
- cold-start recovery through the private `~/.capt-inversion-labs/runtime-venv/bin/capt` CLI;
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
- governed checkpoint/resume/shutdown + cold rebootstrap controls with checkpoint, ledger, and integrity digests surfaced;
- task and DriverRun cancellation controls gated by the live capability contract and aggregate state;
- complete six-threshold governed memory-policy editor; RuntimeService remains validator and policy authority;
- read-only ClaimGuard + verification drill-down preserving advisory/uncommitted/not-tested distinctions;
- live RuntimeService capability inventory for queries, commands, components, and lifecycle operations;
- dedicated Labs surface backed only by `lab_engines` + `run_lab_engine_advisory`, with Math, Structural Analogy, QIPC Consensus, and bounded Forge instruments;
- explicit epistemic labels (`CALCULATION`, `HEURISTIC`, `ADVISORY`) kept separate from CAPT authority state (`UNVERIFIED` unless a real verification identity exists);
- Lab donor commit/source digests and limitations visible before execution;
- Lab runs require an existing authoritative mission/task and never manufacture hidden lineage;
- separate edition state root `~/.capt-inversion-labs` (or `CAPT_LAB_STATE_DIR`) with its own runtime venv/socket/token/ledger/session ciphertext and Keychain service;
- distinct signed bundle identity `com.inversionlabs.capt.lab`, allowing the golden core CAPT app/runtime to coexist unchanged;
- bounded 4 MiB framed Unix-socket transport;
- `script/install_local_runtime.sh` builds/installs the exact local CAPT wheel into a private venv;
- `script/build_and_run.sh --verify` installs that runtime if needed, stages, signs, verifies, and launches `dist/Inversion Labs CAPT.app`.

The meaningful current RuntimeService operator surface plus the additive Lab
registry/command surface is represented. Low-level `create_mission` and fixed
OpenHarness commands remain visible in the live capability inventory but
intentionally do not get competing native workflows;
the governed chat path subsumes their normal operator use. Remaining work is
productization: onboarding polish, deeper artifact/provenance browsing, icon
and visual polish, provider-specific advanced settings, and distribution-grade
notarization. Internal development builds are signed with a stable Apple
Development identity when available (override with `CAPT_CODESIGN_IDENTITY`),
falling back to ad-hoc signing only when no development identity exists.
None of these productization items may create alternate runtime authority.

## Behavioral reference

Use the current Tk client (`capt_ui/surfaces/desktop/surface.py`) and
`capt_ui/operator` as behavioral references. Do not duplicate authority.

## Layout (per UI_WIREFRAMES.md)

- Sidebar: New Chat / Recent Chats / Chat / Missions / Approvals / Providers /
  Memory / Evidence / Labs / Runtime / Ledger / Settings
- Conversation: familiar chat shell; messages represent mission work, runtime
  state, approvals, evidence, recovery, memory (not just chat)
- Right inspector (dynamic): current model, provider, mission, checkpoint,
  ledger, evidence, verification, memory, context budget, driver, latency
- Bottom status (always visible): Runtime / Connected / Healthy / Checkpoint /
  Context / Provider / Model / Memory / EventStore
