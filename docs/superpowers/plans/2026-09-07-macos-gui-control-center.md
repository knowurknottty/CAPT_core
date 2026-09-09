# CAPT macOS GUI Control Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver verified Skills, a real Settings control center, and end-to-end filesystem/shell/provider-network authority in the regular CAPT macOS GUI, then prepare the functional surface for visual refinement.

**Architecture:** SwiftUI persists operator intent only. RuntimeService normalizes and freezes that intent into HumanApproval; dispatch revalidates it. Any model-requested filesystem or shell operation is translated into a CAPT ToolRequest and executed through ToolBroker, never directly by ProviderDriver.

**Tech Stack:** SwiftUI/SwiftPM, Python 3.12, CAPT RuntimeService/EventStore/ToolBroker, OpenAI-compatible provider APIs, Ollama chat API.

**Spec:** `docs/superpowers/specs/2026-09-07-macos-gui-control-center-design.md`

## Global Constraints
- Never create a second authority path in SwiftUI or ProviderDriver.
- File mutation, shell execution, and remote provider use remain independently gated.
- Default file mutation and shell authority are false.
- Generic web-fetch tooling is out of scope for this tranche; provider-network authority must be labeled truthfully.
- Preserve macOS 13 deployment compatibility already declared by the package.
- Do not install over the user's existing CAPT.app until all verification gates are green.

---

### Task 1: Finish Skills surface and approval propagation
**Files:** `CAPTManagedSkills.swift`, `SkillsView.swift`, `CAPTOperatorStore.swift`, `CAPTChatCoordinator.swift`, `CAPTBackgroundRuntime.swift`, `prompt_proposals.py`, `capt_runtime_service.py`, associated Python/Swift tests.
- [ ] Add/confirm failing tests for managed-skill metadata decoding and manual/off approval payload propagation.
- [ ] Verify RED.
- [ ] Finish the Skills UI and route it in sidebar/content.
- [ ] Implement only the code required by tests.
- [ ] Run focused Python + Swift tests and commit.

### Task 2: Settings profile model and real control center
**Files:** new Swift settings model/view plus store wiring and focused tests.
- [ ] Add failing tests for filesystem scope normalization, high-risk full scope, shell/file-mutation/provider-network persistence, and approval invalidation semantics.
- [ ] Verify RED.
- [ ] Implement `CAPTExecutionAuthoritySettings` and `SettingsView` with project/custom/full folder selection and explicit warnings.
- [ ] Wire settings into prompt compilation/approval intent without granting authority locally.
- [ ] Run focused Swift tests and commit.

### Task 3: Runtime authority normalization and approval binding
**Files:** new `capt_runtime/model_authority.py`, `prompt_approval.py`, `model_approval_binding.py`, `prompt_proposals.py`, `capt_runtime_service.py`, tests.
- [ ] Add failing Python tests for profile normalization, path validation, risk classification, remote-provider denial, binding immutability, and no post-approval widening.
- [ ] Verify RED.
- [ ] Implement the normalized runtime authority profile.
- [ ] Freeze it into HumanApproval and PreparedApprovedModelExecution.
- [ ] Revalidate provider endpoint and scope at preparation/dispatch.
- [ ] Run focused Python tests and commit.

### Task 4: CAPT-governed provider tool loop
**Files:** `drivers/provider.py`, new model-tool bridge module, `capt_runtime_service.py`, ToolBroker integration tests.
- [ ] Add failing tests proving file read/search go through ToolBroker, scope escape is rejected, write requires mutation authority, shell requires shell authority, and remote provider is rejected under local-only before HTTP dispatch.
- [ ] Verify RED.
- [ ] Implement tool schemas + OpenAI/Ollama tool-call decoding.
- [ ] Translate each call into canonical ToolRequest bound to task-specific grants/leases and execute through ToolBroker.
- [ ] Return tool results to the model loop; cap iterations and fail closed on malformed calls.
- [ ] Run focused + regression Python tests and commit.

### Task 5: Functional integration verification
- [ ] Run prompt compiler, managed skills, approval/security, ToolBroker/provider, and macOS Swift suites.
- [ ] Build the SwiftPM GUI.
- [ ] Launch only the worktree build and verify process startup.
- [ ] Run a disposable-scope live smoke matrix for read/write/shell/provider-network gates.
- [ ] Record exact pass/fail evidence; do not claim skipped live checks.

### Task 6: Inversion Labs visual-language pass
**Files:** native macOS views/support only after Tasks 1-5 are green.
- [ ] Capture current worktree UI for baseline.
- [ ] Apply one coherent visual system to Chat, Missions, Skills, Settings, sidebar, cards, typography, spacing, motion, and density without changing authority semantics.
- [ ] Build, launch, inspect, and regression-test.
- [ ] Commit separately from functional authority work.
