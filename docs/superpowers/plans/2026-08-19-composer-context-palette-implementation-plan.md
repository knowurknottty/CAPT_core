# Composer Context Palette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the approved prompt-box capability inventory—Search, Deep Research, Council, Attach Files, Folder/Repo Workspace, Active Apps, Screenshots, Clipboard History, Project/Shared context, Model Selector, and Voice Input—with visible removable pre-send chips.

**Architecture:** The composer owns a local `CAPTComposerContextDraft` describing user-selected eligible inputs/modes. It contains references, not ambient app data or raw quarantined bytes. On Send, the draft is normalized and bound into the approval request; selections can be removed before binding. RuntimeService remains authoritative about actual context/admission.

**Tech Stack:** Swift 6/SwiftUI/AppKit; Secure Intake `FileReference`; Projects; existing provider/model registry; existing native chat approval flow; macOS APIs for file/folder picker, screen/window enumeration, pasteboard, and speech input where available.

**Spec:** `docs/superpowers/specs/2026-08-19-public-release-composer-parity-contract.md` and parent design Part IV.

## Global Constraints

- Every required inventory item is directly discoverable from the composer or immediate menu.
- Search and Deep Research are mutually exclusive.
- Council and ordinary single-model execution are distinct modes.
- Attach Files never bypasses Secure Intake.
- Active Apps requires explicit app/window selection; no ambient all-app access.
- Clipboard History requires explicit item selection; no silent ingestion.
- Workspace defaults read-only unless write authority is separately granted.
- Voice transcript remains visible/editable before consequential dispatch.
- Removing a chip removes its corresponding execution input before approval binding.

## File Structure

**Create:**
- `CAPTCoreDesktop/CAPTComposerContext.swift`
- `CAPTNativeMac/Views/ComposerCapabilityMenu.swift`
- `CAPTNativeMac/Views/ComposerContextChips.swift`
- `CAPTNativeMac/Views/WorkspacePickerView.swift`
- `CAPTNativeMac/Views/ActiveAppPickerView.swift`
- `CAPTNativeMac/Views/ClipboardPickerView.swift`
- `CAPTNativeMac/Views/ScreenshotPickerView.swift`
- `CAPTCoreDesktopTests/CAPTComposerContextTests.swift`

**Modify:**
- `ChatView.swift` / `ComposerView` integration only.
- `CAPTOperatorStore.swift` to own active composer draft per active chat/new chat.
- `CAPTNativeSessionStore.swift` only if the design chooses persistence of user-selected draft chips; default plan persists selected Project/workspace references but does not persist transient Active App/clipboard selections.
- `CAPTChatCoordinator.swift` request payload to include normalized `composerContext` binding.

---

### Task 1: Composer draft domain model and precedence

**Interfaces:**
- Produces `CAPTComposerContextDraft` and `CAPTExecutionMode`.

- [ ] **Step 1: Write RED model tests**

```swift
@Test func deepResearchReplacesSearch() {
    var draft = CAPTComposerContextDraft()
    draft.setExecutionMode(.search)
    draft.setExecutionMode(.deepResearch)
    #expect(draft.executionMode == .deepResearch)
}

@Test func removingFileChipRemovesReference() {
    var draft = CAPTComposerContextDraft(fileReferences: [.fixture("upl-1")])
    draft.remove(.file("upl-1"))
    #expect(draft.fileReferences.isEmpty)
}
```

- [ ] **Step 2: Implement exact types**

```swift
public enum CAPTExecutionMode: String, Codable, Sendable { case normal, search, deepResearch }
public struct CAPTWorkspaceSelection: Codable, Equatable, Sendable { let rootPath: String; let gitHead: String?; let writeRequested: Bool }
public struct CAPTActiveAppSelection: Codable, Equatable, Sendable { let bundleID: String; let windowID: String?; let snapshotRef: String }
public struct CAPTClipboardSelection: Codable, Equatable, Sendable { let itemID: String; let contentDigest: String; let preview: String }
public struct CAPTScreenshotSelection: Codable, Equatable, Sendable { let captureID: String; let fileReferenceID: String }
public struct CAPTComposerContextDraft: Codable, Equatable, Sendable {
    var executionMode: CAPTExecutionMode = .normal
    var fileReferenceIDs: [String] = []
    var workspace: CAPTWorkspaceSelection?
    var activeApps: [CAPTActiveAppSelection] = []
    var screenshots: [CAPTScreenshotSelection] = []
    var clipboardItems: [CAPTClipboardSelection] = []
    var projectID: UUID?
    var councilID: UUID?
}
```

Normalize arrays by stable ID before binding.

- [ ] **Step 3: Run GREEN and commit**

```bash
swift test --filter CAPTComposerContextTests
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add composer context draft"
```

---

### Task 2: Capability menu and removable chips

**Interfaces:**
- `ComposerCapabilityMenu` exposes the literal approved inventory.
- `ComposerContextChips` renders only active selections.

- [ ] **Step 1: Write menu inventory test**

Define `CAPTComposerCapability.allCases` and assert exact required identifiers:

```swift
#expect(Set(CAPTComposerCapability.allCases.map(\.rawValue)) == Set([
 "search", "deep_research", "cohort_council", "attach_files", "workspace",
 "active_apps", "screenshots", "clipboard_history", "project", "model", "voice"
]))
```

- [ ] **Step 2: Implement grouped menu**

Visible grouping:

```text
Research: Search, Deep Research
Council: Cohort Council
Context: Attach Files, Folder / Repo Workspace, Active Apps, Screenshots, Clipboard History
Project: Current Project, Switch Project…
```

Model selector and microphone remain visible primary composer controls rather than hidden only in the plus menu.

- [ ] **Step 3: Implement chips**

Each chip has inspect/remove semantics and accessible labels. Examples: `Search`, `Workspace: CAPT_core`, `2 files`, `Safari window`, `Council: 4C/12V`, `Project: Release Sprint`.

- [ ] **Step 4: Verify chip removal mutates only local draft**

No runtime call, no Project store mutation, no ledger change.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add composer capability palette"
```

---

### Task 3: Attach Files integration through Secure Intake

**Interfaces:**
- Composer action invokes Quarantine intake flow and receives only eligible `FileReference` IDs.

- [ ] **Step 1: Write RED no-bypass test**

Select a file, stop after `SCANNING`, inspect composer draft: no file reference ID present. Complete `use_in_chat` disposition: exact eligible reference appears.

- [ ] **Step 2: Wire Attach Files action**

Reuse `AttachmentQuarantineView`; do not create a second file picker/intake implementation.

- [ ] **Step 3: Add pending-scan visual state outside bound chips**

Show `Scanning 1 file…` as intake status, not an active execution chip. Only eligible references become chips.

- [ ] **Step 4: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): route composer attachments through quarantine"
```

---

### Task 4: Folder / Repo Workspace selection

**Interfaces:**
- Produces `CAPTWorkspaceSelection` with canonical root, repo HEAD when Git, dirty state summary, requested read/write mode.

- [ ] **Step 1: Write RED workspace projection tests**

Folder selection defaults `writeRequested == false`. Git repo projection captures exact `git rev-parse HEAD` and `git status --porcelain` digest/summary without modifying repo.

- [ ] **Step 2: Implement picker**

Use folder-selection panel. Resolve symlinks/canonical root. When `.git` is present, invoke `git -C <root> rev-parse HEAD` and `git -C <root> status --porcelain=v1` via argument arrays, bounded timeout, sanitized environment.

- [ ] **Step 3: Add explicit write request control**

UI wording: `Read-only` default; `Request write access…` creates a request flag only. It is not a capability grant.

- [ ] **Step 4: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add workspace selection to composer"
```

---

### Task 5: Active Apps, Screenshots, Clipboard History

**Interfaces:**
- Each selection produces a bounded snapshot/reference, not ambient live authority.

- [ ] **Step 1: Implement explicit Active App/window inventory**

Use `NSWorkspace.shared.runningApplications` for app listing. Window/screen capture capability must remain subject to macOS privacy permissions. Selecting an app alone stores bundle ID/display metadata; selecting content produces a bounded snapshot reference.

- [ ] **Step 2: Implement Screenshot flow**

Choices: Screen, Window, Region, Recent Screenshot. Persisted captures route their resulting file through Secure Intake and produce a cleared `FileReference` before context eligibility.

- [ ] **Step 3: Implement Clipboard picker**

Initial public release reads the current pasteboard plus an in-app history only for items CAPT itself observed while enabled. Persistent history remains opt-in. Each selected item stores digest + preview + selected payload reference; never auto-add all history.

- [ ] **Step 4: Write privacy tests**

No selection -> no app/screenshot/clipboard context. Clearing a chip removes context. Disconnect/new chat clears transient app/clipboard selections unless user intentionally pins them to Project context.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add explicit app screenshot and clipboard context"
```

---

### Task 6: Project selector, model selector, voice input

**Interfaces:**
- Project chip references Projects subsystem.
- Model selector keeps existing provider/model behavior and warm state.
- Voice creates editable text only.

- [ ] **Step 1: Add Project selection**

Current Project visible near composer. Switching updates local draft/session organization; it does not dispatch or mutate RuntimeService.

- [ ] **Step 2: Preserve model/provider selector and warm indicator**

When Council is off, selected provider/model is the single-model path. When Council is on, label primary model as default/synthesis Cohort if configured; never silently disable Council.

- [ ] **Step 3: Add voice input adapter**

Use platform speech support behind a protocol so tests inject transcripts. Transcript inserts into `draft` and remains editable. Send still follows the normal approval path.

- [ ] **Step 4: Add voice persistence test**

Audio bytes are not stored in session model by default; only the edited text is submitted/persisted unless a future explicit retention setting says otherwise.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): complete composer project model and voice controls"
```

---

### Task 7: Bind normalized composer context into approval

**Interfaces:**
- `CAPTChatCoordinator.requestApproval` adds deterministic `composerContext`/digest.
- Runtime approval binding persists/validates the offered context-selection digest.

- [ ] **Step 1: Write RED binding mutation test**

Approve with file ref A + workspace HEAD X; run with file ref B or HEAD Y. Expect pre-dispatch `AUTHORITYVIOLATION` with context-binding mismatch and zero DriverRuns created.

- [ ] **Step 2: Implement deterministic normalization**

Only stable IDs/digests/canonical roots enter binding. Exclude UI previews, chip order, colors, window positions.

- [ ] **Step 3: Make `submitPrompt` snapshot draft before async approval request**

Once Send is pressed, freeze the normalized draft for that pending approval. Subsequent UI edits apply to the next prompt and cannot mutate the in-flight binding.

- [ ] **Step 4: Run authority tests and commit**

```bash
python -m pytest tests/capt_runtime/test_prompt_approval_binding.py -q
cd capt_ui/surfaces/desktop_swift && swift test

git add capt_runtime desktop capt_ui/surfaces/desktop_swift tests
git commit -m "feat(runtime): bind composer context to approved execution"
```

---

### Task 8: Composer parity acceptance

- [ ] **Step 1: UI inventory acceptance**

Verify every required capability is reachable from the composer or immediate menu.

- [ ] **Step 2: Precedence acceptance**

Search -> Deep Research replaces mode; Council remains distinct from primary model; cleared Project + explicit attachments combine as eligible references; no pending scan is bound.

- [ ] **Step 3: Privacy acceptance**

No app/clipboard/screenshot data enters draft absent explicit selection. Removing each chip removes the corresponding normalized input.

- [ ] **Step 4: Ledger neutrality**

Opening menus, selecting/removing local context, switching Project/model, and editing voice transcript do not change EventStore state. Only governed Send/approval/admission may do so.

- [ ] **Step 5: Full tests/build**

```bash
python -m pytest -q
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```
