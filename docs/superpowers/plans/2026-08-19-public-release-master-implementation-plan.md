# CAPT Public Release Tranche Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved public-release tranche as six independently testable subsystems without weakening CAPT RuntimeService authority.

**Architecture:** Secure Intake is the dependency root for file bytes. Projects, result presentation, composer context, Search/Deep Research, and Cohort Council consume explicit references/configuration but remain Operator Plane/UI concerns until RuntimeService admits consequential work. Each subsystem has its own implementation plan and review gate.

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
capt_ui/operator/quarantine_scan.py     scanner orchestration + sandbox launcher
capt_ui/operator/quarantine_worker.py   isolated format/scanner worker
capt_ui/operator/quarantine_archive.py  bounded archive inspection
capt_ui/operator/quarantine_media.py    metadata/stego indicator inspection
capt_ui/operator/project_context.py     deterministic Project context references
capt_runtime/workload_budget.py         governed wall-clock/retrieval profiles
capt_runtime/research.py                Search/Deep Research plan + provenance
capt_runtime/council.py                 Council validation/planning/execution helpers
```

New Swift responsibilities:

```text
CAPTCoreDesktop/CAPTQuarantineModels.swift
CAPTCoreDesktop/CAPTProjectModels.swift
CAPTCoreDesktop/CAPTEncryptedProjectStore.swift
CAPTCoreDesktop/CAPTResultPresentation.swift
CAPTCoreDesktop/CAPTComposerContext.swift
CAPTCoreDesktop/CAPTResearchModels.swift
CAPTCoreDesktop/CAPTCouncilModels.swift
CAPTNativeMac/Views/AttachmentQuarantineView.swift
CAPTNativeMac/Views/ProjectsView.swift
CAPTNativeMac/Views/ProjectCustomizeView.swift
CAPTNativeMac/Views/ResultContentView.swift
CAPTNativeMac/Views/ComposerCapabilityMenu.swift
CAPTNativeMac/Views/CouncilBuilderView.swift
```

Existing files change only at their established integration boundaries. Do not turn `CAPTOperatorStore.swift`, `ChatView.swift`, or `desktop/capt_runtime_service.py` into catch-all implementations.

---

### Task 1: Establish isolated implementation baseline

**Files:** Read both approved specs; no source changes.

**Interfaces:** Consumes design head `8c8241f885fdd0565ced44e35efcc24f862d3a43`; produces an isolated implementation worktree/branch and baseline evidence.

- [ ] **Step 1: Create isolated worktree**

```bash
git worktree add .worktrees/public-release-tranche -b feat/public-release-tranche-r1 8c8241f885fdd0565ced44e35efcc24f862d3a43
cd .worktrees/public-release-tranche
```

- [ ] **Step 2: Verify exact lineage/cleanliness**

```bash
test "$(git rev-parse HEAD)" = "8c8241f885fdd0565ced44e35efcc24f862d3a43"
git status --short --branch
```

- [ ] **Step 3: Run Python baseline alone**

```bash
python -m pytest -q
```

Record exact passed/skipped/deselected counts.

- [ ] **Step 4: Run Swift baseline alone**

```bash
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```

Record exact pass/intentional-live-skip counts.

---

### Task 2: Execute Secure Intake / Quarantine plan

**Files:** `docs/superpowers/plans/2026-08-19-secure-intake-quarantine-implementation-plan.md`

**Produces:** Stable `QuarantineRecord`, `ScanReport`, `FileReference`, CLI/Swift intake interfaces.

- [ ] Execute every TDD task in the subsystem plan.
- [ ] Prove hostile filename/path handling, sandboxed scan boundary, archive controls, EXIF/metadata output, stego coverage language, scanner-unavailable semantics, explicit disposition, and zero picker-to-model bypass.
- [ ] Freeze `FileReference` serialization before Projects/Composer depend on it.

---

### Task 3: Execute Human-First Results plan

**Files:** `docs/superpowers/plans/2026-08-19-human-first-results-implementation-plan.md`

- [ ] Execute Swift-first TDD tasks.
- [ ] Verify raw JSON is collapsed by default and one interaction away.
- [ ] Verify code-block copy preserves exact literal content and excludes surrounding prose.
- [ ] Verify Copy/Raw details accessibility labels and ledger neutrality.

---

### Task 4: Execute Projects plan

**Files:** `docs/superpowers/plans/2026-08-19-projects-implementation-plan.md`

- [ ] Execute Project model/store tasks.
- [ ] Execute Customize surface and chat context-menu tasks.
- [ ] Bind deterministic Project context eligibility into approval.
- [ ] Prove Project CRUD/membership alone changes no RuntimeService ledger state.

---

### Task 5: Execute Composer Context Palette plan

**Files:** `docs/superpowers/plans/2026-08-19-composer-context-palette-implementation-plan.md`

- [ ] Add literal parity inventory from the companion contract.
- [ ] Route Attach Files exclusively through Secure Intake.
- [ ] Add Folder/Repo Workspace, Active Apps, Screenshots, Clipboard, Project, model, and voice controls.
- [ ] Prove removing a chip removes its normalized execution input before approval binding.

---

### Task 6: Execute Search + Deep Research Governance plan

**Files:** `docs/superpowers/plans/2026-08-19-search-deep-research-governance-implementation-plan.md`

- [ ] Implement workload budgets before changing provider timeout plumbing.
- [ ] Keep `interactive_chat` at the existing bounded profile.
- [ ] Add Search, Deep Research, and deep code-review profiles with explicit ceilings.
- [ ] Prove long-context work can receive a larger *admitted* timeout without globally weakening every provider call.

---

### Task 7: Execute Cohort Council plan

**Files:** `docs/superpowers/plans/2026-08-19-cohort-council-implementation-plan.md`

- [ ] Implement immutable Council models/hard limits.
- [ ] Implement UI builder without dispatch authority.
- [ ] Implement RuntimeService governed Council admission/scheduling.
- [ ] Prove majority != verification and dissent survives synthesis.
- [ ] Prove 111 logical Vessels are scheduled under resource concurrency ceilings, never blindly launched together.

---

### Task 8: Cross-subsystem release acceptance

**Files:** release acceptance documentation/evidence manifest only after all subsystem gates pass.

- [ ] **Step 1: Run Python suite alone**

```bash
python -m pytest -q
```

Expected: zero failures.

- [ ] **Step 2: Run Swift suite/build alone**

```bash
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```

Expected: zero failures; intentional live-runtime skips enumerated.

- [ ] **Step 3: Run contract drift check**

```bash
python contracts/tools/check_drift.py
```

Expected: clean generated-contract drift.

- [ ] **Step 4: Run security/privacy matrix**

At minimum: archive traversal, archive expansion ceiling, symlink source, executable upload, malformed image, EXIF GPS image, metadata-free image, sandbox/scanner unavailable, Project-only context, workspace read-only selection, clipboard selection/removal, Council 10/111 limits, Deep Research timeout profile, raw JSON disclosure, exact-copy code.

- [ ] **Step 5: Verify authoritative ledger separation**

Project edits, file scanning, capability-menu changes, provider prewarm, and presentation toggles must not create Mission/Task/DriverRun/Evidence state. Consequential governed dispatch still must.

- [ ] **Step 6: Commit acceptance evidence**

```bash
git add docs reports
git commit -m "test: record public release tranche acceptance"
```
