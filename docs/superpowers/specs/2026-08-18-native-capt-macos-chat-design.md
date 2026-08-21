# Native CAPT macOS Chat Surface Design

## Goal
Build a real native SwiftUI macOS application that presents CAPT as a familiar chat/operator surface while preserving RuntimeService/EventStore authority.

## Architectural boundary
The app is an untrusted renderer/controller. It never writes the ledger directly, never promotes model output, and never bypasses human approval. It speaks CAPT's existing authenticated framed Unix-socket protocol and submits governed command envelopes.

The native path is intentionally separate from the private-tunnel MCP path. Both terminate at CAPT authority; neither becomes authority itself.

## Runtime topology
`CAPT.app -> UnixSocketRuntimeClient -> ~/.capt/runtime.sock -> RuntimeService -> EventStore / providers / drivers / memory / verification`.

Remote Desktop Commander is a development/remote-control transport for this build and a proof that the Mac is reachable. CAPT.app itself uses the local socket when running on Kirk's Mac.

## Primary interaction
The center pane behaves like a chat transcript. Sending a message first creates a concrete model-execution approval request. The UI then exposes Approve or Deny. Approval executes the exact bound request; denial never dispatches a model.

Provider/model selection is explicit and defaults to the operator's configured local values. The first slice supports Ollama and OpenRouter identifiers already supported by CAPT.
## Window and state model
Use one `WindowGroup` with a three-column desktop layout: native sidebar, conversation detail, and inspector. App-wide state lives in one `@Observable` `CAPTOperatorStore`; view-local draft text stays `@State`.

Sidebar sections: Chat, Missions, Providers, Evidence, Settings. The first slice makes Chat fully operational and renders truthful summary/status views for the other sections.

The bottom status strip always shows runtime connectivity, provider, model, approval state, and EventStore head where available.

## Transport
`UnixSocketRuntimeClient` implements the existing 4-byte big-endian length-prefixed JSON protocol from `desktop/desktop_runtime_client.py`.

Authentication reads the token from `CAPT_STATE_DIR/runtime.token` or `~/.capt/runtime.token`, sends `{token}`, and records the returned `operatorId` and `sessionId`. All command envelopes bind those exact identities.

The client must enforce a bounded maximum frame size and fail closed on malformed, truncated, oversized, or non-JSON responses.

## Chat command flow
1. User submits text.
2. App calls `request_model_prompt_approval` with objective, target root, provider, model, 32K context, response mode, enhancement mode, and human verification required.
3. CAPT returns request/mission/task/driver-run identities.
4. UI renders an approval card; no provider dispatch has happened yet.
5. Approve calls `submit_approval_decision`.
6. The same bound identities call `run_approved_hermes_inspection`.
7. Returned observation/artifact text becomes an assistant transcript item labelled `awaiting_verification` where authoritative state says so.
8. Deny calls `submit_approval_decision(decision=deny)` and never dispatches.
## Safety and authority invariants
- No raw shell tool is exposed by the native UI.
- No provider credential is stored in Swift state or app preferences.
- No automatic approval in v1.
- No automatic verification, ClaimGuard acceptance, task success, or mission success.
- Exact runtime errors are surfaced as non-authoritative UI diagnostics.
- Runtime disconnection never falls back to direct filesystem/model execution.

## Packaging
Extend the existing Swift package with an executable SwiftUI target `CAPTNativeMac` while retaining the `CAPTCoreDesktop` library. Add focused XCTest coverage for framing, command-envelope identity binding, and response extraction.

A project-local `script/build_and_run.sh` builds, stages `dist/CAPT.app`, launches it, and supports `--verify`. `.codex/environments/environment.toml` exposes the same command as the Run action.

## Acceptance
The slice is accepted when: Swift tests pass; the app bundle builds and launches; it authenticates to a real CAPT runtime; a harmless prompt reaches the approval-request state; denial causes zero provider dispatch; and an approved local-model prompt returns a rendered CAPT result without bypassing RuntimeService.
