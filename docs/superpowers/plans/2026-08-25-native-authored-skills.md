# CAPT Native Authored Skills R1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import heterogeneous Agent Skills into each CAPT state root, contextually select applicable skills before approval, preserve CAPT governance, and expose selected-skill provenance in the native macOS client.

**Architecture:** Extend the existing `capt_runtime.authored_skills` authority spine with a managed-pack module and deterministic selector. RuntimeService resolves the pack from the ledger state root and freezes selection before approval; Swift only renders the selected names returned by the runtime.

**Tech Stack:** Python 3.10+, pytest, existing CAPT RuntimeService/contracts, Swift 6/SwiftUI/XCTest, filesystem SHA-256 manifests.

**Spec:** `docs/superpowers/specs/2026-08-25-native-authored-skills-design.md`

## Global Constraints

- Skills are context-only guidance and never grant tools, permissions, authority, or policy overrides.
- Explicit authored-skill selection remains supported and outranks contextual selection.
- Managed skill bytes are verified before approval and frozen through dispatch; no post-approval re-read.
- Imports are atomic and reject path traversal/symlink escapes/conflicting duplicate names.
- Native Swift remains a renderer; runtime owns import, ranking, verification, and selection.
- Standard and Inversion Labs editions keep independent packs under their respective `CAPT_STATE_DIR` roots.

---

### Task 1: Managed skill-pack import and verification

**Files:**
- Create: `capt_runtime/managed_skills.py`
- Modify: `capt_cli.py`
- Test: `tests/capt_runtime/test_managed_skills.py`
- Test: `tests/test_cli_authored_skills.py`

**Interfaces:**
- Produces `import_managed_skill_pack(source, destination, pack_name) -> dict`
- Produces `verify_managed_skill_pack(root) -> dict`
- Produces `default_managed_skill_root(state_root, pack_name='ultimate') -> Path`

- [ ] Write failing tests for directory/flat-markdown/`.skill` import, identical duplicate collapse, conflicting duplicate rejection, ZIP traversal rejection, and tamper detection.
- [ ] Run focused tests and confirm RED failures are feature-absence failures.
- [ ] Implement canonical discovery, safe ZIP extraction, whole-directory copying, atomic manifest write, and tree digests.
- [ ] Add `capt skills import` / `capt skills verify` CLI paths without weakening existing pinned-pack commands.
- [ ] Run focused tests green and commit.

### Task 2: Deterministic contextual selector and frozen context

**Files:**
- Modify: `capt_runtime/managed_skills.py`
- Modify: `capt_runtime/authored_skills.py`
- Test: `tests/capt_runtime/test_managed_skill_selection.py`
- Test: `tests/capt_runtime/test_authored_skill_context.py`

**Interfaces:**
- Produces `select_managed_skills(objective, verified_pack, limit=4) -> list[str]`
- Produces `prepare_managed_skill_context(root, objective, explicit_names=None, limit=4) -> tuple[dict|None,list[str]]`

- [ ] Write failing tests for exact trigger, description/name matching, composed selections, stable ordering, negative applicability, no-match, limit, and explicit override.
- [ ] Verify RED.
- [ ] Implement tokenization/scoring with deterministic tie-breaks and minimum threshold.
- [ ] Reuse existing context shape/summary so DriverHost and prompt assembly remain contract-compatible.
- [ ] Run focused tests green and commit.

### Task 3: RuntimeService approval binding and native provenance

**Files:**
- Modify: `desktop/capt_runtime_service.py`
- Modify: `capt_ui/surfaces/desktop_swift/Sources/CAPTCoreDesktop/CAPTRuntimeModels.swift`
- Modify: `capt_ui/surfaces/desktop_swift/Sources/CAPTCoreDesktop/CAPTChatCoordinator.swift`
- Modify: `capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/ChatView.swift`
- Test: `tests/capt_runtime/test_authored_skill_context.py` or new focused RuntimeService test
- Test: `capt_ui/surfaces/desktop_swift/Tests/CAPTCoreDesktopTests/CAPTChatCoordinatorTests.swift`

**Interfaces:**
- Runtime approval response includes `skillNames: [String]`.
- `CAPTPendingApproval` gains `skillNames: [String]` with backwards-compatible default `[]`.

- [ ] Write failing Python test proving default managed selection occurs before approval binding and prepared execution reuses the frozen selection.
- [ ] Write failing Swift test proving selected skill names survive request approval parsing.
- [ ] Verify both RED.
- [ ] Resolve default managed pack from `Path(ledger_path).parent / 'skills' / 'ultimate'`; auto-select only when the pack exists and explicit selection is absent.
- [ ] Return selected names with approval metadata and store/render them in native chat/inspector UI.
- [ ] Run Python and Swift focused tests green and commit.

### Task 4: Import Ultimate-skills into both native editions and close verification

**Files:**
- Runtime state only: `~/.capt/skills/ultimate/**`
- Runtime state only: `~/.capt-inversion-labs/skills/ultimate/**`
- Modify docs if CLI behavior changed: `docs/AUTHORED_SKILLS.md`

- [ ] Run `capt skills import` against `~/Desktop/Ultimate-skills` for each state root.
- [ ] Run `capt skills verify` for both and compare manifest digests/counts.
- [ ] Exercise selector objectives for CAPT continuation/release work and Inversion/web-design work; verify expected skills and a no-match control.
- [ ] Run complete relevant Python suite, contract drift/parity gates, and `swift test`.
- [ ] Inspect final git diff/status, commit docs if needed, push branch, and open/update PR without merging unless explicitly authorized.
