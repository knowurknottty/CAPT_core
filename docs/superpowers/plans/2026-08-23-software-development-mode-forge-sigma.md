# Software Development Mode + Forge/Sigma Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a native macOS Software Development Mode that turns an approved software contract into an isolated, governed, actually runnable repository using Forge as builder, Sigma as adversarial integrator, and CAPT as the only authority/completion gate.

**Architecture:** Build on Plan A's PromptProposal approval. Promote safe Forge repository-intelligence semantics into Core, add a bounded software orchestration layer that emits validated tool actions, execute those actions only through scoped CAPT tools/workspaces, run project-specific acceptance adapters, and require evidence-backed build/test/launch/smoke success before completion.

**Tech Stack:** Python RuntimeService/EventStore, JSON Schema contracts, Git worktrees, CAPT ToolRequest/ToolResult and capability leases, local/ssh/docker terminal backends where configured, Swift 6/SwiftUI, XCTest, project-native build/test tools.

**Spec:** `docs/superpowers/specs/2026-08-23-native-prompt-intelligence-software-development-mode-design.md`

**Prerequisite:** Plan A is merged or the implementation branch contains its exact verified PromptProposal/approval semantics.

## Global Constraints

- No model receives direct ungoverned shell/filesystem authority.
- Existing active branch/dirty worktree is never silently mutated.
- Every write/process/network action is scoped to the exact approved software proposal and workspace lease.
- Forge and Sigma produce plans/reviews; only CAPT executes tools, admits evidence, verifies criteria, and declares completion.
- Repair loops are bounded by rounds, wall clock, operations, tokens/cost, and cancellation.
- A generated repository is not complete until all applicable required runnable-proof checks PASS.

---

## File Map

**Create**
- `contracts/schema/software.schema.json` — software plan/action/acceptance/run contracts.
- `capt_runtime/software_dev/__init__.py`
- `capt_runtime/software_dev/models.py` — immutable orchestration models.
- `capt_runtime/software_dev/repository_intelligence.py` — safe Core port of Labs Forge scan/gap semantics.
- `capt_runtime/software_dev/workspace.py` — existing-repo worktree/new-project isolation.
- `capt_runtime/software_dev/tool_broker.py` — scoped file/process action executor.
- `capt_runtime/software_dev/forge.py` — structured implementation planner/builder stage.
- `capt_runtime/software_dev/sigma.py` — adversarial reconciliation stage.
- `capt_runtime/software_dev/acceptance.py` — adapter protocol and project detection.
- `capt_runtime/software_dev/adapters/{python,swiftpm,node,generic}.py`
- `capt_runtime/software_dev/orchestrator.py` — bounded Forge/Sigma execution loop.
- Python tests under `tests/capt_runtime/software_dev/`.
- `CAPTCoreDesktop/CAPTSoftwareDevelopment.swift`
- `CAPTNativeMac/Views/SoftwareDevelopmentControls.swift`
- `CAPTNativeMac/Views/SoftwareDevelopmentProgressView.swift`
- `CAPTNativeMac/Views/SoftwareHandoffView.swift`

**Modify**
- `contracts/schema/index.json`, `event.schema.json`, `checkpoint.schema.json`, `tool.schema.json`, and only the driver schema pieces proven necessary.
- Runtime command routing, capability/tool registry, prompt compiler FORGE/SIGMA stages, native store/chat flow/views, canonical docs, CI/security evidence mappings.
## Task 1: Promote safe Forge/Sigma repository intelligence into Core

- [ ] **Write RED Core tests from the proven Labs semantics.**

Create tests for canonical-root validation, symlink/path escape rejection, ignored/secret/binary exclusion, file/byte/depth limits, conservative token evidence, identifier normalization, repository archaeology, gap analysis, and SIGMA brief construction.

Use the behavior from PR #104/#108/#109/#110/#112 as donor evidence, not as merge authority. Tests must explicitly retain the epistemic labels: observed text is not implementation proof; `not_observed` is not proof of absence.

- [ ] **Port semantics into `repository_intelligence.py`.**

Do not import `capt_lab`, separate Lab state, donor runtime registration, or obsolete provider configuration. The Core module is pure bounded repository observation and returns typed advisory results.

- [ ] **Connect real FORGE/SIGMA prompt stages.**

Replace Plan A's software-stage-disabled routing with actual structured stages:
- FORGE consumes approved intent + bounded repository observation and emits acceptance-aware implementation requirements;
- SIGMA reconciles architecture/constraints and emits explicit dissent/tradeoffs.

Neither stage writes files or executes commands.

- [ ] **Run donor-regression and compiler tests.**

```zsh
python3 -m pytest tests/capt_runtime/software_dev/test_repository_intelligence.py tests/capt_runtime/test_prompt_compiler.py -q
```
Commit: `feat(forge): promote bounded repository intelligence into core`
## Task 2: Add software-run contracts and isolated workspace authority

- [ ] **Write RED schema/workspace tests.**

Require contracts for `SoftwareProjectKind`, `SoftwareAction`, `SoftwareActionPlan`, `SoftwareAcceptanceCheck`, `SoftwareAcceptanceResult`, `SoftwareRunSnapshot`, and bounded run state (`planned`, `executing`, `reviewing`, `awaiting_verification`, `completed`, `blocked`, `cancelled`).

Workspace tests must prove:
- existing Git repo creates an isolated worktree/branch outside the active dirty checkout;
- dirty active branch remains byte/Git-status unchanged;
- new project uses a bounded project root and initializes Git unless explicitly disabled in the approved proposal;
- root canonicalization and symlink escape fail closed;
- workspace descriptor/lease identity is bound into software-run state and capability conditions.

- [ ] **Implement `SoftwareWorkspaceService`.**

For existing repos, use `git worktree add` with a CAPT-owned branch name derived from software-run identity. Reject a requested worktree path already owned by a foreign worktree or outside approved workspace parent policy.

For new projects, create only the approved root and CAPT metadata/staging beneath it. Do not create files outside that root.

- [ ] **Persist software-run state.**

Add software-run events/stream only if needed for restart/recovery; if a new stream is added, extend StreamId, EventPayload/EventType, checkpoint versions, replay, and generated bindings in the same task.

- [ ] **Generate contracts and run workspace tests.**

```zsh
python3 contracts/tools/generate.py && python3 contracts/tools/check_drift.py
python3 -m pytest tests/capt_runtime/software_dev/test_workspace.py -q
```
Commit: `feat(software): add isolated software workspace authority`
## Task 3: Add governed software ToolBroker actions without weakening read-only drivers

- [ ] **Preserve the existing read-only external-driver boundary.**

Do **not** change `FilesystemPolicy.writesAllowed: false` or expand existing DriverWorkOrder read-only operations merely to let a model mutate code. Forge/Sigma remain planning/review stages; CAPT executes mutation through validated ToolRequests.

- [ ] **Write RED ToolBroker containment tests.**

Require at minimum these scoped operations:
```text
fs.read_file
fs.write_file
fs.delete_path
fs.make_directory
process.exec
```
`process.exec` accepts executable + argv + cwd, never an arbitrary shell string. Every operation requires the software workspace lease, exact root, idempotency identity, and applicable capability reservation.

Tests must reject absolute/relative path escapes, symlink escapes, writes outside root, cwd outside root, undeclared executable operations, revoked/expired lease, mismatched run/workspace IDs, and replay with changed arguments.

- [ ] **Implement `SoftwareToolBroker`.**

Use existing `ToolRequest`/`ToolResult`, capability reservation/finalization, effect taxonomy, and terminal backend contracts. Capture stdout/stderr as bounded/digested evidence; redact secrets from presentation/log surfaces.

- [ ] **Network remains separate.**

Dependency downloads are unavailable unless the approved proposal explicitly includes network capability/hosts. Local package caches may be used without converting that into unrestricted egress.
- [ ] **Verify local/ssh/docker routing does not bypass scope.**

The backend changes transport only; path/tool/capability validation occurs before backend dispatch and result reconciliation occurs afterward.

- [ ] **Run adversarial tool tests.**

```zsh
python3 -m pytest tests/capt_runtime/software_dev/test_tool_broker.py tests/capt_runtime/test_tool_* -q
```
Commit: `feat(software): add governed software tool broker`

## Task 4: Implement bounded Forge builder + Sigma integrator loop

- [ ] **Write RED orchestration tests with deterministic fake stage outputs.**

Prove:
- Forge returns a closed `SoftwareActionPlan`, never executable free-form prose;
- every planned action is validated against approved capabilities before execution;
- tool results are fed back as evidence, not trusted success claims;
- Sigma can accept, dissent, request evidence, or propose corrections;
- Sigma cannot directly execute an action or mark the run complete;
- corrective Forge rounds consume a bounded round budget;
- round/resource exhaustion yields `blocked` with exact outstanding criteria;
- cancellation stops new reservations/actions and reconciles any in-flight effect.

- [ ] **Implement structured Forge planning.**

Forge receives approved software contract, repository observation, current tree digest, prior tool evidence, acceptance register, and Sigma findings. Its JSON output contains ordered actions with rationale and expected evidence, plus no direct authority fields.
- [ ] **Implement Sigma review.**

Sigma receives source/tree digests, acceptance results, architecture summary, Forge plan/actions, and failures. It must enumerate unresolved requirements and contradictions explicitly. A clean Sigma review is advisory evidence, not the completion verdict.

- [ ] **Implement `SoftwareDevelopmentOrchestrator`.**

Default bounded policy:
```python
SoftwareLoopBudget(max_rounds=6, max_wall_seconds=3600, max_actions=200)
```
Cost/token limits remain constrained by the existing resource governor. Each round is persisted/reconstructable enough to resume or report exact partial state after restart.

- [ ] **Integrate RuntimeService commands.**

Add:
```text
start_software_development
get_software_development_status
cancel_software_development
```
`start_software_development` requires a consumed approval bound to a software-development PromptProposal and creates/uses only its approved workspace/capability envelope.

- [ ] **Run orchestration tests.**

```zsh
python3 -m pytest tests/capt_runtime/software_dev/test_orchestrator.py -q
```
Commit: `feat(software): add bounded forge sigma execution loop`
## Task 5: Add project acceptance adapters and hard completion gate

- [ ] **Write RED acceptance tests before adapters.**

Each adapter returns explicit `applicable / pass / fail / not_verified` checks with command/evidence identities. Completion must reject any required `fail` or `not_verified` check.

Required adapter coverage:
- Python package/CLI: dependency/install, tests, import/entrypoint invocation;
- SwiftPM/macOS: `swift build`, `swift test`, app/product launch where applicable;
- Node/web: dependency install, production build, tests, local server, browser/smoke hook;
- generic service/CLI/library fallback: declared build/test/run commands plus representative invocation.

- [ ] **Implement project detection conservatively.**

Detection uses repository files (`pyproject.toml`, `Package.swift`, `package.json`, executable/service metadata). Ambiguous projects require explicit adapter selection rather than guessing a PASS path.

- [ ] **Implement placeholder/stub production-path scan.**

Flag unresolved `TODO`, `FIXME`, deliberate placeholder screens/messages, unconditional stub success, and test mocks referenced by production entrypoints. Findings are review inputs; false positives must be adjudicable and never silently ignored.

- [ ] **Implement completion gate.**

`evaluate_software_completion(...)` may return `completed` only when every applicable required acceptance criterion has evidence-bound PASS and final workspace/source digest matches the tested tree.
A later write after the last successful acceptance check invalidates completion and requires the affected checks to run again.

- [ ] **Prove the gate refuses fake success.**

Tests must cover model says "done" with failing build, tests pass but app cannot launch, stale evidence after source change, missing smoke check, and exhausted repair loop. Every case remains blocked/partial.

- [ ] **Run adapter/completion tests.**

```zsh
python3 -m pytest tests/capt_runtime/software_dev/test_acceptance.py tests/capt_runtime/software_dev/test_completion_gate.py -q
```
Commit: `feat(software): require runnable repository proof`

## Task 6: Add first-class native Software Development Mode

- [ ] **Write RED Swift store/flow tests.**

Require:
- Software Development defaults OFF;
- enabling it changes prompt mode to `software_development` and AUTO stage chain to OMNI/META/FORGE/SIGMA;
- proposal review visibly includes workspace plan, write/process/network capabilities, loop budget, and acceptance contract;
- changing the toggle invalidates proposal/approval;
- execution progress remains bound to originating session/softwareRunID;
- UI never renders `Complete` unless RuntimeService software snapshot is completed with verified acceptance.
- [ ] **Create `CAPTSoftwareDevelopment.swift`.**

Decode software-run snapshot, round summaries, workspace identity, acceptance checks, outstanding blockers, and final handoff metadata as Sendable value types.

- [ ] **Add `SoftwareDevelopmentControls.swift`.**

The composer control is a first-class toggle, not an expert engine selector. When enabled, the store requests software mode in PromptProposal compilation and displays an explicit capability/verification badge.

- [ ] **Add progress and handoff views.**

`SoftwareDevelopmentProgressView` shows current round, Forge/Sigma phase, recent tool evidence, acceptance register, and blockers without leaking secrets or unbounded logs.

`SoftwareHandoffView` shows repository/worktree path, exact source digest, branch, acceptance checks, command results, unresolved debt, and safe next actions. It must not auto-merge or deploy.
- [ ] **Bind async state to originating chat.**

`CAPTOperatorStore` and workspace/session state key every compile/software status result by session ID and softwareRunID. Late results after navigation are stored only on the originating session or discarded if superseded.

- [ ] **Run full Swift tests/build.**

```zsh
cd capt_ui/surfaces/desktop_swift
swift test
swift test -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
swift build --product CAPTNativeMac
```
Commit: `feat(mac): add software development mode workflow`

## Task 7: Prove a real disposable repository end-to-end

- [ ] **Create deterministic dogfood fixture definitions, not mocked completion.**

Use at least one new-project fixture and one existing-repo fixture. The new-project fixture must require actual source creation, tests, package/build metadata, and executable behavior. The existing-repo fixture must contain a real defect requiring a code change while its original active checkout remains unchanged.
- [ ] **Dogfood through the native macOS app and real RuntimeService.**

For each fixture prove:
```text
literal request
 -> automatic OMNI/META/FORGE/SIGMA proposal
 -> visible software capabilities/acceptance contract
 -> human approval
 -> isolated workspace
 -> real writes/processes
 -> build/tests/run/smoke
 -> Sigma review/correction when needed
 -> CAPT completion evaluation
 -> handoff receipt
```
Capture session/proposal/approval/softwareRun/workspace/DriverRun or ToolExecution/evidence/verification IDs and exact source/tree digests. Do not capture raw secrets.

- [ ] **Assert active checkout isolation.**

Record Git status/tree digest of the donor existing repo before and after dogfood; they must match. All implementation changes remain in the CAPT-created worktree.

- [ ] **Assert truthful negative path.**

Run a fixture whose required runtime check is intentionally impossible. Verify the UI and RuntimeService return BLOCKED/PARTIAL with the missing check rather than `Complete`.

- [ ] **Commit dogfood tests/evidence adapters:** `test(software): prove runnable repo workflow`
## Task 8: Freeze Software Development tranche with exact-head evidence

- [ ] **Run complete Python/contracts/tool security suite.**

```zsh
python3 -m pytest -q
python3 contracts/tools/check_drift.py
node contracts/tools/ts_parity.mjs
git diff --check
```
Run focused capability/path/injection/resource/security rings separately so failures are attributable.

- [ ] **Run complete native gates.**

```zsh
cd capt_ui/surfaces/desktop_swift
swift test
swift test -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
swift build --product CAPTNativeMac
```
Run ThreadSanitizer on affected native async/session/software paths where supported and record unsupported conditions explicitly.

- [ ] **Run Release Security exact-head gate.**

New write/process/network capabilities must be reflected in the security catalog/evidence mapping where applicable. Do not preserve a green badge by marking newly applicable controls N/A.

- [ ] **Run CAPT-governed Qwen 3.8/MLX adversarial review.**

Require the reviewer to attack path/worktree escapes, capability escalation, arbitrary command injection, stale acceptance evidence, false completion, infinite repair loops, cross-chat state contamination, Forge/Sigma authority confusion, secret leakage, and remote-provider boundary mistakes.
- [ ] **Adjudicate required findings with executable proof.**

If review identifies a valid defect, add a failing regression test before the fix and rerun the relevant full gates. Never relabel a rejected/reasoning-only model run as review approval.

- [ ] **Update canonical docs after proof.**

Update current state, architecture, desktop/user guide, functionality matrix, release evidence, security, and PR topology so Core main—not the old Labs PR lineage—is the authority for Software Development Mode. Preserve donor PRs as historical provenance.

- [ ] **Open PR with immutable receipts and merge only exact green head.**

PR body must include exact head/tree, full Python/Swift counts, contract parity, Release Security decision/counts, positive and negative native dogfood receipts, Qwen review receipt, and residual platform/build-system limits.

After merge, create a fresh detached checkout of the actual merge SHA and repeat full Python/contracts/Swift build plus the hosted Release Security/M0-A checks for that merge SHA.

## Plan B Definition of Done

The native macOS app has a first-class Software Development toggle. An approved software request produces an isolated repository/worktree, executes only CAPT-validated write/process/network actions, iterates through bounded Forge build and Sigma adversarial review, and cannot report completion until the exact final source state has applicable dependency/build/test/launch/smoke/package evidence.

The user receives a continuation-ready repository and inspectable evidence. If any required check cannot be proven, the terminal state is BLOCKED/PARTIAL with exact debt—not a softened success claim.
