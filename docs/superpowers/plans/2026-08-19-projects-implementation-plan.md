# CAPT Projects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent CAPT Projects with instructions, chats, cleared files, Skill Foundry references, links, workspace defaults, governance defaults, and Council defaults without turning Project state into RuntimeService authority.

**Architecture:** Projects use a dedicated encrypted local metadata store, separate from native session cache and EventStore. Project content is eligible context only. RuntimeService/context assembly receives an explicit deterministic `ProjectContextReference` at approval time and remains authoritative about what enters ContextPack.

**Tech Stack:** Swift 6/CryptoKit/Keychain; Python deterministic Project-context projection; existing Skill Foundry IDs, Secure Intake `FileReference`, Workspace descriptors, native sessions.

**Spec:** `docs/superpowers/specs/2026-08-19-public-release-quarantine-projects-council-design.md` Part III §§19-23.

## Global Constraints

- Project != Mission.
- Project membership != ContextPack inclusion.
- Project instructions are visible user-editable context, never hidden authority.
- Project Files reference Secure Intake `FileReference`s only.
- Project Skills do not bypass Skill Foundry lifecycle/permissions.
- Workspace selection does not imply write permission.
- Project CRUD/membership must be RuntimeService-ledger neutral.

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
- `CAPTNativeSessionStore.swift` for backward-compatible Project membership refs.
- `CAPTNativeChatWorkspace.swift` for add/move/remove membership helpers.
- `CAPTOperatorStore.swift` for Project store/selection coordination.
- `SidebarView.swift` for Projects navigation + chat context menu.
- `CAPTBackgroundRuntime.swift` / approval bridge for optional Project context ref.

---

### Task 1: Project domain model

**Interfaces:** Produces `CAPTProject`, `CAPTProjectGovernanceDefaults`, `CAPTProjectWorkspace`, `CAPTProjectLink`, `CAPTProjectFileRef`, `CAPTProjectSkillRef`.

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
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    let encoded = try encoder.encode(p)
    #expect(try JSONDecoder().decode(CAPTProject.self, from: encoded) == p)
}
```

- [ ] **Step 2: Implement exact model/defaults**

```swift
public struct CAPTProjectGovernanceDefaults: Codable, Equatable, Sendable {
    public var verificationRequired: Bool
    public var allowedProviderIDs: [String]
    public var maxWallClockSeconds: Int?
    public var maxCostUSD: Double?
    public static let `default` = CAPTProjectGovernanceDefaults(
        verificationRequired: true, allowedProviderIDs: [], maxWallClockSeconds: nil, maxCostUSD: nil
    )
}
```

`CAPTProject` mirrors the approved conceptual fields. `instructions` is plain visible text. Links store stable ID + URL + optional retrieval metadata, not fetched page bodies.

- [ ] **Step 3: Add validation**

Name trimmed/non-empty/max 128 chars. URLs require `http`/`https`. Duplicate refs collapse deterministically. Workspace `writeAllowed` defaults false.

- [ ] **Step 4: Run GREEN and commit**

```bash
cd capt_ui/surfaces/desktop_swift
swift test --filter CAPTProjectModelsTests
git add .
git commit -m "feat(projects): add project domain model"
```

---

### Task 2: Dedicated encrypted Project store

**Interfaces:** `CAPTEncryptedProjectStore.load() -> [CAPTProject]`, `save(_:)`; file `~/.capt/ui/classic_native_projects.enc`.

- [ ] **Step 1: Write RED store tests**

Use injected key provider. Cover create/load, atomic replacement, malformed ciphertext, unknown schema version, and permissions.

- [ ] **Step 2: Implement store using the existing session-store cryptographic pattern but a separate key**

```swift
service: "com.inversionlabs.capt.native-project-store"
account: "project-store-key-v1"
```

Directory/file permissions `0700`/`0600`.

- [ ] **Step 3: Add versioned envelope**

```swift
struct CAPTProjectStoreEnvelope: Codable, Sendable {
    let schemaVersion: Int
    let projects: [CAPTProject]
}
```

Initial schema is 1. Unknown future schema versions throw a typed store error; do not silently coerce.

- [ ] **Step 4: Run GREEN and commit**

```bash
swift test --filter CAPTProjectStoreTests
git add .
git commit -m "feat(projects): persist encrypted project metadata"
```

---

### Task 3: Session Project membership semantics

**Interfaces:** `CAPTNativeSession` gains `projectIDs: [UUID]` and `primaryProjectID: UUID?` with decode defaults. Workspace gains add/move/remove helpers.

- [ ] **Step 1: Write RED backward-compatibility tests**

Decode legacy session JSON with no Project fields -> empty memberships. Add/move/remove cannot change `missionID`, messages, provider/model, or pending approval.

- [ ] **Step 2: Implement semantics**

`Add`: preserve all current memberships. `Move`: set new primary and remove only prior primary membership if present; preserve secondary memberships. `Remove`: remove one membership and clear primary if it matches.

- [ ] **Step 3: Run/commit**

```bash
swift test --filter CAPTNative
git add .
git commit -m "feat(projects): add chat project membership"
```

---

### Task 4: Projects / Customize UI

**Interfaces:** Project list/navigation plus Customize sections.

- [ ] **Step 1: Write store/view-model tests**

Create/update/delete Project; edit instructions; add cleared FileReference, Skill ID, link, Workspace, governance defaults. Assert persistence and zero runtime calls.

- [ ] **Step 2: Implement `ProjectsView`**

Project list + New Project. Selecting Project exposes Sessions and Customize.

- [ ] **Step 3: Implement exact Customize sections**

```text
Instructions
Files
Skills
Links
Workspace
Governance
Council Defaults
```

Files list only cleared refs and may launch Secure Intake. Skills list Skill Foundry refs. Workspace write defaults off.

- [ ] **Step 4: Run/build/commit**

```bash
swift test
swift build --product CAPTNativeMac
git add .
git commit -m "feat(mac): add CAPT Projects customize surface"
```

---

### Task 5: Chat right-click Project menu

**Interfaces:** Existing chat rows gain `.contextMenu` Project actions.

- [ ] **Step 1: Write command-state tests**

Given Projects A/B and Session S, Add/Move/Remove modify membership/project store only.

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

Wire existing actions to existing implementations; add only missing actions required here.

- [ ] **Step 3: Add Project-filtered Sessions view**

Show member chats by reference; do not duplicate session content.

- [ ] **Step 4: Ledger-neutrality proof and commit**

Record head/digest before and after Add/Move/Remove; identical.

```bash
git add .
git commit -m "feat(mac): add chat project context menu"
```

---

### Task 6: Deterministic Project context reference

**Interfaces:** Python `ProjectContextReference` with stable digest.

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

- [ ] **Step 1: Write RED digest tests**

Same normalized Project -> same digest regardless of input ordering. Instructions/file/workspace changes -> new digest. Membership alone is never prompt text.

- [ ] **Step 2: Implement canonical normalization**

Sorted IDs and normalized URLs; canonical JSON before SHA-256. Exclude UI display state.

- [ ] **Step 3: Bind optional reference into approval/context selection**

Approval intent carries exact Project reference/digest. Runtime context pipeline resolves eligible material and records what was actually selected.

- [ ] **Step 4: Mutation test**

Approve digest A, offer B at execution -> `AUTHORITYVIOLATION` before DriverRun dispatch.

- [ ] **Step 5: Commit**

```bash
git add capt_ui/operator/project_context.py capt_runtime desktop tests capt_ui/surfaces/desktop_swift
git commit -m "feat(projects): bind project context eligibility to approval"
```

---

### Task 7: Project subsystem acceptance

- [ ] Run full Swift tests/build.
- [ ] Run `python -m pytest tests/capt_ui/test_project_context.py tests/capt_runtime/test_prompt_approval_binding.py -q`.
- [ ] Workflow: create Project -> instructions -> cleared file -> Skill -> link -> read-only repo -> existing chat -> new Project chat.
- [ ] Verify Project CRUD/membership alone leaves EventStore head/digest unchanged.
- [ ] Run full Python suite alone with zero failures.
