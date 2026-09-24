# OpenWorker → CAPT convergence

Upstream: https://github.com/andrewyng/openworker
Snapshot: 37a09360d1d99a34b19c07b35c429f9b0a56abb0
License: MIT, Copyright (c) 2024 Andrew Ng.

## Provenance-preserving import

The complete upstream snapshot is retained under third_party/openworker/ as a git subtree.
This is deliberate: CAPT does not erase OpenWorker provenance or relabel upstream work as
original CAPT implementation.

## Active adaptations

CAPT cherry-picks the high-value, runtime-compatible mechanisms below into
capt_runtime/openworker_compat/:

- multimodal attachment shaping for image/PDF/text inputs;
- deterministic live-clock helper;
- bounded workspace/environment snapshot;
- conservative read-only shell classification and read-target extraction;
- frozen session-known-world and external-ingestion facts;
- bounded model-visible tool-result rendering;
- SSRF / private-network URL guard;
- explicit user-owned workspace trust store;
- base-directory containment helper.

The adapted modules are intentionally stdlib-only so they do not widen CAPT's base dependency
surface.

## Authority boundary

OpenWorker's engine, permission engine, conversation/session stores, server, providers,
connectors, scheduler, reviewer, inbox, teams, remote-machine runtime, and GUI remain available
in the subtree for further convergence, but are not activated as parallel CAPT runtimes.

CAPT keeps these invariants:

1. RuntimeService/EventStore stays authoritative.
2. Tool side effects still cross ToolBroker and CAPT capability leases.
3. Provider/model output does not become evidence by assertion.
4. No imported approval/autonomy path may mint or widen CAPT authority.
5. New media input must still pass CAPT Secure Intake / Quarantine before model eligibility.

## First live integration

OpenWorker's tool-result bounding is applied only to the copy of ToolBroker results sent back
into a model's conversation. The full raw ToolResult remains durable in CAPT's EventStore.
This limits context amplification without weakening evidence or silently discarding canonical
tool output.

## Convergence inventory

The subtree is intentionally broader than the first live adaptation. Current disposition:

| OpenWorker area | CAPT disposition |
| --- | --- |
| attachments / PDF / multimodal message normalization | adapted now; provider dispatch wiring follows Secure Intake |
| result bounding / context amplification control | live now in ModelToolBridge |
| readonly command classifier / read-target extraction | adapted and tested; candidate for session-grant policy |
| workspace trust / base-dir containment | adapted and tested; candidate for project-root policy |
| session facts / ingestion provenance | adapted and tested; candidate for approval/reviewer context |
| SSRF and private-network URL guard | adapted and tested; must front any future CAPT web-fetch/browser adapter |
| clock / environment snapshot | adapted and tested |
| STT Rust sidecar | retained verbatim for voice convergence; not yet authoritative CAPT media I/O |
| sandbox providers (Seatbelt/OpenShell/runner) | retained for convergence; CAPT ToolBroker remains the authority boundary |
| provider matrix (OpenAI/Anthropic/Gemini/Bedrock/Vertex/Codex) | retained as donor implementations; CAPT provider contracts remain canonical |
| MCP/connectors/email/calendar/GitHub/browser | retained as donor implementations; effects must be re-hosted behind ToolBroker |
| automations / self-wake / inbox | retained as donor implementations; scheduling must emit CAPT missions/tasks/events |
| personas / skills / reviewer | retained as donor implementations; may not mint authority or evidence |
| teams / board / journal | retained as donor implementations; likely donor for higher-level Council/operator UX |
| server / remote homes / cloud proxy | retained only; not activated as an alternate CAPT control plane |
| React/Tauri GUI | retained as a UI donor; UI is never runtime authority |

This is the governing interpretation of "majority": the upstream implementation is available
locally, with provenance intact, while CAPT activates mechanisms only after their effects are
mapped to CAPT authority/evidence semantics. Wholesale replacement of CAPT RuntimeService with
OpenWorker's engine would import more files but less architecture.

## Verification

CAPT's pytest configuration excludes third_party from CAPT test discovery because vendored
projects own separate dependency/test matrices. The adapted boundary is covered by native CAPT
tests. Upstream tests remain present verbatim under third_party/openworker/tests for isolated
upstream verification when its development dependencies are installed.
