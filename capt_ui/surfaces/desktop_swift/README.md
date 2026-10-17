# CAPT Native macOS Desktop (SwiftUI)

**Status:** NATIVE_DESKTOP_CORE_PARITY_INTERNAL_DOGFOOD_READY — runnable
`CAPT.app` with authenticated RuntimeService IPC, governed multi-turn model
execution, cold-start bootstrap/recovery, encrypted restartable chat sessions,
and operator coverage for the meaningful RuntimeService capabilities exposed by
the current CAPT-core candidate.

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
- AES-GCM encrypted classic presentation-session cache at `~/.capt/ui/classic_native_sessions.enc` with a device-only macOS Keychain key and `0600` file permissions; on first use, the legacy shared `native_sessions.enc` cache is migrated once, preserving valid bound approvals while quarantining expired/unknown cursors;
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
- governed checkpoint/resume/shutdown + cold rebootstrap controls with checkpoint, ledger, and integrity digests surfaced;
- task and DriverRun cancellation controls gated by the live capability contract and aggregate state;
- complete six-threshold governed memory-policy editor; RuntimeService remains validator and policy authority;
- read-only ClaimGuard + verification drill-down preserving advisory/uncommitted/not-tested distinctions;
- live RuntimeService capability inventory for queries, commands, components, and lifecycle operations;
- bounded 4 MiB framed Unix-socket transport;
- `script/install_local_runtime.sh` builds/installs the exact local CAPT wheel into a private venv;
- `script/build_and_run.sh --verify` installs or refreshes the private runtime when missing or stale, then builds and signs **one** verified native bundle with a `CAPTSourceCommit` marker. It transactionally publishes identical signed copies to `dist/CAPT.app` and `~/Applications/CAPT.app`, and launches **only the installed** `~/Applications` copy used by TIA. Existing bundles are archived before replacement; failure restores both copies. A stable Apple Development signing identity is required by default (development-only ad-hoc signing must be explicitly opted in).

The meaningful current RuntimeService operator surface is represented. Low-level
`create_mission` and fixed OpenHarness commands remain visible in the live
capability inventory but intentionally do not get competing native workflows;
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
  Memory / Evidence / Runtime / Ledger / Settings
- Conversation: familiar chat shell; messages represent mission work, runtime
  state, approvals, evidence, recovery, memory (not just chat)
- Right inspector (dynamic): current model, provider, mission, checkpoint,
  ledger, evidence, verification, memory, context budget, driver, latency
- Bottom status (always visible): Runtime / Connected / Healthy / Checkpoint /
  Context / Provider / Model / Memory / EventStore

## Native app packaging and drift prevention

From the Swift package folder, invoke `./script/build_and_run.sh --verify` for a verified install. This is not merely a `dist/` build: it publishes the exact same signed executable and source-commit marker to both `dist/CAPT.app` and `~/Applications/CAPT.app`. Only `~/Applications/CAPT.app` is launched, matching TIA's fixed signed-process identity.

The installer stages and verifies the complete bundle **before** closing any running CAPT app, requests normal app quit without force killing the process, and snapshots both previous bundles under `~/.capt/app-release-backups/`. Swaps occur at their respective destination filesystem paths; on any replacement, signing, or launch failure, both old bundles are restored. RuntimeService and its ledger are not restarted by the bundle publisher. Native package source changes during the build fail closed to avoid a false `CAPTSourceCommit` claim.

The existing runtime installer preflight remains in `build_and_run.sh`; it can update the private Python runtime when source HEAD differs. Do not confuse that runtime-package update with a RuntimeService restart. For a strictly UI-only build without modifying the private runtime, use the separate `swift build --product CAPTNativeMac` path, which builds an executable but **does not publish** either app.

Configuration: `CAPT_CODESIGN_IDENTITY` selects an exact signing identity; absent an identity, publication stops rather than silently replacing the TIA-targeted signed app with an ad-hoc signature. Set `CAPT_ALLOW_ADHOC_SIGNING=1` explicitly only in isolated development environments, not the production TIA identity. `CAPT_APP_BACKUP_DIR` overrides the archive location. The packaging helper is `script/install_signed_bundle.py`; its tests are `tests/capt_runtime/test_native_app_packaging.py`.
