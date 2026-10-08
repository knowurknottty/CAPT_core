# Native macOS CAPT — RuntimeService capability parity tracker

Date: 2026-10-08. Canonical source: CAPT_core. This is a source-backed
capability inventory, **not** a claim that the native app has feature parity.

## Authority invariant

RuntimeService/EventStore/ToolBroker remain authoritative. The Swift app must
not directly modify SQLite, bypass HumanApproval, convert observations to
verified claims, auto-approve model tasks, or infer any unrecorded transition.
One logical vessel is one analytical perspective, **not** one inference call.
Two cohorts can mean two provider calls if explicitly dispatched. No parallel
cohorts by default.

## Latest live runtime contract

23 query operations and 28 command operations observed. Availability of an
operation in the runtime contract is **not** proof of end-to-end Swift UX.

## Native implemented / integration in progress

- Chat/PI: native chat sessions, PI compile/revise/select/cancel proposal,
  approval request/decision, bound provider dispatch, provider-result review;
  per-request socket isolation, local PI wait escape.
- Councils: native chat-bound governed council editor (1–24 cohorts),
  independent provider/model identities, equal vessels per cohort (1–1000),
  explicit concurrency (default sequential), stable idempotency identities,
  independent HumanApproval buttons, read-only model authority, encrypted
  session state, status refresh and exact-lineage reattach after transport loss.
  Dispatch is gated on **runtime-owned** approved state.
- Missions: list scoped mission-grade/active/history, task graph, task/run cancel.
- Evidence: accepted/pending/all filter and independent claim verification read.
- Ledger: bounded timeline and optional low-level event filtering.
- Bots, providers, memory, skills, approvals, Runtime: surfaced in native views;
  coverage and permission boundaries require separate acceptance tests.

## Remaining substantive parity work — NOT complete

1. **Native operator orchestration:** governed multi-task mission creation,
   task graph editing, DriverRun reassignment and evidence-bound continuation.
2. **Tools and execution surfaces:** tool catalog and ToolBroker inspection,
   workspace MCP servers, tool-run receipts, per-project authority UX, project
   eligibility, secure intake/quarantine, governed Search/Deep Research.
3. **Council workbench:** persist complete per-cohort receipts and status
   timelines; merge independently verified results into user-facing comparison;
   execution authority editor with policy previews; PI enhancement of each
   cohort objective without unintended cross-model substitution.
4. **Forensics:** per-stream events, replay-at-sequence, security rejection
   viewer, branch/fork replay, governed capability revocation, steering.
5. **Provider feature parity:** local MLX/llama.cpp/Prism/OpenRouter selection,
   warmup diagnostics, provider model switching, offline/error recovery;
   independent live testing across every supported backend.
6. **Accessibility:** TIA acceptance of all major controls, startup/window
   recovery, keyboard navigation, VoiceOver semantics, regression automation.
7. **Multimodal:** governed image, microphone/voice, and any future video
   capability only when RuntimeService has an equivalent audited contract.
8. **Release closure:** live gated native↔runtime↔MCP tests, full Python
   gate, notarization/distribution, rollback, release evidence.

## Verification evidence for this slice

- 131 Swift tests passed; 9 explicitly skipped live/integration tests.
- TIA on staged signed CAPT.app observed the new Council disclosure control,
  the approval-preparation button, Add Cohort and vessel count.
- No paid inference was dispatched, no HumanApproval was auto-decided.
- This change does not claim full feature parity until the remaining items
  each pass source/test/install/live/release gates.
