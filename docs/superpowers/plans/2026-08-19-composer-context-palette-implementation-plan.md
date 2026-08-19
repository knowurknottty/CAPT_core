# Composer Context Palette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the approved prompt-box capability inventory—Search, Deep Research, Council, Attach Files, Folder/Repo Workspace, Active Apps, Screenshots, Clipboard History, Project/Shared context, Model Selector, and Voice Input—with visible removable pre-send chips.

**Architecture:** The composer owns a local `CAPTComposerContextDraft` describing user-selected eligible references/modes. It contains references, not ambient app data or raw quarantined bytes. On Send, the draft is normalized and frozen into the approval request. RuntimeService remains authoritative about actual context/admission.

**Tech Stack:** Swift 6/SwiftUI/AppKit; Secure Intake `FileReference`; Projects; provider/model registry; existing native approval flow; macOS file/folder, screen/window, pasteboard, and speech APIs behind testable protocols.

**Spec:** `docs/superpowers/specs/2026-08-19-public-release-composer-parity-contract.md` and parent design Part IV.

## Global Constraints

- Every required inventory item is directly discoverable from composer/immediate menu.
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
- `CAPTOperatorStore.swift` for active draft state.
- `CAPTNativeSessionStore.swift` only for durable Project/workspace selections; transient app/clipboard selection is not persisted by default.
- `CAPTChatCoordinator.swift` to carry normalized `composerContext` binding.

---

### Task 1: Composer draft domain model and precedence

**Interfaces:** Produces `CAPTComposerContextDraft`, `CAPTExecutionMode`, `CAPTComposerChipID`.

- [ ] **Step 1: Write RED model tests**

```swift
@Test func deepResearchReplacesSearch() {
    var draft = CAPTComposerContextDraft()
    draft.setExecutionMode(.search)
    draft.setExecutionMode(.deepResearch)
    #expect(draft.executionMode == .deepResearch)
}

@Test func removingFileChipRemovesReference() {
    var draft = CAPTComposerContextDraft(fileReferenceIDs: ["upl-1"])
    draft.remove(.file("upl-1"))
    #expect(draft.fileReferenceIDs.isEmpty)
}
```

- [ ] **Step 2: Implement exact types/methods**

```swift
public enum CAPTExecutionMode: String, Codable, Sendable { case normal, search, deepResearch }

public struct CAPTWorkspaceSelection: Codable, Equatable, Sendable {
    public let rootPath: String
    public let gitHead: String?
    public let dirtyDigest: String?
    public let writeRequested: Bool
}

public struct CAPTActiveAppSelection: Codable, Equatable, Sendable {
    public let bundleID: String
    public let windowID: String?
    public let snapshotRef: String
}

public struct CAPTClipboardSelection: Codable, Equatable, Sendable {
    public let itemID: String
    public let contentDigest: String
    public let preview: String
}

public struct CAPTScreenshotSelection: Codable, Equatable, Sendable {
    public let captureID: String
    public let fileReferenceID: String
}

public enum CAPTComposerChipID: Hashable, Sendable {
    case file(String), workspace, activeApp(String), screenshot(String), clipboard(String), project(UUID), council(UUID), executionMode
}

public struct CAPTComposerContextDraft: Codable, Equatable, Sendable {
    public var executionMode: CAPTExecutionMode = .normal
    public var fileReferenceIDs: [String] = []
    public var workspace: CAPTWorkspaceSelection?
    public var activeApps: [CAPTActiveAppSelection] = []
    public var screenshots: [CAPTScreenshotSelection] = []
    public var clipboardItems: [CAPTClipboardSelection] = []
    public var projectID: UUID?
    public var councilID: UUID?

    public init(fileReferenceIDs: [String] = []) { self.fileReferenceIDs = fileReferenceIDs }
    public mutating func setExecutionMode(_ mode: CAPTExecutionMode) { executionMode = mode }
    public mutating func remove(_ chip: CAPTComposerChipID) { /* implement exhaustive mutation in this task */ }
}
```

Implement `remove` exhaustively: remove matching stable ID or nil the singleton field; `.executionMode` resets to `.normal`. Normalize arrays by stable ID before binding.

- [ ] **Step 3: Run GREEN and commit**

```bash
cd capt_ui/surfaces/desktop_swift
swift test --filter CAPTComposerContextTests
git add .
git commit -m "feat(mac): add composer context draft"
```

---

### Task 2: Capability menu and removable chips

**Interfaces:** `ComposerCapabilityMenu` exposes literal approved inventory; `ComposerContextChips` renders active selections.

- [ ] **Step 1: Write exact inventory test**

```swift
#expect(Set(CAPTComposerCapability.allCases.map(\.rawValue)) == Set([
 "search", "deep_research", "cohort_council", "attach_files", "workspace",
 "active_apps", "screenshots", "clipboard_history", "project", "model", "voice"
]))
```

- [ ] **Step 2: Implement grouped menu**

```text
Research: Search, Deep Research
Council: Cohort Council
Context: Attach Files, Folder / Repo Workspace, Active Apps, Screenshots, Clipboard History
Project: Current Project, Switch Project…
```

Model selector and microphone remain visible primary controls rather than being hidden only in the plus menu.

- [ ] **Step 3: Implement inspect/remove chips**

Examples: `Search`, `Workspace: CAPT_core`, `2 files`, `Safari window`, `Council: 4C/12V`, `Project: Release Sprint`.

- [ ] **Step 4: Verify local-only mutation and commit**

Opening/removing chips makes no runtime call and no ledger change.

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add composer capability palette"
```

---

### Task 3: Attach Files integration through Secure Intake

**Interfaces:** Attach action receives only eligible `FileReference` IDs from Secure Intake.

- [ ] **Step 1: Write RED no-bypass test**

Selected file in `SCANNING` state -> no file ref in draft. After explicit `use_in_chat` disposition -> exact cleared ref appears.

- [ ] **Step 2: Reuse `AttachmentQuarantineView`**

Do not create a second picker/intake implementation.

- [ ] **Step 3: Distinguish scan status from execution chips**

`Scanning 1 file…` is status, not a bound chip. Only eligible `FileReference`s become chips.

- [ ] **Step 4: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): route composer attachments through quarantine"
```

---

### Task 4: Folder / Repo Workspace selection

**Interfaces:** Produces canonical `CAPTWorkspaceSelection` with root, Git HEAD/dirty digest when applicable, and read/write request.

- [ ] **Step 1: Write RED projection tests**

Folder defaults `writeRequested == false`; Git repo captures exact HEAD and digest of `git status --porcelain=v1` without mutation.

- [ ] **Step 2: Implement folder picker/canonicalization**

Resolve symlinks. Invoke Git via argument arrays with bounded timeout/sanitized environment:

```text
git -C <root> rev-parse HEAD
git -C <root> status --porcelain=v1
```

- [ ] **Step 3: Add explicit write request**

UI default `Read-only`; `Request write access…` sets only `writeRequested=true`. It does not grant capability.

- [ ] **Step 4: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add workspace selection to composer"
```

---

### Task 5: Active Apps, Screenshots, Clipboard History

**Interfaces:** Each creates a bounded selected reference; no ambient live authority.

- [ ] **Step 1: Active App explicit inventory**

Use `NSWorkspace.shared.runningApplications` for app listing. Window/screen content requires explicit selection and macOS privacy permission. App selection stores bundle/display identity only until a bounded snapshot is actually captured.

- [ ] **Step 2: Screenshot flow**

Choices exactly: Screen, Window, Region, Recent Screenshot. Persisted capture file routes through Secure Intake before becoming a `FileReference`.

- [ ] **Step 3: Clipboard picker**

Initial public release exposes current pasteboard plus an in-app history of items CAPT observed while history was explicitly enabled. Persistent history is opt-in. Each selected item carries digest + bounded preview + payload reference.

- [ ] **Step 4: Privacy tests**

No selection -> no context. Removing chip -> no context. New Chat/disconnect clears transient Active App/clipboard selections unless user explicitly stores them in a Project-compatible artifact flow.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add explicit app screenshot and clipboard context"
```

---

### Task 6: Project selector, model selector, voice input

**Interfaces:** Project consumes Projects subsystem; model keeps current provider/model + warm-state behavior; voice produces editable draft text only.

- [ ] **Step 1: Add current Project control**

Switching Project updates local organizational/context draft only.

- [ ] **Step 2: Preserve model selector / Council distinction**

Council off: provider/model is the single-model path. Council on: primary model may serve as explicit default/synthesis Cohort but cannot silently collapse Council.

- [ ] **Step 3: Add speech adapter protocol**

Tests inject transcripts. Captured transcript is inserted into the editable composer draft; ordinary Send/approval flow remains mandatory.

- [ ] **Step 4: Verify audio retention default**

Session persistence contains edited text, not raw audio bytes, unless a future explicit retention setting changes policy.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): complete composer project model and voice controls"
```

---

### Task 7: Freeze/bind normalized composer context at Send

**Interfaces:** `CAPTChatCoordinator.requestApproval` carries deterministic `composerContext` + digest.

- [ ] **Step 1: Write RED mutation test**

Approve file A + workspace HEAD X; offer file B or HEAD Y at run -> pre-dispatch `AUTHORITYVIOLATION`, zero DriverRuns.

- [ ] **Step 2: Normalize only stable execution inputs**

Include stable IDs/digests/canonical roots. Exclude UI previews, chip order, colors, window positions, warm latency.

- [ ] **Step 3: Snapshot draft synchronously on Send**

Freeze normalized draft before async approval begins. Later UI edits apply only to the next request.

- [ ] **Step 4: Run authority tests and commit**

```bash
python -m pytest tests/capt_runtime/test_prompt_approval_binding.py -q
cd capt_ui/surfaces/desktop_swift && swift test
git add capt_runtime desktop capt_ui/surfaces/desktop_swift tests
git commit -m "feat(runtime): bind composer context to approved execution"
```

---

### Task 8: Composer parity acceptance

- [ ] Verify every required capability is reachable from composer/immediate menu.
- [ ] Verify Search -> Deep Research replacement and Council/model distinction.
- [ ] Verify no pending scan becomes bound context.
- [ ] Verify no app/clipboard/screenshot data enters context absent explicit selection.
- [ ] Verify chip removal removes normalized input.
- [ ] Verify menu/context editing remains EventStore-ledger neutral.
- [ ] Run full Python suite, Swift tests, and `swift build --product CAPTNativeMac` with zero failures.
