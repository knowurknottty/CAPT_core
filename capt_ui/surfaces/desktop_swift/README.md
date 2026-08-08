# CAPT Native macOS Desktop MVP (SwiftUI)

**Status:** NATIVE_DESKTOP_TRACK_INITIATED — first slice (client contract +
project scaffold). This is NOT the shipped native product yet.

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

## Initial surface (per roadmap UI-4)

- first-run onboarding;
- runtime start/status/stop;
- provider selection;
- model selection;
- CaveCAPT verbosity;
- conversation/mission surface;
- approval queue (approve/deny);
- memory/context status;
- evidence inspector;
- checkpoint/resume;
- provider LOCAL/CLOUD state;
- event/provenance view;
- troubleshooting surface.

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
