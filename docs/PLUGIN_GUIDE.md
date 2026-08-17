# CAPT Runtime and Integration Guide

CAPT exposes three relevant integration layers:

- `capt_solo.api` for supported in-process services;
- RuntimeService / `capt harness` for governed lifecycle and execution;
- `capt_ui.operator` for presentation/control clients such as TUI/desktop.

Hermes is an external compatibility/execution client. It is not CAPT runtime authority.

## Runtime integration

Use installed `capt harness --help` as the exact command authority. The harness owns authenticated runtime access, EventStore-backed lifecycle, command admission/idempotency, checkpoint/recovery, capability/lease boundaries, DriverHost, evidence/verification persistence, and bounded external execution.

## UI/operator integration

A client may project runtime/mission/memory/provider/approval/evidence state and submit operator intent through the shared operator/runtime boundary. It must not write SQLite/EventStore directly or promote model output to authoritative completion.

## Provider integration

Merged `main` contains provider registry/discovery/model-selection foundations. Active PR #47 adds bounded Ollama native and OpenAI-compatible generation transport with provenance/digests/secret scrubbing and conservative reconciliation semantics.

Do not label a provider operational merely because it registers or returns a model list.

## Hermes integration

The current evidence story has multiple layers:

- historical v0.5 installed-wheel bounded Hermes proof;
- active #46 lifecycle hardening;
- `HERMES_LOCAL_002_COMPLETE` local Hermes Agent TUI workspace/state-map evidence on `evidence/hermes-local-002-r6` at `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`.

LOCAL-002 reports 98/0/0 focused and 174/0/2 broader tests with no product/state-map blocker. It explicitly does not close the destructive external-provider/tool-kill rollback E2E gap.

## Building a compatibility client

A client should:

1. use public installed/runtime/operator contracts;
2. preserve CAPT-generated IDs and provenance;
3. request only declared capability/scope;
4. distinguish local client state from RuntimeService authority;
5. treat provider/model output as untrusted until evidence/verification admission;
6. test duplicate, restart, cancellation, stale-state, auth, and indeterminate-dispatch cases;
7. never silently persist credentials into evidence/logs;
8. retain limitations in user-facing output.

## Security rule

Prompt discipline is not runtime enforcement. Client-side approval UI is not capability authority. A model or compatibility client must never be documented as owning CAPT memory, ledger, verification, or completion state.