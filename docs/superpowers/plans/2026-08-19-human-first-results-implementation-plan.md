# Human-First Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make public CAPT responses readable by default while keeping technical detail and the exact raw envelope one interaction away, with exact-copy code blocks.

**Architecture:** Introduce a typed presentation model in `CAPTCoreDesktop` that separates human text, code blocks, technical fields, and raw JSON. Runtime/Operator responses remain unchanged authority-wise; the native client projects them into display layers. Raw data is retained read-only and collapsed by default.

**Tech Stack:** Swift 6, SwiftUI, Foundation, AppKit `NSPasteboard`, existing CAPT native message/session models and RuntimeService projection.

**Spec:** `docs/superpowers/specs/2026-08-19-public-release-quarantine-projects-council-design.md` Part II §§14-18.

## Global Constraints

- `Normal` is the default presentation mode.
- Raw JSON is never the default ordinary assistant answer.
- Raw JSON remains one interaction away.
- Copying a code block copies only literal block content, preserving indentation and characters.
- Presentation mode changes rendering only; it never changes authority/evidence/verification state.

## File Structure

**Create:**
- `CAPTCoreDesktop/CAPTResultPresentation.swift`
- `CAPTNativeMac/Views/ResultContentView.swift`
- `CAPTNativeMac/Views/CodeBlockView.swift`
- `CAPTNativeMac/Views/RawDetailsView.swift`
- `CAPTCoreDesktopTests/CAPTResultPresentationTests.swift`

**Modify:**
- `CAPTChatCoordinator.swift` to retain a stable raw response representation in `CAPTExecutionResult`.
- `CAPTNativeSessionStore.swift` for backward-compatible presentation payload persistence when needed.
- `ChatView.swift` to delegate assistant/system message content rendering to `ResultContentView`.

---

### Task 1: Define typed presentation payload

**Interfaces:** Produces `CAPTPresentationMode`, `CAPTTechnicalField`, `CAPTMessageSegment`, `CAPTResultPresentation`.

- [ ] **Step 1: Write RED parsing/default tests**

```swift
@Test func parsesCodeFenceWithoutChangingLiteralContent() throws {
    let source = "Before\n```swift\nlet x = \"a  b\"\n    print(x)\n```\nAfter"
    let p = CAPTResultPresentation.parse(text: source, rawJSON: nil, authorityState: "awaiting_verification")
    #expect(p.segments.contains(.code(language: "swift", literal: "let x = \"a  b\"\n    print(x)")))
}

@Test func defaultModeIsNormal() {
    #expect(CAPTPresentationMode.default == .normal)
}
```

- [ ] **Step 2: Implement exact types**

```swift
public enum CAPTPresentationMode: String, Codable, CaseIterable, Sendable {
    case normal, detailed, forensic, raw
    public static let `default`: Self = .normal
}

public struct CAPTTechnicalField: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let label: String
    public let value: String
    public let category: String
}

public enum CAPTMessageSegment: Codable, Equatable, Sendable {
    case text(String)
    case code(language: String?, literal: String)
}

public struct CAPTResultPresentation: Codable, Equatable, Sendable {
    public let humanText: String
    public let segments: [CAPTMessageSegment]
    public let technicalDetails: [CAPTTechnicalField]
    public let rawJSON: String?
    public let authorityState: String?
}
```

- [ ] **Step 3: Implement deterministic fence parser**

`parse(text:rawJSON:authorityState:)` preserves exact code content between the structural opening/closing-fence newlines, supports multiple fenced blocks, and treats an unmatched opening fence as ordinary text rather than dropping content.

- [ ] **Step 4: Run GREEN and commit**

```bash
cd capt_ui/surfaces/desktop_swift
swift test --filter CAPTResultPresentationTests
git add .
git commit -m "feat(mac): add result presentation model"
```

---

### Task 2: Preserve raw RuntimeService response without rendering it by default

**Interfaces:** `CAPTExecutionResult` gains `rawResponseJSON: String?`; user-facing fallback is human text.

- [ ] **Step 1: Write RED coordinator tests**

For a response with observations and one with no renderable text:

```swift
#expect(result.rawResponseJSON?.contains("driverRunId") == true)
#expect(result.text.contains("{\"") == false)
```

- [ ] **Step 2: Implement stable sorted raw JSON**

Use `JSONSerialization.data(withJSONObject: options: [.sortedKeys])`. Replace raw-dump chat fallback with:

```text
CAPT returned a structured result without renderable assistant text. Open Raw details to inspect the response.
```

- [ ] **Step 3: Preserve backward compatibility**

Older session messages with only `text`/`authorityState` synthesize presentation during rendering; no destructive migration of old encrypted session bytes.

- [ ] **Step 4: Run focused tests and commit**

```bash
swift test --filter CAPTChatCoordinator
git add .
git commit -m "fix(mac): preserve raw result without dumping JSON to chat"
```

---

### Task 3: Exact-copy code block component

**Interfaces:** `CodeBlockView(language:literal:)`; `CAPTClipboardPayload.code(_:) -> String`.

- [ ] **Step 1: Write RED literal-copy tests**

Cover tabs, multiple spaces, Unicode, quotes, trailing blank lines. Returned payload must equal input string byte-for-byte after UTF-8 encoding.

- [ ] **Step 2: Implement clipboard helper/component**

```swift
public enum CAPTClipboardPayload {
    public static func code(_ literal: String) -> String { literal }
}
```

`CodeBlockView` header shows language and Copy button; body uses monospaced selectable text and horizontal scrolling when needed. Copy:

```swift
let pasteboard = NSPasteboard.general
pasteboard.clearContents()
pasteboard.setString(CAPTClipboardPayload.code(literal), forType: .string)
```

- [ ] **Step 3: Add accessibility/transient feedback**

Button accessibility label `Copy code block`; transient visual `Copied` state does not mutate stored content.

- [ ] **Step 4: Run/build/commit**

```bash
swift test --filter CAPTResultPresentationTests
swift build --product CAPTNativeMac
git add .
git commit -m "feat(mac): add exact-copy code blocks"
```

---

### Task 4: Human / technical / raw disclosure UI

**Interfaces:** `ResultContentView(presentation:mode:)`, `RawDetailsView(rawJSON:)`.

- [ ] **Step 1: Write disclosure state tests**

```swift
public struct CAPTDisclosureState: Equatable, Sendable {
    public var technicalExpanded = false
    public var rawExpanded = false
}
```

Assert both false initially and one explicit action toggles each.

- [ ] **Step 2: Implement Normal rendering**

Render text/code segments in order; authority/evidence state is a compact badge. Debug IDs stay out of Normal mode unless they were part of actual human answer text.

- [ ] **Step 3: Implement disclosures**

Controls exactly:

```text
Technical details ▸
Raw details ▸
```

Raw details are read-only monospaced selectable JSON plus `Copy raw JSON`.

- [ ] **Step 4: Implement modes**

`detailed`: technical fields expanded. `forensic`: technical + provenance/evidence fields expanded. `raw`: raw envelope expanded. Modes change rendering only.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat(mac): add layered CAPT result disclosure"
```

---

### Task 5: Integrate with ChatView

**Interfaces:** Assistant/system messages delegate to ResultContentView; user messages remain ordinary text.

- [ ] **Step 1: Write presentation projection tests**

Message containing prose + two code blocks + raw JSON yields ordered segments and separate raw field.

- [ ] **Step 2: Refactor `MessageRow`**

Do not leave parsing/copy logic in `ChatView`; construct/use `CAPTResultPresentation` via focused types.

- [ ] **Step 3: Verify width behavior**

Large code/raw JSON scrolls internally and does not force full window width.

- [ ] **Step 4: Run full Swift suite/build and commit**

```bash
swift test
swift build --product CAPTNativeMac
git add .
git commit -m "feat(mac): render human-first chat results"
```

---

### Task 6: Human-first result subsystem acceptance

- [ ] Fixture matrix: ordinary prose; code-only; prose + multiple fenced languages; unmatched fence; raw-only RuntimeService result; large raw envelope; scan result; verification result.
- [ ] SHA-256 source literal vs clipboard helper UTF-8 output for every code fixture; digests must match.
- [ ] Fresh profile defaults to Normal and no raw JSON is visible without user action.
- [ ] Presentation mode changes, Raw-details expansion, and copy actions leave RuntimeService head/digest unchanged.
- [ ] Run full Python suite, Swift tests, and `swift build --product CAPTNativeMac` with zero failures.
