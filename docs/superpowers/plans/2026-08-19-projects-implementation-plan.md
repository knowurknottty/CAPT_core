# CAPT Projects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent CAPT Projects with instructions, chats, quarantined-cleared files, Skill Foundry references, links, workspace defaults, governance defaults, and Council defaults without turning Project state into RuntimeService authority.

**Architecture:** Projects are a dedicated encrypted/private local metadata store, separate from the native session cache and EventStore. Project content is eligible context only. RuntimeService/context assembly receives an explicit `ProjectContextReference` snapshot/digest at approval time and chooses what enters the governed ContextPack.

**Tech Stack:** Swift 6/CryptoKit/Keychain for native Project persistence and UI; Python operator projection only where RuntimeService/context assembly needs deterministic Project references; existing Skill Foundry IDs, `FileReference`, Workspace descriptors, native session IDs.

**Spec:** `docs/superpowers/specs/2026-08-19-public-release-quarantine-projects-council-design.md` Part III §§19-23.

## Global Constraints

- Project != Mission.
- Project membership != ContextPack inclusion.
- Project instructions are visible user-editable context, never hidden system authority.
- Project Files must reference Secure Intake `FileReference`s only.
- Project Skills do not bypass Skill Foundry lifecycle/permissions.
- Workspace selection does not imply write permission.
- Project edits must be RuntimeService-ledger neutral.

## File Structure

**Create:**
- `CAPTCoreDesktop/CAPTProjectModels.swift`
- `CAPTCoreDesktop/CAPTEncryptedProjectStore.swift`
- `CAPTNativeMac/Views/ProjectsView.swift`
- `CAPTNativeMac/Views/ProjectCustomizeView.swift`
- `CAPTNativeMac/Views/ProjectPickerView.swift`
- `CAPTCoreDesktopTests/CAPTProjectModelsTests.swift`
- `CAPTCoreDesktopTests/CAPTProjectStoreTests.swift`
- `capt_ui/operator/project_context.py`
- `tests/capt_ui/test_project_context.py`

**Modify:**
- `CAPTNativeSessionStore.swift` to add non-authoritative Project membership references to sessions.
- `CAPTNativeChatWorkspace.swift` for add/move/remove membership helpers.
- `CAPTOperatorStore.swift` for Project selection/store coordination.
- `SidebarView.swift` for Projects navigation and chat context menu.
- `CAPTBackgroundRuntime.swift` / approval request bridge to carry explicit Project context reference when present.

---

### Task 1: Project domain model

**Interfaces:**
- Produces `CAPTProject`, `CAPTProjectGovernanceDefaults`, `CAPTProjectWorkspace`, `CAPTProjectLink`, `CAPTProjectFileRef`, `CAPTProjectSkillRef`.

- [ ] **Step 1: Write RED Codable/equality tests**

```swift
@Test func projectRoundTripsDeterministically() throws {
    let p = CAPTProject(
        id: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
        name: "Release Sprint",
        createdAt: Date(timeIntervalSince1970: 1),
        updatedAt: Date(timeIntervalSince1970: 2),
        instructions: "Use repository authority.",
        chatIDs: [], fileRefs: [], skillRefs: [], links: [],
        workspace: nil,
        governance: .default,
        councilDefaults: nil
    )
    let encoded = try JSONEncoder.captDeterministic.encode(p)
    #expect(try JSONDecoder().decode(CAPTProject.self, from: encoded) == p)
}
```

- [ ] **Step 2: Implement focused Sendable/Codable types**

`CAPTProject` fields match the approved conceptual model. `instructions` is plain user-visible text. Links store stable IDs + URL + optional snapshot metadata, not fetched page bytes.

- [ ] **Step 3: Add hard validation**

Project name trimmed/non-empty/max 128 chars; link URLs require `http` or `https`; duplicate ref IDs collapse deterministically; `workspace.writeAllowed` defaults false.

- [ ] **Step 4: Run GREEN and commit**

```bash
swift test --filter CAPTProjectModelsTests
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(projects): add project domain model"
```

---

### Task 2: Dedicated encrypted Project store

**Interfaces:**
- Produces `CAPTEncryptedProjectStore.load() -> [CAPTProject]` and `save(_:)`.
- Storage file: `~/.capt/ui/classic_native_projects.enc`.
- Keychain service/account distinct from session cache.

- [ ] **Step 1: Write RED store tests with injected key provider**

Test create/load, atomic replacement, malformed ciphertext, permissions, and schema-version rejection.

- [ ] **Step 2: Implement encrypted store using existing session-store pattern without sharing keys**

Keychain defaults:

```swift
service: "com.inversionlabs.capt.native-project-store"
account: "project-store-key-v1"
```

File/directory permissions remain `0600`/`0700`.

- [ ] **Step 3: Add explicit envelope schema**

```swift
struct CAPTProjectStoreEnvelope: Codable, Sendable {
    let schemaVersion: Int // initial 1
    let projects: [CAPTProject]
}
```

Reject unknown future schema versions with a typed error; do not silently decode as v1.

- [ ] **Step 4: Run tests/commit**

```bash
swift test --filter CAPTProjectStoreTests
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(projects): persist encrypted project metadata"
```

---

### Task 3: Session Project membership semantics

**Interfaces:**
- `CAPTNativeSession` gains `projectIDs: [UUID]` and `primaryProjectID: UUID?` with backward-compatible defaults.
- Workspace methods: `addSession(_:toProject:)`, `moveSession(_:toProject:)`, `removeSession(_:fromProject:)`.

- [ ] **Step 1: Write RED migration/backward tests**

Decode a legacy session fixture without Project fields and assert empty membership. Add/move/remove must not alter `missionID`, messages, provider/model, pending approval, or timestamps except the session's own `updatedAt`.

- [ ] **Step 2: Implement membership operations**

`Add` preserves existing memberships. `Move` sets primary Project and optionally removes prior primary membership only; other memberships remain. `Remove` clears membership and primary if matching.

- [ ] **Step 3: Run session/workspace tests and commit**

```bash
swift test --filter CAPTNative

git add capt_ui/surfaces/desktop_swift
git commit -m "feat(projects): add chat project membership"
```

---

### Task 4: Projects and Customize UI

**Interfaces:**
- Produces Projects navigation and `ProjectCustomizeView` tabs/sections.

- [ ] **Step 1: Write store/view-model tests**

Create/update/delete Project, edit instructions, attach existing FileReference, Skill ID, link, Workspace, governance defaults. Assert changes persist and no runtime calls are made.

- [ ] **Step 2: Implement `ProjectsView`**

Project list + New Project button. Selecting opens Sessions / Customize-style navigation.

- [ ] **Step 3: Implement Customize sections**

Exactly:

```text
Instructions
Files
Skills
Links
Workspace
Governance
Council Defaults
```

Files picker here lists already-cleared FileReferences and may invoke Attach Files -> Secure Intake, never direct Project byte ingestion.

- [ ] **Step 4: Implement validation UX**

Invalid URL/name shows local human-readable error. Workspace write toggle defaults off and uses explicit confirmation copy before enabling.

- [ ] **Step 5: Run Swift tests/build and commit**

```bash
swift test
swift build --product CAPTNativeMac
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add CAPT Projects customize surface"
```

---

### Task 5: Chat right-click menu and Project navigation

**Interfaces:**
- Existing chat/session rows gain `.contextMenu` actions.

- [ ] **Step 1: Write command-state tests**

Given projects A/B and session S, assert menu commands call only workspace/project-store operations.

- [ ] **Step 2: Implement menu**

```text
Rename
Pin
Duplicate
────────────
Add to Project…
Move to Project…
Remove from Project
────────────
Export
Delete
```

Keep existing actions wired to current implementations where present; only add missing operations required by this plan.

- [ ] **Step 3: Add Project-filtered session list**

Inside a Project Sessions view show member chats without duplicating session storage.

- [ ] **Step 4: Verify no ledger mutation and commit**

Capture RuntimeService head/digest before/after Add/Move/Remove. Must be identical.

```bash
git add capt_ui/surfaces/desktop_swift
git commit -m "feat(mac): add chat project context menu"
```

---

### Task 6: Deterministic Project context reference

**Interfaces:**
- Python produces `ProjectContextReference`:

```python
@dataclass(frozen=True)
class ProjectContextReference:
    project_id: str
    project_digest: str
    instructions_digest: str
    file_refs: tuple[str, ...]
    skill_refs: tuple[str, ...]
    link_refs: tuple[str, ...]
    workspace_ref: str | None
```

- Swift sends the reference only when a Project is selected for a governed request.

- [ ] **Step 1: Write RED digest tests**

Same normalized Project -> same digest regardless of internal dictionary ordering. Updating instructions/file refs changes digest. Project membership alone does not become prompt text.

- [ ] **Step 2: Implement `capt_ui/operator/project_context.py` normalization**

Use sorted IDs/normalized URL strings and canonical JSON before SHA-256. Do not include mutable UI display state.

- [ ] **Step 3: Bind reference into approval/context selection**

Extend the model approval intent/binding with optional `projectContextRef` and its digest. RuntimeService reads only the referenced eligible material through the context pipeline; it never trusts the UI to claim that content was included.

- [ ] **Step 4: Add digest-mutation authority test**

Approve with Project digest A, mutate offered digest/content to B at execution; expect `AUTHORITYVIOLATION` / project-context binding mismatch before DriverRun dispatch.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/operator capt_runtime desktop tests capt_ui/surfaces/desktop_swift
git commit -m "feat(projects): bind project context eligibility to approval"
```

---

### Task 7: Project subsystem acceptance

- [ ] **Step 1: Full Swift store/UI regression**

```bash
cd capt_ui/surfaces/desktop_swift
swift test
swift build --product CAPTNativeMac
```

- [ ] **Step 2: Python context-binding tests**

```bash
python -m pytest tests/capt_ui/test_project_context.py tests/capt_runtime/test_prompt_approval_binding.py -q
```

- [ ] **Step 3: Public workflow acceptance**

Create Project → set instructions → add cleared file → add Skill ref → add link → select read-only repo workspace → add existing chat → create new chat inside Project → verify visible Project chip/context.

- [ ] **Step 4: Authority acceptance**

Project CRUD and membership keep EventStore head/digest unchanged. Governed prompt using Project context advances ledger only through ordinary approval/admission execution.

- [ ] **Step 5: Full Python suite alone**

```bash
python -m pytest -q
```
