# CAPT Public Release Tranche Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved public-release tranche as six independently testable subsystems without weakening CAPT RuntimeService authority.

**Architecture:** Secure Intake is the dependency root for file bytes. Projects, result presentation, composer context, Deep Research, and Cohort Council consume explicit references/configuration but remain Operator Plane/UI concerns until RuntimeService admits consequential work. Each subsystem has its own implementation plan and review gate.

**Tech Stack:** Python 3.12+ CAPT operator/runtime modules; Swift 6 / SwiftUI macOS native client; CryptoKit/Keychain; SQLite/EventStore where already canonical; JSON Schema generated contracts; pytest; Swift Testing/XCTest; existing `capt-ui` CLI bridge.

**Spec:** `docs/superpowers/specs/2026-08-19-public-release-quarantine-projects-council-design.md` and `docs/superpowers/specs/2026-08-19-public-release-composer-parity-contract.md`

## Global Constraints

- Base implementation lineage is the approved design head `8c8241f885fdd0565ced44e35efcc24f862d3a43`.
- Uploaded regular files never flow picker -> model; bytes enter Secure Intake first.
- `NO_KNOWN_INDICATORS` never means proven safe.
- Steganography checks report indicators/coverage, never universal absence.
- Project membership is context eligibility, not RuntimeService authority.
- Project Skills remain subject to Skill Foundry lifecycle/permissions.
- Selecting a Workspace never implies write authority.
- Council majority is not verification.
- Cohort != Vessel.
- `MAX_DISTINCT_COHORTS = 10`.
- `MAX_LOGICAL_VESSELS = 111`.
- 111 logical Vessels never implies 111 concurrent processes.
- Public output defaults to human-readable rendering; raw JSON is one interaction away.
- Search and Deep Research are distinct modes; Deep Research receives a larger governed wall-clock/retrieval envelope.
- RuntimeService remains the only consequential execution authority.

---

## Release Dependency Graph

```text
A Secure Intake / Quarantine
   ├──> B Human-First Results
   ├──> C Projects
   │      └──> D Composer Context Palette
   │               └──> E Search + Deep Research Governance
   └────────────────────> F Cohort Council

B also feeds scan/results/project/council rendering.
```

## Plan Files

1. `docs/superpowers/plans/2026-08-19-secure-intake-quarantine-implementation-plan.md`
2. `docs/superpowers/plans/2026-08-19-human-first-results-implementation-plan.md`
3. `docs/superpowers/plans/2026-08-19-projects-implementation-plan.md`
4. `docs/superpowers/plans/2026-08-19-composer-context-palette-implementation-plan.md`
5. `docs/superpowers/plans/2026-08-19-search-deep-research-governance-implementation-plan.md`
6. `docs/superpowers/plans/2026-08-19-cohort-council-implementation-plan.md`

## File Structure Lock

New Python/operator responsibilities:

```text
capt_ui/operator/quarantine.py          intake store + state machine
capt_ui/operator/quarantine_scan.py     bounded scanner orchestration/adapters
capt_ui/operator/projects.py            project metadata store and references
capt_runtime/workload_budget.py         governed wall-clock/retrieval profiles
capt_runtime/council.py                 council plan validation/admission helpers
```

New Swift responsibilities:

```text
CAPTCoreDesktop/CAPTQuarantineModels.swift
CAPTCoreDesktop/CAPTProjectModels.swift
CAPTCoreDesktop/CAPTResultPresentation.swift
CAPTCoreDesktop/CAPTComposerContext.swift
CAPTCoreDesktop/CAPTCouncilModels.swift
CAPTNativeMac/Views/AttachmentQuarantineView.swift
CAPTNativeMac/Views/ProjectView.swift
CAPTNativeMac/Views/ResultContentView.swift
CAPTNativeMac/Views/ComposerCapabilityMenu.swift
CAPTNativeMac/Views/CouncilBuilderView.swift
```

Existing files modified only where their current responsibility already owns the integration point:

```text
capt_ui/operator/cli.py or current capt-ui entrypoint
capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Services/CAPTOperatorCLI.swift
capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Services/CAPTBackgroundRuntime.swift
capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Stores/CAPTOperatorStore.swift
capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/ChatView.swift
capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/SidebarView.swift
capt_ui/surfaces/desktop_swift/Sources/CAPTCoreDesktop/CAPTNativeSessionStore.swift
capt_runtime/model_approval_binding.py
desktop/capt_runtime_service.py
```

Do not turn `CAPTOperatorStore.swift`, `ChatView.swift`, or `desktop/capt_runtime_service.py` into catch-all implementations. New domain logic belongs in the focused files above.

---

### Task 1: Establish release branch/worktree and baseline

**Files:**
- Read: both approved specs.
- No implementation files change in this task.

**Interfaces:**
- Consumes: design head `8c8241f885fdd0565ced44e35efcc24f862d3a43`.
- Produces: isolated implementation worktree/branch and baseline test evidence.

- [ ] **Step 1: Create an isolated worktree from the approved design head**

```bash
git worktree add .worktrees/public-release-tranche -b feat/public-release-tranche-r1 8c8241f885fdd0565ced44e35efcc24f862d3a43
cd .worktrees/public-release-tranche
```

- [ ] **Step 2: Verify exact lineage and cleanliness**

```bash
test "$(git rev-parse HEAD)" = "8c8241f885fdd0565ced44e35efcc24f862d3a43"
git status --short --branch
```

Expected: clean worktree on `feat/public-release-tranche-r1`.

- [ ] **Step 3: Run Python baseline alone**

```bash
python -m pytest -q
```

Expected: repository baseline pass; record exact passed/skipped/deselected counts.

- [ ] **Step 4: Run Swift baseline alone**

```bash
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```

Expected: zero failures; record intentional live-runtime skips separately.

- [ ] **Step 5: Commit only if worktree metadata/docs changed intentionally**

No source commit is required for a clean baseline.

---

### Task 2: Execute Secure Intake / Quarantine plan

**Files:**
- Plan: `docs/superpowers/plans/2026-08-19-secure-intake-quarantine-implementation-plan.md`

**Interfaces:**
- Consumes: existing Artifact/Workspace containment helpers and Operator CLI patterns.
- Produces: `QuarantineRecord`, `ScanReport`, `FileReference`, CLI/Swift intake surfaces.

- [ ] **Step 1: Execute the Secure Intake plan task-by-task**

Use TDD and one reviewable commit per task in the subsystem plan.

- [ ] **Step 2: Run subsystem acceptance**

Required proof includes hostile filename/path handling, archive traversal/bomb limits, EXIF/metadata output, stego-coverage language, scanner-unavailable semantics, and zero picker-to-model bypass.

- [ ] **Step 3: Freeze interface digests/names consumed by later plans**

Do not begin Projects or Composer file attachment integration until `FileReference` serialization and disposition semantics are stable and tested.

---

### Task 3: Execute Human-First Results plan

**Files:**
- Plan: `docs/superpowers/plans/2026-08-19-human-first-results-implementation-plan.md`

**Interfaces:**
- Consumes: existing CAPT result envelopes plus Secure Intake scan reports.
- Produces: human/technical/raw rendering model and exact-copy code block component.

- [ ] **Step 1: Execute plan with Swift-first TDD**
- [ ] **Step 2: Verify raw JSON is collapsed by default and exactly one interaction away**
- [ ] **Step 3: Verify code-block copy preserves literal content and excludes surrounding prose**
- [ ] **Step 4: Verify accessibility labels for Copy and Raw details**

---

### Task 4: Execute Projects plan

**Files:**
- Plan: `docs/superpowers/plans/2026-08-19-projects-implementation-plan.md`

**Interfaces:**
- Consumes: `FileReference`, Skill Foundry IDs, chat session IDs, Workspace descriptors.
- Produces: versioned encrypted/private Project store and Project context eligibility model.

- [ ] **Step 1: Execute project persistence/model tasks**
- [ ] **Step 2: Execute Project Customize surface tasks**
- [ ] **Step 3: Execute chat context-menu membership tasks**
- [ ] **Step 4: Prove Project membership alone changes no RuntimeService ledger state**

---

### Task 5: Execute Composer Context Palette plan

**Files:**
- Plan: `docs/superpowers/plans/2026-08-19-composer-context-palette-implementation-plan.md`

**Interfaces:**
- Consumes: Projects, Quarantine, Workspace selection, model selector.
- Produces: explicit pre-send capability chips and context-selection draft.

- [ ] **Step 1: Add literal parity inventory from the companion contract**
- [ ] **Step 2: Route Attach Files through Secure Intake only**
- [ ] **Step 3: Add Folder/Repo Workspace, Active Apps, Screenshots, Clipboard selection, Project, model, voice controls**
- [ ] **Step 4: Prove removing a chip removes the corresponding execution input before approval binding**

---

### Task 6: Execute Search + Deep Research Governance plan

**Files:**
- Plan: `docs/superpowers/plans/2026-08-19-search-deep-research-governance-implementation-plan.md`

**Interfaces:**
- Consumes: composer mode selection and RuntimeService approval/admission.
- Produces: workload profile IDs, bounded wall-clock/retrieval budgets, research provenance.

- [ ] **Step 1: Implement workload budget contracts before changing provider timeout behavior**
- [ ] **Step 2: Keep interactive chat at the existing bounded profile**
- [ ] **Step 3: Add separate Search and Deep Research profiles with explicit ceilings**
- [ ] **Step 4: Prove a long-context review can receive a larger admitted wall-clock budget without silently changing all provider calls**

---

### Task 7: Execute Cohort Council plan

**Files:**
- Plan: `docs/superpowers/plans/2026-08-19-cohort-council-implementation-plan.md`

**Interfaces:**
- Consumes: provider/model registry, workload budgets, ContextPack eligibility, ResultPresentation.
- Produces: validated Council plan, bounded Vessel schedule, dissent-preserving synthesis envelope.

- [ ] **Step 1: Implement immutable Council model + hard-limit validation**
- [ ] **Step 2: Implement UI builder without dispatch**
- [ ] **Step 3: Implement RuntimeService governed Council admission/execution**
- [ ] **Step 4: Prove majority != verification and dissent survives synthesis**
- [ ] **Step 5: Prove 111 logical Vessels are scheduled under resource concurrency ceilings rather than launched simultaneously**

---

### Task 8: Cross-subsystem release acceptance

**Files:**
- Modify: release acceptance documentation/evidence manifest only after all subsystems pass.

**Interfaces:**
- Consumes: all six subsystem acceptance packets.
- Produces: release-candidate evidence packet.

- [ ] **Step 1: Run Python suite alone**

```bash
python -m pytest -q
```

Expected: zero failures.

- [ ] **Step 2: Run Swift suite alone**

```bash
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```

Expected: zero failures; intentional live skips enumerated.

- [ ] **Step 3: Run contract drift check**

```bash
python contracts/tools/check_drift.py
```

Expected: clean generated-contract drift.

- [ ] **Step 4: Run security/privacy acceptance scenarios**

At minimum: malicious archive, symlink escape, executable upload, malformed image, EXIF GPS image, metadata-free image, scanner missing, Project-only context, workspace read-only selection, clipboard selection/removal, Council 10/111 limits, Deep Research budget, raw JSON disclosure, exact-copy code.

- [ ] **Step 5: Verify authoritative ledger separation**

Project edits, file scanning, capability-menu changes, prewarm, and presentation toggles must not create Mission/Task/DriverRun/Evidence state. Consequential dispatch must still create canonical RuntimeService state.

- [ ] **Step 6: Commit release acceptance evidence**

```bash
git add docs reports
ngit commit -m "test: record public release tranche acceptance"
```

Correct the accidental `ngit` typo before execution; the intended command is `git commit -m "test: record public release tranche acceptance"`.
