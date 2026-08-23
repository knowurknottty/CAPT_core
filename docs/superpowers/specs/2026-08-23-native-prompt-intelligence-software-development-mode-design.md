# Native Prompt Intelligence + Software Development Mode Design

**Status:** owner-approved architecture, implementation pending written-spec review  
**Baseline:** `main@3285ad07071d97f3622832bd6c91976f0094bb0b`  
**Scope:** CAPT Core RuntimeService + native macOS application + shared operator contracts  
**Authority rule:** prompt intelligence may propose; only CAPT may approve, mutate, execute, verify, promote, or declare completion.

## 1. Purpose

Bring the native macOS CAPT application to full parity with—and beyond—the current TUI prompt-intelligence prototype.

The finished system must:

1. preserve the user's literal original prompt as immutable provenance;
2. automatically compile a stronger execution-grade prompt by default;
3. show the proposed upgrade, rationale, engine chain, capability scope, and verification contract before execution;
4. require explicit human approval of either the upgraded prompt, an edited upgrade, or the original prompt;
5. bind the exact approved prompt assembly to the existing one-use RuntimeService approval identity;
6. provide a first-class **Software Development Mode** that engages governed Forge/Sigma capabilities and produces a continuation-ready repository that is actually buildable, testable, launchable, and runnable;
7. preserve the single CAPT RuntimeService/EventStore authority spine.

This design does not permit a UI, model, Forge, Sigma, OmniPrompter, MetaPrompter, or Labs engine to become a second runtime authority.

## 2. Current gap

At the baseline:

- the TUI exposes `OFF`, `AUTO`, `OMNI`, `META`, `FORGE`, and `SIGMA`;
- `inspect_prompt()` is a deterministic presentation-side heuristic that chooses an engine label and appends a short fixed suffix;
- the TUI requires `ENHANCE -> APPROVE -> RUN`, which is a sound approval shape but requires explicit enhancement and overwrites the editable prompt field;
- RuntimeService records the enhancement-engine label and binds the exact model-visible prompt, but does not execute the named prompt engines itself;
- native Swift chat hardcodes `promptEnhancement: "OFF"` for approval and execution;
- the real governed Forge repository archaeology/gap/SIGMA-brief implementation exists in the separate Inversion Labs lineage and remains advisory/read-only rather than a full software builder;
- there is no native Software Development Mode and no completion contract requiring a generated repository to build, run, and pass acceptance checks.

Therefore the product presently has strong approval plumbing but incomplete prompt-intelligence and software-production semantics.

## 3. Non-negotiable invariants

### 3.1 Original user intent is immutable

CAPT stores the literal submitted user prompt separately from every generated proposal. Enhancement never rewrites or replaces the original record.

Every proposal must contain at minimum:

- `originalPromptDigest`;
- `proposalPromptDigest`;
- selected engine chain;
- rationale;
- explicit assumptions;
- unresolved questions;
- requested capability envelope;
- verification/completion contract;
- provenance for model/provider/engine outputs used to create the proposal.

### 3.2 No silent execution

A generated proposal is never executable merely because CAPT generated it.

The human must explicitly choose one of:

- **Approve Upgrade**;
- **Edit Upgrade**, then approve the edited exact bytes;
- **Use Original**, then approve the original exact bytes;
- **Cancel**.

Any modification to prompt text, provider/model, context budget, capability envelope, target root, software-development mode, or verification contract invalidates the prior approval.

### 3.3 One authority plane

RuntimeService remains the sole mutation/admission authority. Prompt engines return proposals or advisory artifacts. Forge/Sigma cannot directly mark tasks complete, grant capability, verify claims, or promote artifacts.

### 3.4 No absolute "perfect prompt" claim

The product may describe an upgrade as optimized, execution-grade, or CAPT-compiled. It must not claim mathematical or universal prompt perfection. The user remains the final authority over intent.

## 4. Prompt compiler architecture

Introduce a RuntimeService-owned **PromptCompiler** orchestration boundary. The existing UI-only `inspect_prompt()` becomes a thin preview/fallback helper rather than the authoritative compiler.

### 4.1 Stage interface

Each stage consumes a bounded `PromptCompileContext` and returns a structured `PromptStageResult`:

```text
PromptCompileContext
  original prompt
  target/project root
  selected provider/model
  requested context budget
  current governed ContextPack references
  optional authored-skill context
  requested mode (normal/software-development)
  allowed stage capabilities (analysis only)

PromptStageResult
  stage identity/version
  proposed text delta or structured contract
  assumptions
  questions
  constraints added
  acceptance criteria added
  confidence/limitations
  evidence/provenance digest
```

Prompt stages have no filesystem-write, shell-write, Git-write, provider-secret, completion, or verification authority.

### 4.2 Engine responsibilities

**OmniPrompter** owns intent completeness. It identifies missing outcome, scope, inputs, outputs, constraints, safety/authority limits, success criteria, and ambiguities. It may ask questions rather than invent intent.

**MetaPrompter** converts the clarified intent into an execution contract: requested artifact, boundaries, evidence requirements, response format, uncertainty handling, and completion criteria.

**Forge prompt stage** specializes software/repository work: repository scope, acceptance tests, build/runtime expectations, mutation boundaries, tooling requirements, and proof obligations.

**Sigma prompt stage** reconciles competing requirements, architectural alternatives, cross-module constraints, and unresolved trade-offs. It must preserve dissent/uncertainty instead of forcing false consensus.

### 4.3 AUTO routing

`AUTO` becomes the normal default and chooses a stage chain rather than a single label.

Expected examples:

- ordinary substantive request: `OMNI -> META`;
- underspecified request: `OMNI`, stop for clarification when necessary, then `META`;
- software work: `OMNI -> META -> FORGE -> SIGMA`;
- comparison/reconciliation work: `OMNI -> META -> SIGMA`;
- simple already-complete request: `META` or no material rewrite when enhancement adds no value.

The router must be inspectable and provenance-bearing. It cannot silently add a high-impact capability or change the user's requested objective.

### 4.4 Compiler provider and privacy boundary

Automatic prompt compilation is **local-first**. The preferred compiler path uses an available local model/provider whose endpoint class is already verified as local.

A remote model may receive the literal original prompt for prompt compilation only when the operator has explicitly selected or enabled that remote provider for Prompt Intelligence. The native proposal flow must disclose that the original prompt will cross a remote provider boundary before the compilation request is sent. Selecting a remote provider for final task execution does not silently imply consent to use it for pre-approval prompt compilation.

Compiler-provider selection is separately provenance-bound from the final execution provider/model. Raw credentials never enter compiler prompts or proposal evidence. If no permitted compiler provider is available, CAPT must fall back to deterministic local analysis or present the original prompt for approval; it must not silently send the prompt elsewhere.

## 5. Prompt proposal and approval contract

Add an authoritative `PromptProposal` aggregate/projection bound to the existing approval system.

The proposal stores references/digests sufficient to reconstruct:

- literal original prompt;
- compiled proposed prompt;
- user-edited proposal when applicable;
- engine-chain outputs;
- target root/project identity;
- selected provider/model;
- requested/effective context budget;
- mode;
- requested capability envelope;
- verification contract;
- exact final model-visible assembly digest;
- exact outbound dispatch digest.

Approval remains one-use and expiring. Existing approval replay/mismatch protections continue to apply.

The approval screen must make it visually impossible to confuse "CAPT proposed this" with "you approved this."

## 6. Native macOS user experience

### 6.1 Composer

Normal chat defaults:

- **Prompt Intelligence: Auto** — enabled;
- **Software Development** — disabled;
- provider/model selector;
- response mode;
- context budget;
- human result verification enabled by default.

Expert disclosure exposes explicit stage policy (`AUTO`, `OFF`, or constrained manual stage selection) without forcing normal users to understand internal engine names.

### 6.2 Proposal sheet

Submitting a prompt does not immediately dispatch the model. CAPT opens a proposal sheet containing:

- **Original Prompt** — immutable, selectable/copyable;
- **Upgraded Execution Prompt** — separately editable;
- **What CAPT Changed** — concise semantic diff;
- **Why** — stage rationales and assumptions;
- **Engine Chain** — e.g. `OMNI -> META -> FORGE -> SIGMA`;
- **Capabilities Requested**;
- **Target Project/Root**;
- **Verification Contract**;
- unresolved questions/blockers;
- buttons: `Approve Upgrade`, `Edit`, `Use Original`, `Cancel`.

The UI never mutates the original composer text into the upgraded prompt.

### 6.3 Approval state

After approval, the conversation shows a compact receipt with proposal/approval digest prefixes and mode. Any subsequent change invalidates the receipt and returns the UI to proposal/review state.

## 7. Software Development Mode

Software Development Mode changes the execution contract, capability envelope, evidence requirements, and completion semantics. It is not a prompt preset.

### 7.1 Entry behavior

When enabled, AUTO uses at least:

`OMNI -> META -> FORGE -> SIGMA`

before approval unless a stage returns a clarification blocker.

The proposal sheet must show the planned project root/worktree, requested mutation capabilities, build/test/run proof strategy, and expected deliverable.

### 7.2 Workspace isolation

For an existing Git repository, CAPT creates or selects an isolated worktree/branch by default. It must not silently modify the user's active branch or foreign dirty worktree.

For a new project, CAPT creates a bounded project directory and initializes version control unless the user explicitly declines Git.

All writes must remain inside the approved project/worktree root and CAPT-owned staging/artifact areas. Symlink/path escapes fail closed.

### 7.3 Builder/integrator split

Forge becomes the governed **builder/orchestrator**, not an authority bypass. It decomposes the approved implementation contract into bounded tasks and requests existing ToolBroker/DriverHost capabilities for filesystem mutation, terminal execution, dependency operations, and project-specific test/build commands.

Sigma becomes the **adversarial integrator**. It examines architecture, module contracts, competing approaches, failed checks, incomplete acceptance criteria, and cross-component inconsistency. Sigma produces corrective proposals/tasks; it does not directly declare success.

The execution loop is:

```text
approved software contract
 -> isolated workspace
 -> Forge implementation task
 -> build/test/run evidence
 -> Sigma reconciliation/adversarial review
 -> corrective Forge task when required
 -> repeat within bounded iteration/resource policy
 -> CAPT verification/completion gate
```

A bounded iteration/resource limit must prevent infinite self-repair loops. Exhaustion yields an honest blocked/partial result with evidence.

### 7.4 Tooling

Software mode reuses the canonical CAPT tool/execution architecture. Initial supported terminal backends remain `local`, `ssh`, and `docker` where configured. Browser/runtime validation uses the configured browser automation/Chrome DevTools path where appropriate.

Forge/Sigma do not gain hidden shell or filesystem paths outside the existing governed tool broker/capability system.

## 8. "Working repository" completion contract

Software work cannot complete merely because files were generated or a model says it is done.

CAPT chooses an acceptance adapter based on project type and records which checks are applicable. At minimum, applicable proof must cover:

1. dependency resolution/install succeeds;
2. compile/build succeeds when the project has a build step;
3. automated tests pass, including newly required acceptance tests;
4. the produced application/server/CLI actually launches or executes;
5. critical user flow(s) receive a smoke/E2E check appropriate to the product;
6. no unintended TODO-only implementations, placeholder screens, stubbed success paths, or mocks remain in production code paths;
7. packaging/install/export succeeds when the requested deliverable requires it;
8. generated/modified repository is clean enough for continued development and its change set is inspectable;
9. required evidence and verification identities are bound to the exact source/worktree state.

Project-specific examples:

- native macOS: Swift build/tests, strict-concurrency gate where configured, application launch, critical native flow smoke test;
- web: production build, unit/integration tests, real local server, browser smoke/E2E validation;
- CLI: package/install, executable invocation, representative command behavior;
- service/API: process start, health/readiness, contract/API smoke tests;
- library: build/package plus representative consumer/import test.

If an acceptance check cannot be executed, CAPT must report the exact verification debt and cannot label the corresponding criterion PASS.

## 9. Promotion of existing Labs Forge/Sigma work

Do not mechanically merge the old Labs PR stack.

Implementation must selectively port/reconcile the proven safe semantics from the separate Labs lineage:

- bounded canonical-root validation;
- secret/binary exclusion and scan limits;
- repository archaeology;
- lexical/gap evidence with conservative epistemic labels;
- SIGMA implementation briefs;
- ForgeProof-style rubric concepts where useful;
- RuntimeService -> DriverRun -> artifact -> Claim/Evidence provenance pattern.

These become Core prompt/software-development capabilities behind shared contracts. Edition-specific runtime state, separate authority, donor branding, or obsolete provider spine must not be imported.

The existing Labs expert screen may remain as an optional instrument surface, but normal software development must not require manually composing JSON Lab requests.

## 10. Failure handling

Prompt compilation fails closed to the original prompt, not to silent execution. The UI must distinguish:

- clarification required;
- compiler stage unavailable;
- proposal rejected by policy;
- proposal ready for approval;
- approval expired/invalidated;
- execution blocked by capability/policy;
- implementation partial/blocked;
- verification incomplete;
- completed and verified.

If a specialist stage/model is unavailable, CAPT may use a documented fallback only when that fallback does not weaken the requested authority/verification contract. The user sees the fallback.

Provider/model output remains untrusted until admitted through CAPT evidence/verification boundaries.

## 11. Security and privacy

- Prompt stages receive the minimum required context.
- Secret references remain references; raw secrets do not enter prompt proposals/evidence.
- Original and compiled prompt persistence uses the existing encrypted authoritative storage boundary where sensitive state applies.
- Software mode capabilities are scoped to the approved root/worktree and tool set.
- Network access is explicit in the capability envelope.
- External package downloads/provider calls remain subject to resource and billing controls.
- Prompt compiler output cannot escalate its own capabilities.
- Any proposal attempting to change target root, requested tools, or destructive scope requires a new human approval.

## 12. Shared-surface parity

Runtime contracts are source of truth. Native macOS and TUI consume the same proposal/approval APIs.

The TUI should migrate away from in-place prompt replacement to the same original/proposal distinction after the RuntimeService compiler exists.

Native macOS is the primary product-quality surface for this tranche. No feature is considered complete if only the TUI exposes it.

## 13. Testing and verification

Implementation follows TDD at authority boundaries.

Required Python/RuntimeService coverage includes:

- original prompt immutability;
- deterministic/reconstructable proposal identity;
- stage routing and clarification behavior;
- proposal edit invalidates prior digest;
- use-original and use-upgraded produce distinct exact bindings;
- no run before explicit human approval;
- approval expiry/replay/mismatch rejection;
- software-mode capability/worktree containment;
- symlink/path escape rejection;
- Forge/Sigma advisory outputs cannot self-verify or complete;
- bounded repair-loop exhaustion;
- completion gate refuses missing build/run/test evidence;
- project-type acceptance adapters;
- provenance/evidence reconstruction.

Required Swift coverage includes:

- Prompt Intelligence defaults to Auto;
- native path no longer hardcodes enhancement OFF;
- proposal sheet correctly displays original vs proposed text;
- edit/use-original/approve/cancel state transitions;
- modifying any bound setting invalidates approval;
- Software Development toggle changes requested mode/capability/verification contract;
- asynchronous proposal/run results remain bound to originating chat/session;
- UI never reports completion more strongly than RuntimeService state.

Release verification includes:

- full Python suite;
- contract generation/drift;
- TypeScript parity if contracts change;
- Swift normal tests;
- strict concurrency + warnings-as-errors;
- ThreadSanitizer for the affected native state paths where supported;
- `swift build --product CAPTNativeMac`;
- Release Security exact-head PASS;
- real native dogfood of normal prompt upgrade/approval;
- real native software-mode dogfood against a disposable sample repo;
- independent CAPT-governed Qwen 3.8/MLX adversarial review of the final exact tree.

## 14. Acceptance scenarios

### Scenario A — normal prompt

User enters a substantive request. CAPT automatically produces an OMNI/META proposal. The original remains unchanged. The user sees the upgrade and rationale, approves it, and only the exact approved assembly runs.

### Scenario B — user rejects upgrade

User chooses Use Original. CAPT binds and executes the exact original prompt after approval. No generated proposal silently remains in the execution path.

### Scenario C — user edits upgrade

User edits the proposed text. The prior proposal approval identity is invalidated. CAPT binds the edited bytes and requires fresh approval.

### Scenario D — software project

User enables Software Development and requests an application. CAPT compiles an OMNI/META/FORGE/SIGMA execution contract, shows worktree/capabilities/acceptance criteria, receives approval, creates the isolated workspace, implements, builds, tests, launches, smoke-tests, iterates on failures, and returns a working continuation-ready repository plus evidence.

### Scenario E — software cannot be proven runnable

Build or runtime validation cannot be completed. CAPT returns BLOCKED/PARTIAL with the exact failed/missing checks and never labels the repository complete.

## 15. Migration and rollout

1. Add shared RuntimeService prompt-proposal/compiler contracts without changing existing execution behavior.
2. Implement real OMNI/META orchestration and exact proposal approval binding.
3. Move TUI to the new proposal contract while preserving compatibility.
4. Add native Swift proposal UX and remove hardcoded `promptEnhancement: OFF`.
5. Promote/reconcile safe Forge/Sigma analysis semantics into Core.
6. Add Software Development Mode workspace/capability/execution loop.
7. Add project-type verification adapters and runnable-repo completion gate.
8. Dogfood native normal mode and software mode.
9. Run independent CAPT/Qwen 3.8 review, hosted CI, Release Security, then merge.

Each step must leave the runtime usable and must not require the later steps to preserve existing authority invariants.

## 16. Explicit non-goals for this tranche

- autonomous publishing/deployment to production without separate approval;
- automatic merge into the user's active branch;
- hidden access to arbitrary host files or credentials;
- claiming Forge/Sigma output is verification by module name;
- replacing RuntimeService/EventStore with a Labs runtime;
- unlimited recursive self-improvement loops;
- universal support for every build system on first release;
- treating generated code as complete without runnable proof.

## 17. Definition of done

This tranche is done only when the native macOS app can demonstrate both:

**Prompt Intelligence:** literal prompt -> automatic governed upgrade -> visible review -> explicit approval -> exact-bound execution.

**Software Development:** literal software request -> governed OMNI/META/FORGE/SIGMA contract -> visible capability/acceptance review -> explicit approval -> isolated implementation -> build/test/launch/smoke evidence -> CAPT verification -> working repository handoff.

No intermediate model, engine, UI, or tool may bypass CAPT authority to reach either terminal state.
