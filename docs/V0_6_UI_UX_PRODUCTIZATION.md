# CAPT v0.6/v0.7 — UI/UX Productization Workstream

**Status:** additive canonical productization requirements
**Parent authority:** `docs/V0_6_PRODUCTIZATION_SOURCE_OF_TRUTH.md`

## Governing UX requirement

CAPT is not broadly usable until a normal technically capable person can operate the primary system without understanding Unix sockets, ledger paths, RuntimeService internals, DriverHost, ContextPack implementation details, or provider-specific plumbing.

The preferred normal-user experience is a familiar chat-oriented interface backed by CAPT authority, with progressive disclosure of governance, memory, evidence, and runtime state.

The UI must never become a second runtime. All mutation and authority remain in CAPT RuntimeService and its governed command/query surfaces.

## Version boundary

### v0.6 — required usability foundation

v0.6 should include:

1. a polished TUI;
2. a usable desktop application MVP;
3. unified model/provider discovery and selection;
4. CaveCAPT verbosity controls;
5. runtime/model/context/evidence visibility;
6. human approval/cancel/checkpoint/resume controls;
7. normal-user onboarding and error recovery.

A broad public release should not depend on CLI-only operation.

### v0.7 — deeper native-product polish

v0.7 may carry:

- richer native visual design and animation;
- notarized/signed platform packaging and auto-update maturity;
- advanced conversation/session organization;
- richer provider/model parameter editing;
- advanced memory/context visualization;
- extensible themes/layouts;
- additional platform-native integrations;
- more sophisticated multi-window/operator workflows.

v0.7 should refine the product rather than postpone basic usability.

---

# 1. Shared operator UX contract

TUI and desktop must consume the same CAPT-backed operator model.

Required shared concepts:

- runtime status;
- current mission;
- task graph/state;
- approval queue;
- active provider/model;
- current context/token budget;
- memory-trigger state;
- checkpoint/recovery state;
- evidence/verification state;
- EventStore timeline;
- operator controls.

No UI may fabricate authoritative state locally.

---

# 2. Familiar chat-first desktop experience

The desktop application should initially feel familiar to users of ChatGPT-style interfaces while exposing CAPT-specific controls progressively.

Recommended shell:

```text
+------------------------------------------------------------------+
| CAPT | Runtime healthy | Model: Qwen... | Context 18k/32k        |
+----------------------+-------------------------------------------+
| Sessions / Missions  |                                           |
|                      | Conversation / mission transcript          |
| + New mission        |                                           |
| Project A            |                                           |
| Project B            |                                           |
|                      |                                           |
+----------------------+-------------------------------------------+
| Memory | Evidence | Runtime | Approvals | Settings               |
+------------------------------------------------------------------+
| message / task input                                      Send   |
+------------------------------------------------------------------+
```

CAPT-specific surfaces should include:

- status indicator;
- mission selector;
- model/provider selector;
- CaveCAPT verbosity control;
- context-budget indicator;
- approval notifications;
- evidence/completion indicator;
- checkpoint button;
- stop/cancel control;
- memory/evidence/runtime inspectors.

The default screen should remain simple enough to use without learning CAPT's internal nouns first.

---

# 3. Native desktop requirement

A regular user should be able to launch CAPT as an application rather than a terminal workflow.

For macOS, evaluate the existing desktop/runtime-client work and prefer a thin native SwiftUI client over duplicating runtime logic.

Architecture:

```text
SwiftUI / native desktop UI
        |
        | authenticated local IPC / supported operator API
        v
CAPT RuntimeService
        |
        +-- EventStore
        +-- Memory Governor
        +-- Evidence / Verification
        +-- DriverHost
```

The desktop app owns presentation and operator intent only.

Do not embed or fork CAPT authority into the UI.

Cross-platform alternatives may be evaluated separately, but native macOS quality is a priority for the initial product because the current development/runtime environment is macOS-first.

---

# 4. OSS UI reference / reuse investigation

Before implementing a large desktop shell from scratch, conduct a license-aware survey of open-source chat interfaces that resemble the familiar ChatGPT web layout.

Candidate categories to investigate include modern open-source LLM chat clients and self-hosted chat UIs.

The purpose is to identify reusable:

- information architecture;
- interaction patterns;
- component structure;
- visual inspiration;
- potentially reusable code where licensing and architecture are compatible.

Do not copy code without confirming license compatibility and attribution requirements.

The final CAPT desktop UX must be redesigned around CAPT authority, missions, approvals, evidence, memory, provider switching, and recovery rather than remaining a generic chatbot skin.

---

# 5. TUI requirement

Ship a terminal-native operator interface for developers and power users.

The TUI should provide at minimum:

```text
CAPT
├── Chat / Mission
├── Runtime
├── Models
├── Approvals
├── Memory / Context
├── Evidence
└── Events
```

Required capabilities:

- start/connect to runtime;
- enter a user task/message;
- select provider and model;
- change CaveCAPT verbosity;
- display streaming model output where supported;
- show active mission/task state;
- approve/deny requests;
- checkpoint/resume/cancel;
- inspect evidence and verification;
- inspect memory/context status;
- show errors/remediation without requiring raw JSON.

The TUI must use supported CAPT command/query interfaces and not direct ledger mutation.

Evaluate established Python TUI frameworks rather than hand-building terminal rendering unless there is a strong reason not to.

---

# 6. Unified model/provider UX

A normal user must not configure DriverHost manually.

Required provider abstraction should support a common operator workflow across at least:

- OpenRouter;
- Ollama;
- LM Studio;
- llama.cpp-compatible servers;
- MLX / mlx_lm;
- vLLM;
- Hermes compatibility where applicable.

User workflow should approximate:

```text
Settings -> Models

Provider: [LM Studio v]
Endpoint: detected / editable
Model:    [Qwen... v]
Context:  32768
Status:   Connected

[Test connection]
[Use model]
```

CLI/TUI equivalent should expose a coherent model-management surface, e.g.:

```zsh
capt models providers
capt models discover
capt models list
capt models test <provider/model>
capt models use <provider/model>
```

Exact command names may change after implementation review.

## Provider discovery

Where practical:

- LM Studio: discover local OpenAI-compatible endpoint/models;
- Ollama: discover running local service and installed models;
- OpenRouter: retrieve available models using configured credentials/network;
- llama.cpp/vLLM: support explicit OpenAI-compatible endpoint configuration;
- MLX: enumerate configured/local supported models where technically reliable.

Never silently send prompts to a cloud provider when the user believes a local provider is selected.

Clearly display LOCAL versus REMOTE/CLOUD.

---

# 7. Model parameters

The user should be able to edit common generation settings when the provider supports them:

- context window / safe context limit;
- temperature;
- top-p;
- top-k;
- min-p where supported;
- max output tokens;
- seed where supported;
- reasoning/thinking controls where supported;
- provider/model-specific advanced settings behind progressive disclosure.

Defaults should be safe and provider-aware.

Unsupported parameters must be disabled or omitted rather than silently ignored where possible.

---

# 8. CaveCAPT verbosity controls

CaveCAPT must expose an explicit operator-controlled verbosity setting.

The UI should not require users to edit prompts or configuration files simply to change how much CAPT explains itself.

At minimum provide a compact control such as:

```text
CaveCAPT verbosity
[ Minimal | Normal | Detailed | Diagnostic ]
```

Recommended semantics:

- **Minimal** — final answer / essential operator prompts only;
- **Normal** — useful progress, decisions, approvals, important evidence summaries;
- **Detailed** — richer runtime explanation, memory/context actions, verification summaries;
- **Diagnostic** — engineering-level operational details, IDs, policy/evidence/runtime diagnostics.

This control should affect presentation/explanatory output, not weaken governance, evidence requirements, policy checks, or verification.

If CaveCAPT currently conflates verbosity with internal reasoning or policy behavior, separate those concerns.

The selected setting should persist locally and be visible in TUI and desktop settings.

---

# 9. Memory/context UX

Normal users need understandable memory visibility rather than raw internal structures.

Desktop/TUI should expose:

- whether memory is active;
- current ContextPack/token usage;
- next trigger threshold;
- recent retrieved memories;
- provenance/source;
- pinned/important memories;
- memory search;
- concise explanation of why a memory entered context;
- optional advanced view for lifecycle/conflicts/relations.

Do not dump raw durable memory indiscriminately into the model or UI.

---

# 10. Evidence UX

Evidence should be one of the strongest visible product differentiators.

For a completed task/claim, provide a human-readable "Why complete?" or "Evidence" action showing:

```text
Claim
  -> Evidence
  -> Verification result
  -> ClaimGuard decision
  -> Relevant runtime events / receipts
```

Users should not need to understand EventStore schemas to know why CAPT believes work is complete.

Advanced mode may expose raw IDs/hashes/JSON.

---

# 11. Approval UX

Consequential actions must produce obvious approval UI.

Desktop:

- clear notification/badge;
- requested capability;
- operation;
- scope;
- risk/reason;
- approve;
- deny;
- optional note.

TUI:

- dedicated approval panel;
- keyboard-accessible approve/deny;
- no hidden or auto-approved consequential action unless policy explicitly allows it.

---

# 12. Runtime controls

Normal-user surfaces need obvious:

- Start;
- Status;
- Checkpoint;
- Resume;
- Stop;
- Cancel current task/run.

The user should not need to know socket/token/ledger paths for ordinary operation.

Expert settings may expose them.

---

# 13. Error and recovery UX

Errors should be translated into actionable operator language.

Examples:

- model provider unavailable;
- credential missing;
- endpoint unreachable;
- model context too small;
- stale runtime socket;
- runtime stopped;
- approval required;
- memory integrity failure;
- checkpoint unavailable;
- provider rate limited;
- cloud/network unavailable.

Every common error should offer a recommended next action.

---

# 14. First-run onboarding

Desktop should eventually provide a first-run setup flow:

1. Welcome / one-sentence CAPT explanation;
2. choose Local or Cloud model path;
3. detect available local providers;
4. optionally configure OpenRouter;
5. choose model;
6. run connection test;
7. explain approval/evidence briefly;
8. run a small first governed mission;
9. show evidence;
10. optionally enable advanced controls.

Do not require understanding CAPT architecture during first run.

---

# 15. Accessibility and interaction polish

Required UI quality considerations:

- full keyboard navigation for core controls;
- readable contrast;
- scalable text;
- reduced-motion compatibility where relevant;
- clear focus states;
- no color-only status communication;
- copy/export for evidence and diagnostics;
- searchable sessions/missions where practical;
- confirmation for destructive actions;
- streaming state that distinguishes model output from CAPT status/evidence.

---

# 16. Session and mission organization

Avoid treating all work as one endless chat transcript.

Users should be able to see:

- conversations / missions;
- status;
- model/provider used;
- timestamps;
- checkpoint/recovery availability;
- verification/completion state.

A chat may be the interaction metaphor, but Mission/EventStore state remains authoritative.

---

# 17. Privacy UX

Always make model destination obvious.

The UI must visibly distinguish:

- LOCAL processing;
- REMOTE/CLOUD processing.

Before first use of a remote provider, explain that prompts/context required for inference leave the local machine according to that provider's service path.

Never expose API keys in logs, evidence views, or exported diagnostics.

---

# 18. UI acceptance gates

## v0.6 UI acceptance

A first-time technically capable user can, without terminal-only knowledge:

1. launch CAPT through desktop or TUI;
2. see whether runtime is healthy;
3. select/configure a supported model provider;
4. select a model;
5. set CaveCAPT verbosity;
6. submit a governed task;
7. respond to an approval request;
8. observe model/runtime progress;
9. inspect context/memory status;
10. checkpoint/cancel/resume;
11. inspect evidence/verification;
12. recover from common provider/runtime failures using surfaced guidance.

At least one TUI path and one desktop path must be demonstrated end-to-end against the real RuntimeService.

## v0.7 polish acceptance

A non-developer user can install and operate the native desktop application with minimal or no terminal use, including first-run provider configuration and common troubleshooting.

---

# 19. Immediate implementation sequence

Recommended ordering:

### UI-0 — UX architecture and OSS survey

- audit existing `desktop/` client/service work;
- define shared operator view-model / supported query-command contract;
- survey compatible OSS chat UI patterns/codebases and licenses;
- choose native desktop stack and TUI framework;
- define screenshots/wireframes before implementation.

### UI-1 — Model/provider configuration core

- provider registry/config model;
- discover/list/test/use operations;
- provider health and model metadata;
- local/cloud labeling;
- settings persistence.

### UI-2 — CaveCAPT verbosity preference

- define stable verbosity enum/contract;
- persist setting;
- wire presentation behavior;
- CLI/TUI/desktop controls.

### UI-3 — TUI MVP

- runtime state;
- chat/task input;
- model selector;
- approvals;
- memory/context status;
- evidence;
- checkpoint/stop/resume.

### UI-4 — Native desktop MVP

- ChatGPT-familiar shell;
- mission/session sidebar;
- provider/model selector;
- verbosity control;
- approvals;
- runtime/memory/evidence panels;
- checkpoint/cancel/resume;
- first-run provider setup.

### UI-5 — Independent usability test

Give a new technically capable user only the shipped application/docs and measure whether they can complete the v0.6 release gate without author assistance.

---

# Source-of-truth rule

These requirements supplement `docs/V0_6_PRODUCTIZATION_SOURCE_OF_TRUTH.md` and should be treated as canonical UI/UX product requirements unless explicitly superseded by a later reviewed commit.
