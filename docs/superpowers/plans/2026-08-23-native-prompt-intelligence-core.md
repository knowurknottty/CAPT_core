# Native Prompt Intelligence Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make RuntimeService the authoritative prompt compiler and give the native macOS app an automatic original→upgraded→human-approved→exact-bound execution flow.

**Architecture:** Add a durable PromptProposal stream and a RuntimeService-owned PromptCompiler with local-first OMNI/META stages. Preserve HumanApproval as the sole execution authorization boundary. Migrate TUI and native Swift to shared proposal APIs while retaining compatibility for old callers.

**Tech Stack:** Python 3.10+, JSON Schema generated Python/TypeScript contracts, RuntimeService/EventStore, provider drivers, Swift 6/SwiftUI, XCTest.

**Spec:** `docs/superpowers/specs/2026-08-23-native-prompt-intelligence-software-development-mode-design.md`

## Global Constraints

- Literal original prompt bytes are immutable provenance and are never replaced by compiled text.
- Prompt compilation is local-first; remote compilation requires separate explicit permission and disclosure.
- Prompt stages are analysis-only and gain no filesystem-write, shell-write, Git-write, verification, promotion, or completion authority.
- Human approval is one-use, expiring, and bound to exact prompt/provider/model/context/target/capability/verification bytes.
- Native macOS is the primary product surface; TUI parity is required but TUI-only completion is insufficient.
- Existing Release Security fail-closed semantics must remain intact.

---

## File Map

**Create**
- `contracts/schema/prompt.schema.json` — PromptProposal and compiler-stage contracts.
- `capt_runtime/aggregates/prompt_proposal.py` — event-sourced proposal state.
- `capt_runtime/prompt_compiler/__init__.py` — public compiler exports.
- `capt_runtime/prompt_compiler/models.py` — internal immutable compile request/result models.
- `capt_runtime/prompt_compiler/router.py` — inspectable AUTO stage routing.
- `capt_runtime/prompt_compiler/stages.py` — OMNI/META stage prompts and structured result validation.
- `capt_runtime/prompt_compiler/provider_runner.py` — bounded local-first model dispatch.
- `capt_runtime/prompt_compiler/service.py` — compiler orchestration and proposal construction.
- `tests/capt_runtime/test_prompt_proposal_aggregate.py`
- `tests/capt_runtime/test_prompt_compiler.py`
- `tests/capt_runtime/test_prompt_compiler_provider_policy.py`
- `capt_ui/surfaces/desktop_swift/Sources/CAPTCoreDesktop/CAPTPromptProposal.swift`
- `capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/PromptProposalSheet.swift`
- `capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/PromptIntelligenceControls.swift`

**Modify**
- `contracts/schema/index.json`, `contracts/schema/event.schema.json`, `contracts/schema/checkpoint.schema.json`, `contracts/schema/common.schema.json`
- `capt_runtime/prompt_approval.py`, `capt_runtime/model_approval_binding.py`, `capt_runtime/operator_provenance.py`
- `desktop/m1_command_service.py`, `desktop/capt_runtime_service.py`
- `capt_ui/operator/runtime.py`, `capt_ui/surfaces/tui/app.py`
- native `CAPTChatCoordinator.swift`, `CAPTChatFlow.swift`, `CAPTNativeChatWorkspace.swift`, `CAPTNativeSessionStore.swift`, `CAPTOperatorStore.swift`, `ChatView.swift`
- corresponding Python and Swift tests.
## Task 1: Add authoritative PromptProposal contracts and stream

- [ ] **Write RED contract/aggregate tests first.**

Add tests proving:
- a proposal preserves both literal `originalPrompt` and separately compiled `proposedPrompt`;
- their SHA-256 digests differ when compilation changes text;
- revisions never mutate the stored original prompt/digest;
- stream IDs accept `prompt_proposal-<id>` and reject malformed IDs;
- checkpoint manifests include prompt-proposal stream versions;
- generated Python and TypeScript bindings expose identical proposal shapes.

Run:
```zsh
python3 -m pytest tests/capt_runtime/test_prompt_proposal_aggregate.py -q
```
Expected: FAIL because PromptProposal contracts/aggregate do not exist.

- [ ] **Add schema types and events.**

`prompt.schema.json` must define at minimum `PromptMode`, `PromptStageName`, `PromptStageRecord`, `PromptCapabilityRequest`, `PromptVerificationContract`, and `PromptProposalSnapshot`.

Use proposal lifecycle events `PromptProposalCreated`, `PromptProposalRevised`, and `PromptProposalCancelled`; approval remains a separate HumanApproval stream rather than duplicating approval authority inside PromptProposal.
Required snapshot identity:
```python
proposal = {
    "proposalId": proposal_id,
    "originalPrompt": original,
    "originalPromptDigest": digest(original),
    "proposedPrompt": compiled,
    "proposedPromptDigest": digest(compiled),
    "mode": "normal",
    "stageChain": ["OMNI", "META"],
    "targetRoot": target_root,
}
```

- [ ] **Implement `PromptProposalAggregate`.**

It must apply only valid lifecycle transitions, preserve original bytes across revisions, reject revision after cancellation, and expose a reconstructable snapshot from EventStore replay.

- [ ] **Regenerate contracts and prove byte parity.**

Run:
```zsh
python3 contracts/tools/generate.py
python3 contracts/tools/check_drift.py
node contracts/tools/ts_parity.mjs
python3 -m pytest tests/capt_runtime/test_prompt_proposal_aggregate.py -q
```
Expected: all PASS and drift reports 11 generated files matching schema source.

- [ ] **Commit:** `feat(prompt): add durable prompt proposal contracts`
## Task 2: Implement real local-first OMNI/META PromptCompiler

- [ ] **Write RED compiler tests.**

Tests must prove:
- `AUTO` routes ordinary substantive work to `OMNI -> META`;
- underspecified work returns `clarification_required` instead of inventing intent;
- software signals select `OMNI -> META -> FORGE -> SIGMA` in routing metadata, while FORGE/SIGMA execution remains disabled until Plan B;
- explicit `OFF` produces a no-rewrite proposal whose original/proposed digests match;
- compiler output is structured, bounded, and rejects unknown keys/invalid stage names;
- no stage may add requested capabilities not derivable from user intent/mode policy.

Run:
```zsh
python3 -m pytest tests/capt_runtime/test_prompt_compiler.py -q
```
Expected: FAIL on missing compiler package.

- [ ] **Implement inspectable routing.**

`route_stages(request) -> tuple[PromptStageName, ...]` must be deterministic for identical normalized inputs and record a human-readable routing rationale.

- [ ] **Implement OMNI and META structured stage contracts.**

OMNI returns outcome/scope/inputs/outputs/constraints/success criteria/ambiguities. META converts resolved intent into an execution-grade prompt and verification contract without changing the objective.
Stage model responses must validate against a closed JSON shape before admission. Invalid/unparseable output is evidence of stage failure, not permission to guess.

- [ ] **Implement local-first provider policy.**

`PromptCompilerProviderPolicy.resolve(...)` must prefer a healthy verified-local endpoint. A remote provider is eligible only when `remoteCompilationAuthorized == true`; final execution-provider selection alone is insufficient consent.

Add tests that the policy:
```python
assert resolve(local_available=True, remote_allowed=False).endpoint_class == "local"
with pytest.raises(AuthorityViolation):
    resolve(local_available=False, remote_allowed=False, requested_remote="openrouter")
```

- [ ] **Run compiler stages through a bounded provider runner.**

Reuse existing provider transport/resource accounting. Compiler dispatch is analysis-only, receives no provider secrets, filesystem writes, shell tools, or hidden capability elevation, and records provider/model/stage/input/output digests.

- [ ] **Provide deterministic fallback.**

If no permitted compiler model is available, deterministic local analysis may return clarification/no-op proposal only. It must never silently send the original prompt remotely.

- [ ] **Run GREEN tests and commit.**

```zsh
python3 -m pytest tests/capt_runtime/test_prompt_compiler.py tests/capt_runtime/test_prompt_compiler_provider_policy.py -q
```
Commit: `feat(prompt): add governed omni meta compiler`
## Task 3: Bind proposal selection into existing HumanApproval authority

- [ ] **Write RED approval/security tests.**

Extend `test_prompt_approval_binding.py`, `test_prompt_approval_command.py`, and `test_prompt_approval_security.py` to prove:
- `compile_prompt_proposal` creates no execution approval;
- `request_prompt_proposal_approval` accepts exactly one selection: `upgrade`, `original`, or `edited`;
- edited bytes generate a distinct selected-prompt digest;
- approval binds proposal ID/version, selected prompt digest, provider/model, target root, context budget, mode, capabilities, verification contract, and dispatch digest;
- revising/cancelling a proposal invalidates approvals for older versions;
- prompt/provider/model/root/mode/capability mismatch fails closed before provider dispatch;
- one-use/expiry/replay guarantees remain unchanged.

Run targeted tests and record the expected RED failures before implementation.

- [ ] **Add RuntimeService commands.**

Expose through `desktop/m1_command_service.py`:
```text
compile_prompt_proposal
revise_prompt_proposal
cancel_prompt_proposal
request_prompt_proposal_approval
run_approved_prompt_proposal
```
All command metadata must remain human-authored where the existing approval boundary requires it.
- [ ] **Refactor approval binding around selected proposal bytes.**

`build_bound_model_operator_approval(...)` must receive both immutable original identity and the selected execution text. Cognitive provenance must record `originalHumanPromptDigest`, `proposalId`, `proposalVersion`, `selectedPromptKind`, and `selectedPromptDigest` separately.

The outbound model-visible assembly must contain the selected text, never both original and upgraded text unless the approved execution contract explicitly requests comparison.

- [ ] **Preserve compatibility commands.**

Keep `request_model_prompt_approval` and `run_approved_hermes_inspection` temporarily callable. Route legacy callers through an implicit `OFF/use_original` proposal so old TUI/scripts keep their authority semantics while surfaces migrate.

Compatibility code must be covered by regression tests and clearly marked for later removal only after all first-party surfaces use proposal APIs.

- [ ] **Verify no dispatch before human approval.**

Use a counting fake provider and assert compile/revise operations never increment final execution dispatch; only the exact approved run does.

- [ ] **Run focused and full runtime rings.**

```zsh
python3 -m pytest tests/capt_runtime/test_prompt_* tests/capt_runtime/test_model_operator.py tests/capt_runtime/test_operator_provenance.py -q
python3 -m pytest tests/capt_runtime -q
```
Commit: `feat(prompt): bind proposals into human approval`
## Task 4: Migrate the TUI from in-place ENHANCE to proposal review

- [ ] **Write RED TUI/operator tests.**

Update `tests/test_prompt_intelligence.py` and `tests/test_ui_operator_layer.py` so they require:
- AUTO is default;
- submitting a prompt creates a proposal instead of modifying the TextArea;
- original text remains byte-identical in the composer/session state;
- clarification blockers prevent approval;
- Use Original / Approve Upgrade / Edit Upgrade each call the shared RuntimeService proposal API;
- changing provider/model/context/mode invalidates the local proposal approval cursor.

- [ ] **Thin `prompt_intelligence.py`.**

Keep only local preview/fallback utilities and preference types. Remove its role as authoritative engine executor. The canonical engine chain/rationale comes from RuntimeService proposal receipts.

- [ ] **Replace `ENHANCE -> APPROVE -> RUN` implementation.**

The TUI may preserve keyboard-friendly controls, but its state machine becomes:
```text
DRAFT -> COMPILING -> REVIEWING -> APPROVAL_REQUIRED -> EXECUTING
```
with a separate original/proposal rendering rather than TextArea replacement.

- [ ] **Run TUI tests and commit.**

```zsh
python3 -m pytest tests/test_prompt_intelligence.py tests/test_ui_operator_layer.py -q
```
Commit: `feat(tui): adopt authoritative prompt proposals`
## Task 5: Add native Swift proposal models and session-bound coordinator flow

- [ ] **Write RED Swift model/coordinator tests.**

Extend `CAPTChatCoordinatorTests.swift`, `CAPTChatFlowTests.swift`, `CAPTNativeChatWorkspaceTests.swift`, and `CAPTNativeSessionStoreTests.swift` to require:
- native submission calls `compile_prompt_proposal`, never hardcoded `promptEnhancement: OFF`;
- proposal carries original/proposed text, digests, rationale, stage chain, target root, capability and verification summaries;
- proposal results are applied only to the session that originated them;
- navigation to another chat cannot attach a late proposal/run to the wrong session;
- editing bound settings invalidates proposal/approval state;
- persisted sessions restore proposal state without converting it into approval authority.

Run:
```zsh
cd capt_ui/surfaces/desktop_swift
swift test --filter CAPTChatCoordinatorTests
```
Expected: RED before new models/API exist.

- [ ] **Create `CAPTPromptProposal.swift`.**

Define Sendable value types for proposal receipt, stage records, selection (`upgrade`, `original`, `edited`), capability summary, verification contract summary, and compiler-provider disclosure. Decode RuntimeService receipts strictly; missing identity/digest fields are malformed responses.

- [ ] **Extend `CAPTChatFlow`.**

Add explicit phases `compilingProposal` and `reviewingProposal`; proposal review is not represented as an approval request.
- [ ] **Refactor `CAPTChatCoordinator`.**

Replace `requestApproval(objective:...)` as the first step with:
```swift
compileProposal(original:targetRoot:provider:model:options:) async throws -> CAPTPromptProposal
requestApproval(proposal:selection:editedText:) async throws -> CAPTPendingApproval
approveAndRun(_ pending: CAPTPendingApproval) async throws -> CAPTExecutionResult
```
The coordinator must pass `promptIntelligence=AUTO` by default and preserve compiler-provider consent separately from final execution provider/model.

- [ ] **Extend workspace/session persistence.**

`CAPTNativeChatWorkspace` owns proposal state per session. `CAPTNativeSessionStore` persists user-visible proposal information and digests, but restored state must still reconcile approval validity against RuntimeService before enabling execution.

- [ ] **Run Swift rings.**

```zsh
cd capt_ui/surfaces/desktop_swift
swift test --filter CAPTChatCoordinatorTests
swift test --filter CAPTChatFlowTests
swift test --filter CAPTNativeChatWorkspaceTests
swift test --filter CAPTNativeSessionStoreTests
```
Commit: `feat(mac): add session-bound prompt proposal flow`
## Task 6: Build native Prompt Intelligence controls and proposal sheet

- [ ] **Write RED view/store tests before UI implementation.**

Add store/state tests proving:
- Prompt Intelligence defaults to Auto for new chats;
- remote compiler permission defaults off and is surfaced separately;
- proposal compilation never auto-approves;
- Approve Upgrade, Use Original, edited approval, and Cancel produce distinct state transitions;
- any bound-setting change clears pending approval;
- UI completion labels never exceed RuntimeService task/verification state.

- [ ] **Extract composer controls from `ChatView.swift`.**

Create `PromptIntelligenceControls.swift` and keep `ChatView` focused on layout/composition. Primary controls:
- Prompt Intelligence `Auto / Off`;
- expert disclosure for explicit stage policy;
- compiler-provider disclosure/remote permission when relevant.

Do not add Software Development behavior in this task; Plan B owns that toggle and contract.

- [ ] **Create `PromptProposalSheet.swift`.**

Render Original Prompt and Upgraded Execution Prompt as separate sections, plus semantic changes, rationale, stage chain, requested capabilities, target root, verification contract, compiler provider boundary, and unresolved questions.
Required buttons: `Approve Upgrade`, `Edit`, `Use Original`, `Cancel`. Editing changes proposal-selection identity and requires fresh approval.

- [ ] **Integrate with `CAPTOperatorStore`.**

The store launches compile work asynchronously, tags every result with originating session ID, shows compiling/reviewing/approval/execution phases, and ignores stale results after chat/provider/model/root changes.

- [ ] **Verify macOS UI architecture.**

Keep process/runtime calls in services/coordinator, state in store/workspace, and proposal rendering in focused SwiftUI views. Do not move socket/process logic into `ChatView` or the proposal sheet.

- [ ] **Run Swift tests, strict build, and app build.**

```zsh
cd capt_ui/surfaces/desktop_swift
swift test
swift test -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
swift build --product CAPTNativeMac
```

- [ ] **Dogfood normal prompt flow against disposable runtime state.**

Prove literal prompt -> automatic local OMNI/META proposal -> visible review -> approval -> exact-bound run -> task awaiting verification/verified according to actual runtime state. Capture proposal, approval, and DriverRun IDs plus digests without secrets.

- [ ] **Commit:** `feat(mac): ship prompt intelligence proposal experience`
## Task 7: Freeze Prompt Intelligence tranche with full verification

- [ ] **Run complete deterministic gates on the exact tree.**

```zsh
python3 -m pytest -q
python3 contracts/tools/check_drift.py
node contracts/tools/ts_parity.mjs
git diff --check
cd capt_ui/surfaces/desktop_swift && swift test
swift test -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
swift build --product CAPTNativeMac
```
All applicable commands must exit 0; record exact counts and skipped-test reasons.

- [ ] **Run affected native ThreadSanitizer coverage where supported.**

Use the repo's existing Swift TSan invocation. Any sanitizer failure blocks the tranche; unsupported environment must be reported explicitly rather than relabeled PASS.

- [ ] **Run Release Security locally and on hosted exact head.**

The prompt compiler may not weaken the existing 21-control gate, secret exclusion, billing assurance, encrypted state, or exact-head evidence semantics.

- [ ] **Run independent CAPT-governed Qwen 3.8/MLX adversarial review.**

Ask the reviewer specifically to attack original-prompt immutability, remote pre-approval disclosure, proposal/approval digest binding, session cross-contamination, replay, and any path that executes without exact human approval.

- [ ] **Adjudicate every required review finding with tests.**

No review finding is closed by prose alone when executable proof is possible.
- [ ] **Update canonical docs only after exact-head proof exists.**

Update `README.md`, `docs/CURRENT_STATE.md`, `docs/RELEASE_EVIDENCE.md`, `docs/SECURITY.md`, `docs/DESKTOP.md`, and `docs/USER_GUIDE.md` with immutable evidence references. Preserve historical blocked/older evidence as historical.

- [ ] **Open PR and require hosted gates.**

PR must name exact head SHA, full Python/Swift counts, compiler dogfood receipt, Qwen review receipt, M0-A result, Release Security result, and any explicit residual limitations.

Do not merge until the exact PR head is green and mergeability is resolved. After merge, verify actual merge commit again.

## Plan A Definition of Done

The native macOS application, TUI, and RuntimeService share one proposal contract. A normal user can type a prompt once and receive an automatic local-first OMNI/META upgrade without losing the original. CAPT visibly presents that proposal, requires an explicit original/upgraded/edited selection and human approval, binds the exact selection to one-use execution identity, and cannot dispatch a final task outside that approval.

Software Development routing may be visible in compiler metadata at this point, but no UI or runtime may claim the runnable-repository workflow until Plan B is complete and verified.
