# Human-First Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make public CAPT responses readable by default while keeping technical detail and the exact raw envelope one interaction away, with exact-copy code blocks.

**Architecture:** Introduce a typed presentation model in `CAPTCoreDesktop` that separates human text, code blocks, technical fields, and raw JSON. Runtime/Operator responses remain unchanged authority-wise; the native client projects them into display layers. Raw data is retained read-only and collapsed by default.

**Tech Stack:** Swift 6, SwiftUI, Foundation `AttributedString`, `NSPasteboard`, existing CAPT native message/session models and RuntimeService projection.

**Spec:** `docs/superpowers/specs/2026-08-19-public-release-quarantine-projects-council-design.md` Part II §§14-18.

## Global Constraints

- `Normal` is the default presentation mode.
- Raw JSON is never the default ordinary assistant answer.
- Raw JSON remains one interaction away.
- Copying a code block copies only literal block content, preserving indentation and characters.
- Presentation mode changes rendering only; it never changes authority/evidence/verification state.

## File Structure

**Create:**
- `capt_ui/surfaces/desktop_swift/Sources/CAPTCoreDesktop/CAPTResultPresentation.swift`
- `capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/ResultContentView.swift`
- `capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/CodeBlockView.swift`
- `capt_ui/surfaces/desktop_swift/Sources/CAPTNativeMac/Views/RawDetailsView.swift`
- `capt_ui/surfaces/desktop_swift/Tests/CAPTCoreDesktopTests/CAPTResultPresentationTests.swift`

**Modify:**
- `CAPTChatCoordinator.swift` to retain a stable raw response representation in `CAPTExecutionResult`.
- `CAPTNativeSessionStore.swift` to encode presentation payloads without losing backward compatibility.
- `ChatView.swift` to delegate message content rendering to `ResultContentView`.

---

### Task 1: Define typed presentation payload

**Interfaces:**
- Produces `CAPTResultPresentation` with `humanText`, `segments`, `technicalDetails`, `rawJSON`, `authorityState`.
- Produces `CAPTMessageSegment.text(String)` and `.code(language: String?, literal: String)`.

- [ ] **Step 1: Write RED parsing tests**

```swift
@Test func parsesCodeFenceWithoutChangingLiteralContent() throws {
    let source = "Before\n```swift\nlet x = \"a  b\"\n    print(x)\n```\nAfter"
    let p = CAPTResultPresentation.parse(text: source, rawJSON: nil, authorityState: "awaiting_verification")
    #expect(p.segments.contains(.code(language: "swift", literal: "let x = \"a  b\"\n    print(x)")))
}

@Test func defaultModeIsNormalAndRawIsHidden() {
    #expect(CAPTPresentationMode.default == .normal)
}
```

- [ ] **Step 2: Run RED**

```bash
cd capt_ui/surfaces/desktop_swift
swift test --filter CAPTResultPresentationTests
```

- [ ] **Step 3: Implement presentation types and deterministic fence parser**

```swift
public enum CAPTPresentationMode: String, Codable, CaseIterable, Sendable {
    case normal, detailed, forensic, raw
    public static let `default`: Self = .normal
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

Fence parsing must preserve the exact content between opening and closing fences except the structural newline directly after the opening fence and directly before the closing fence.

- [ ] **Step 4: Run GREEN**
- [ ] **Step 5: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add result presentation model"
```

---

### Task 2: Preserve raw RuntimeService response without rendering it by default

**Interfaces:**
- `CAPTExecutionResult` gains `rawResponseJSON: String?`.
- `extractAssistantText` no longer uses a full JSON dump as the user-facing fallback.

- [ ] **Step 1: Write RED coordinator tests**

Test a response that contains observations and a response with no renderable text. Assert:

```swift
#expect(result.rawResponseJSON?.contains("driverRunId") == true)
#expect(result.text.contains("{\"") == false)
```

- [ ] **Step 2: Implement stable sorted JSON serialization**

Use `JSONSerialization.data(withJSONObject:options:[.sortedKeys])` for `rawResponseJSON`. Fallback human text:

```swift
"CAPT returned a structured result without renderable assistant text. Open Raw details to inspect the response."
```

- [ ] **Step 3: Add backward-compatible session decoding**

If older session messages lack presentation/raw fields, synthesize presentation from existing `text` and `authorityState` during rendering rather than forcing migration of old ciphertext.

- [ ] **Step 4: Run focused tests and commit**

```bash
swift test --filter CAPTChatCoordinator

git add capt_ui/surfaces/desktop_swift
git commit -m "fix(mac): preserve raw result without dumping JSON to chat"
```

---

### Task 3: Exact-copy code block component

**Interfaces:**
- `CodeBlockView(language:literal:)` owns copy action.

- [ ] **Step 1: Write RED helper test for copied content**

Move clipboard payload production into a testable helper:

```swift
public enum CAPTClipboardPayload {
    public static func code(_ literal: String) -> String { literal }
}
```

Test tabs, spaces, Unicode, quotes, trailing blank lines.

- [ ] **Step 2: Implement `CodeBlockView`**

Header: language label at leading edge, `Copy` button at trailing edge. Body uses monospaced selectable text in horizontal scroll when needed. Copy with:

```swift
let pasteboard = NSPasteboard.general
pasteboard.clearContents()
pasteboard.setString(literal, forType: .string)
```

- [ ] **Step 3: Add accessibility labels**

`Copy code block`; after activation provide a transient `Copied` visual state without modifying literal content.

- [ ] **Step 4: Run tests/build and commit**

```bash
swift test --filter CAPTResultPresentationTests
swift build --product CAPTNativeMac

git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add exact-copy code blocks"
```

---

### Task 4: Human / technical / raw disclosure UI

**Interfaces:**
- `ResultContentView(presentation:mode:)`.
- `RawDetailsView(rawJSON:)` collapsed initially.

- [ ] **Step 1: Write state-model tests**

Define `CAPTDisclosureState` with `technicalExpanded` and `rawExpanded`, both false by default. Assert one action toggles each.

- [ ] **Step 2: Implement default human rendering**

Render text and code segments in order. Authority/evidence status is a compact badge. Debug IDs do not appear in Normal mode unless they are part of the actual human answer.

- [ ] **Step 3: Implement disclosures**

Buttons:

```text
Technical details ▸
Raw details ▸
```

Raw details render read-only monospaced selectable JSON and a `Copy raw JSON` action.

- [ ] **Step 4: Implement modes**

`detailed` expands technical fields by default; `forensic` expands technical plus provenance/evidence state; `raw` opens raw envelope by default but still does not change stored data.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add layered CAPT result disclosure"
```

---

### Task 5: Replace ChatView's plain message renderer

**Interfaces:**
- Existing role/layout remains.
- Assistant/system messages render through `ResultContentView`; user messages remain simple text.

- [ ] **Step 1: Write View/store projection tests for message presentation**

Create a message containing prose + code + raw JSON; assert its presentation has all three segments/layers.

- [ ] **Step 2: Refactor `MessageRow`**

Do not parse or copy inside `ChatView`; construct/present `CAPTResultPresentation` through focused types.

- [ ] **Step 3: Verify long JSON and code do not force whole-window width**

Use horizontal scrolling inside code/raw regions only.

- [ ] **Step 4: Run full Swift suite/build**

```bash
swift test
swift build --product CAPTNativeMac
```

- [ ] **Step 5: Commit**

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): render human-first chat results"
```

---

### Task 6: Human-first result subsystem acceptance

- [ ] **Step 1: Run fixture matrix**

Fixtures: ordinary prose; code-only; prose + multiple fenced languages; malformed/unclosed fence; raw-only structured RuntimeService response; large raw envelope; security scan result; verification result.

- [ ] **Step 2: Verify exact copy**

For each code fixture, SHA-256 the source literal and SHA-256 the string returned by the clipboard helper; digests must match.

- [ ] **Step 3: Verify public default**

Fresh app/profile renders Normal mode and no raw JSON is visible without user action.

- [ ] **Step 4: Verify ledger neutrality**

Changing presentation mode, opening Raw details, and copying content must not change RuntimeService ledger head/digest.

- [ ] **Step 5: Run full release regression slice**

```bash
python -m pytest -q
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```
