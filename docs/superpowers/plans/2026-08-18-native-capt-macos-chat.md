# Native CAPT macOS Chat Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a native SwiftUI CAPT chat/operator app that uses the existing authenticated RuntimeService IPC and governed model-approval flow.

**Architecture:** Extend the existing `CAPTCoreDesktop` SwiftPM package with a bounded Unix socket client and an executable SwiftUI target. The app owns presentation only; every consequential action remains a CAPT command.

**Tech Stack:** Swift 6, SwiftUI, Observation, Darwin Unix sockets, SwiftPM, XCTest, CAPT RuntimeService IPC.

**Spec:** `docs/superpowers/specs/2026-08-18-native-capt-macos-chat-design.md`

## Global Constraints
- macOS 13+ package compatibility; current build host macOS 26 / arm64.
- No raw credentials in Swift state or persisted preferences.
- No direct EventStore writes or direct provider calls.
- Human approval remains visible and mandatory.
- Framed transport is bounded and fail-closed.

---

### Task 1: Runtime transport and protocol models

**Files:** modify `Package.swift`; create `CAPTRuntimeClient.swift`; create `CAPTRuntimeModels.swift`; test `CAPTRuntimeClientTests.swift`.

- [ ] Add RED tests for 4-byte big-endian framing, oversize rejection, command-envelope operator/session binding, and response extraction.
- [ ] Implement `CAPTRuntimeClient` with token auth, query, and governed command methods.
- [ ] Run `swift test` and commit transport slice.
### Task 2: Operator store and governed chat flow

**Files:** create `CAPTOperatorStore.swift`; test `CAPTOperatorStoreTests.swift`.

- [ ] Add RED tests for request→pending approval, deny-without-run, approve→exact run identities, and assistant-text extraction.
- [ ] Implement `CAPTOperatorStore` around an injectable runtime-client protocol.
- [ ] Preserve pending approval identity as immutable value state until approve/deny.
- [ ] Run `swift test` and commit operator-flow slice.

### Task 3: Native SwiftUI app surface

**Files:** create `CAPTNativeMacApp.swift`, `ContentView.swift`, `SidebarView.swift`, `ChatView.swift`, `InspectorView.swift`, `StatusBarView.swift`.

- [ ] Add a `WindowGroup` app with native `NavigationSplitView` and inspector.
- [ ] Render messages, pending approval card, provider/model controls, runtime state, and evidence/task status.
- [ ] Add keyboard send and toolbar connect/refresh actions.
- [ ] Build with `swift build` and commit UI slice.

### Task 4: Packaging and Run action

**Files:** create `script/build_and_run.sh`; create `.codex/environments/environment.toml`.

- [ ] Build executable target and stage `dist/CAPT.app` with a minimal Info.plist.
- [ ] Add kill/build/stage/open and `--verify` process check.
- [ ] Wire Codex Run action to the script.
- [ ] Run `./script/build_and_run.sh --verify` and commit packaging slice.

### Task 5: Live CAPT acceptance

- [ ] Start or connect to the real local CAPT runtime using `~/.capt/runtime.sock` and `runtime.token`.
- [ ] Prove identity/capabilities query from the Swift client.
- [ ] Submit a harmless prompt and prove pending approval before dispatch.
- [ ] Deny once and prove no run is created; then approve a fresh request using a local model and render its result.
- [ ] Re-run Swift tests, HY3 continuity tests, `git diff --check`, push branch, and open a stacked PR.