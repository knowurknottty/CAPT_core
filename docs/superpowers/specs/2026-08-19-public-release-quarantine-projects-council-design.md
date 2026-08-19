# CAPT Public Release: Secure Intake, Projects, Human-First Results, and Council Design

Status: `DESIGN_FOR_OWNER_REVIEW`

Base branch: `fix/local-openai-compatible-provider-r1`
Base SHA: `5ec276e891cf9fbfff2ce619a742f4b0f210c1ee`
Design branch: `design/public-release-quarantine-projects-council-r1`
Date: 2026-08-19

## 1. Purpose

This design adds four connected public-release capabilities without weakening CAPT's existing authority model:

1. **Secure Intake / Quarantine** for arbitrary user uploads.
2. **Human-first result rendering** with exact-copy code blocks and one-click raw JSON.
3. **CAPT Projects** with instructions, chats, files, skills, links, workspaces, and governance defaults.
4. **Composer capability selection** including Deep Research, workspace/repo selection, Active Apps, screenshots, clipboard history, and a configurable Cohort Council.

The public-facing principle is simple:

> CAPT should feel approachable by default while preserving forensic depth one click away.

The architectural principle is stricter:

> The native application may organize, inspect, render, and request. It may not manufacture RuntimeService authority.

## 2. Non-negotiable CAPT invariants

The following invariants remain authoritative across all four feature areas:

- Evidence is not truth.
- Evidence is not verification.
- Verification is not automatically a ClaimGuard-accepted claim.
- Successful driver execution is not task completion.
- Task completion is not mission completion.
- Project membership is not runtime authority.
- Project instructions are not hidden authority.
- A file being scanned is not permission to use it.
- A file being "apparently safe" is not proof of harmlessness.
- A Cohort is a model/provider cognitive source; a Vessel is not a model.
- UI state, project state, and council configuration cannot fabricate Mission, Task, DriverRun, Evidence, Verification, Claim, Capability, Lease, or other canonical RuntimeService state.
- Consequential model execution remains governed through the existing approval/admission boundary.

Any implementation that violates these invariants is rejected even if the user experience appears correct.

## 3. Product decomposition

The release tranche is split into four stacked implementation subprojects sharing contracts and storage primitives:

### 3.1 Secure Intake / Quarantine

Foundation for all files later referenced by chats or Projects.

### 3.2 Projects / Spaces

Persistent organizational and context-eligibility layer for chats, files, instructions, skills, links, workspace scope, and council defaults.

### 3.3 Human-First Result Presentation

Public default renderer for CAPT responses, evidence, scans, errors, and structured runtime results.

### 3.4 Composer Capability Palette and Cohort Council

Prompt-box capability selector plus Deep Research, workspace/app context, and governed multi-model/multi-vessel planning.

No later subproject may bypass Secure Intake for user-uploaded file bytes.

---

# PART I — SECURE INTAKE / QUARANTINE

## 4. Threat model

An uploaded file is treated as hostile before content inspection.

Potential hazards include:

- malicious executables or scripts;
- disguised MIME/type mismatches;
- malformed parser payloads;
- document macros or embedded active content;
- archive traversal, symlink escape, decompression bombs, or recursive archive bombs;
- polyglot files;
- suspicious trailing data;
- malicious image/media parser inputs;
- steganographic payloads or unusual data channels;
- forged, inconsistent, or manipulated metadata;
- embedded credentials/secrets;
- hostile filenames/path components;
- files designed to provoke unsafe tool execution;
- content that is harmless as bytes but dangerous when passed to an interpreter, shell, office suite, browser, or privileged parser.

CAPT does not assume a scanner can prove absence of malicious content.

## 5. Intake contract

### 5.1 "Accept all uploads" semantics

CAPT does not maintain a file-extension allowlist for ordinary uploaded files.

A user may select any regular file and CAPT stores its bytes in quarantine before interpretation.

The following are not treated as normal upload files:

- directories;
- filesystem sockets;
- FIFOs/pipes;
- block/character devices;
- other special filesystem nodes.

Directories and repositories are handled by the separate Workspace selection flow.

### 5.2 Intake state machine

```text
SELECTED
  -> COPYING_TO_QUARANTINE
  -> STORED_OPAQUE
  -> SCANNING
  -> SCAN_COMPLETE
  -> AWAITING_USER_DISPOSITION

Failure paths:
COPY_FAILED
SCAN_PARTIAL
SCAN_FAILED
QUARANTINE_BLOCKED
DELETED
```

A file cannot become context-eligible while in `SELECTED`, `COPYING_TO_QUARANTINE`, `STORED_OPAQUE`, or `SCANNING`.

## 6. Quarantine storage

Canonical local root:

```text
~/.capt/quarantine/<upload-id>/
    original/blob
    derived/
    scan/
    manifest.json
```

Requirements:

- generated opaque upload ID; never use user filename as a directory path;
- original filename stored only as metadata;
- canonical path verification before every read/write;
- private directory/file permissions;
- no execute bits;
- original bytes immutable after intake;
- SHA-256 calculated during/after copy and persisted;
- scan/derived output separated from original bytes;
- no scanner receives an untrusted path outside the quarantine root;
- quarantine object is not added to a model ContextPack automatically;
- deletion removes original and derived material according to the user's explicit disposition and leaves only the minimum audit metadata CAPT is configured to retain.

The first implementation should use local filesystem storage because CAPT is local-first. Storage abstraction may later support encrypted-at-rest project vaults without changing the intake contract.

## 7. Scanner isolation

Parsers/scanners do not run inside RuntimeService authority or the Swift UI process.

Use a dedicated **QuarantineScanner execution boundary** with:

- read-only access to the quarantined original;
- write access only to its own `scan/` and bounded temporary directories;
- network denied by default;
- CPU, wall-clock, memory, recursion, output-size, and child-process limits;
- sanitized environment;
- no inheritance of provider/API credentials;
- no shell interpolation of user-controlled names;
- scanner version and availability recorded in the scan report;
- scanner failure represented as uncertainty, never as "clean".

Scanner adapters are capabilities, not mandatory dependencies. The report must distinguish `not_installed`, `not_applicable`, `passed_without_indicator`, `indicator_found`, and `scanner_error`.

## 8. Baseline scan pipeline

Every upload receives a common baseline:

1. size and SHA-256;
2. extension and filename metadata;
3. magic/MIME identification from bytes;
4. extension-vs-magic consistency;
5. malformed/truncated-header checks where available;
6. polyglot/multiple-signature heuristics where available;
7. trailing-data indicators;
8. archive/container identification;
9. secrets/high-risk textual indicators where applicable;
10. malware/signature scanner adapters where installed;
11. YARA-style rules where configured;
12. format-specific metadata/content inspection;
13. scan engine/version inventory;
14. final human-readable disposition summary.

The final status vocabulary must avoid false certainty. Recommended top-level states:

```text
NO_KNOWN_INDICATORS
SUSPICIOUS
HIGH_RISK
BLOCKED
INCOMPLETE_SCAN
SCAN_ERROR
```

`NO_KNOWN_INDICATORS` explicitly means the available checks found no indicators; it does not mean the file is proven safe.

## 9. Archive and container handling

Archive processing is derived inspection, never direct extraction into a project/workspace.

Required defenses:

- normalized member paths;
- reject absolute paths;
- reject `..` traversal after normalization;
- reject symlink/hardlink escapes;
- maximum nesting depth;
- maximum extracted file count;
- maximum total uncompressed bytes;
- maximum expansion ratio;
- maximum single-member size;
- time budget;
- recursion detection by digest where useful;
- nested content remains inside `derived/`;
- executable permission is never preserved from the archive.

Archive children receive child scan records linked to the parent upload.

## 10. Image/photo/media inspection

Images and media receive additional inspection.

### 10.1 Metadata

Report whether metadata exists and summarize:

- EXIF/IPTC/XMP presence;
- GPS/location fields;
- timestamp fields and internal consistency;
- camera/device/software fields;
- orientation/dimensions;
- embedded thumbnails and mismatch indicators;
- color profiles;
- encoder/editor tags;
- metadata structure errors;
- duplicated/conflicting tags;
- impossible or suspicious values;
- signs that metadata may have been rewritten or altered.

CAPT must not claim metadata is authentic merely because it is structurally valid.

Recommended wording:

```text
Metadata present: Yes
Structure: Valid / unusual / malformed
Internal consistency: Normal / inconsistent / insufficient evidence
Alteration indicators: None detected / indicators detected / cannot determine
```

### 10.2 Steganography

Steganography scanning is heuristic.

Possible adapters/techniques may include:

- LSB/statistical anomaly checks;
- channel/plane anomaly checks;
- unusual palette or alpha-channel behavior;
- entropy and compressibility anomalies;
- appended/trailing payload detection;
- embedded-file signatures;
- known-tool-specific checks when available;
- comparison of declared image dimensions to decoded data;
- thumbnail/main-image inconsistency;
- format-specific stego scanners.

CAPT may report:

```text
No steganographic indicators detected by available checks.
```

CAPT must never report:

```text
No steganography exists.
```

unless a future narrowly-defined proof domain can actually support that statement.

## 11. Document inspection

Where applicable inspect for:

- Office macros/VBA;
- OLE embedded objects;
- external template/relationship links;
- PDF JavaScript/actions/embedded files/forms;
- shell/script content;
- suspicious launch actions;
- active hyperlinks and unusual schemes;
- malformed object graphs;
- document metadata anomalies.

Opening/rendering a document is separate from scanning it and must use an appropriate sandboxed renderer/parser.

## 12. User disposition after scan

After scan CAPT asks what to do.

Public UI actions:

```text
Use in this chat
Add to Project…
Extract/index safe content
Inspect more deeply
View metadata
View full scan details
Reveal quarantined copy
Keep quarantined
Delete
```

High-risk/blocked files may restrict actions. Example: a confirmed malicious executable may remain inspectable as inert evidence but cannot be promoted into a runnable workspace.

Promotion creates a **FileReference**, not a byte copy into hidden prompt state.

## 13. FileReference model

Minimum conceptual fields:

```text
FileReference
- uploadId
- originalName
- sha256
- byteCount
- detectedType
- scanStatus
- scanDigest
- quarantinePathRef
- promotedAt?
- projectIds[]
- allowedUses[]
- provenance
```

`allowedUses` may distinguish `chat_context`, `project_reference`, `content_extraction`, `forensic_inspection`, and future explicit capabilities.

---

# PART II — HUMAN-FIRST RESULT PRESENTATION

## 14. Presentation contract

Every structured CAPT result has three layers:

1. **Human View** — default.
2. **Technical Details** — one action away.
3. **Raw Envelope / JSON** — one action away, collapsed by default.

The raw authoritative/provenance data remains available without forcing public users to read it.

## 15. Public default behavior

Do not render raw JSON as ordinary assistant output unless the user explicitly requests raw mode.

Default result cards should expose:

- what happened;
- what CAPT knows;
- what CAPT does not know;
- severity/status;
- recommended next action;
- evidence/verification state where relevant.

Debug identifiers are secondary details, not the main message.

## 16. Code blocks

CAPT code blocks should match the useful behavior users expect from ChatGPT-style interfaces:

- language label;
- exact-copy button;
- copied content equals underlying literal code bytes/text represented by the message;
- indentation preserved;
- no smart-quote substitution;
- no hidden line numbers in copied text;
- optional wrap/scroll;
- raw source accessible when the display renderer performs syntax highlighting.

Copying a code block must not copy surrounding explanatory prose unless the user chooses a whole-message copy action.

## 17. Raw details disclosure

Every CAPT structured response can expose a disclosure control such as:

```text
Raw details ▸
```

Expanded content may include:

- command/result envelope;
- mission/task/DriverRun IDs;
- prompt/evidence digests;
- provider provenance;
- verification state;
- ledger sequence/digest information;
- raw JSON.

The raw panel is read-only by default.

## 18. Presentation preferences

Initial release may expose a global preference:

```text
Normal
Detailed
Forensic
Raw
```

`Normal` is the public default.

Changing presentation mode changes rendering only; it does not change RuntimeService authority, verification, or evidence semantics.

---

# PART III — CAPT PROJECTS

## 19. Project concept

A CAPT Project is a persistent organizational/context-eligibility object.

It is not a Mission, not RuntimeService state authority, and not automatically a ContextPack.

Conceptual model:

```text
CAPTProject
- projectId
- name
- createdAt
- updatedAt
- instructions
- chatRefs[]
- fileRefs[]
- skillRefs[]
- linkRefs[]
- workspaceConfig?
- governanceDefaults
- councilDefaults?
- memoryPolicyRef?
```

## 20. Project Customize surface

The public UI should follow the successful mental model visible in Perplexity-style Spaces while using CAPT semantics.

Sections:

### Instructions

Persistent project instructions visible and editable by the user.

At execution time they become an explicit named context source with provenance, never invisible system authority.

### Files

Only promoted/eligible `FileReference`s from Secure Intake.

Adding a file to a Project never erases quarantine provenance or scan state.

### Skills

References to CAPT Skill Foundry skills/capabilities.

Project inclusion does not bypass skill lifecycle, permission, verification, compatibility, or governance rules.

### Links

Prioritized websites/resources for tasks in the Project.

CAPT distinguishes:

- configured link;
- fetched snapshot;
- retrieval timestamp;
- source provenance;
- current/live site state if fetched later.

### Workspace

Optional folder/repository root and capability defaults.

### Governance

Project-level defaults for verification requirements, provider policy, time/cost ceilings, memory policy, and Council defaults.

## 21. Chat membership

Chats remain sessions with their own immutable/historical execution references.

Project membership is an organizational relationship.

Context menu on a chat:

```text
Rename
Pin
Duplicate
----------------
Add to Project…
Move to Project…
Remove from Project
----------------
Export
Delete
```

Recommended semantics:

- `Add to Project` adds a reference and preserves any existing memberships.
- `Move to Project` changes the primary organizational location but does not rewrite historical CAPT state.
- `Remove from Project` removes membership only.

A future release may support multiple Project memberships per chat. The data model should not prevent it.

## 22. Project context assembly

Project material is **eligible context**, not guaranteed prompt inclusion.

Before a governed model run, CAPT's context pipeline selects from:

- project instructions;
- selected/promoted files;
- links/snapshots;
- workspace state;
- prior mission evidence;
- memory policy;
- explicit user selections.

The resulting ContextPack records provenance and remains subject to budget/policy gates.

Project configuration never bypasses context-size, time, cost, authority, or verification constraints.

## 23. Project storage

Project metadata should use a dedicated local persistent store with:

- schema versioning;
- atomic updates;
- stable IDs;
- migration support;
- private permissions;
- references rather than duplicated large file payloads;
- deterministic serialization/digests where those digests become execution inputs.

Do not overload encrypted chat-session cache as the authoritative Project store.

---

# PART IV — COMPOSER CAPABILITY PALETTE

## 24. Composer UX

The prompt composer gains a capability button/menu modeled on the useful discoverability of Perplexity's prompt box while preserving CAPT semantics.

Recommended menu:

```text
Research
  Deep Research

Council
  Cohort Council

Context
  Attach Files
  Folder / Repo Workspace
  Active Apps
  Screenshot
  Clipboard History

Project
  Current Project
  Switch Project…
```

Active selections render as removable chips above/inside the composer so the operator can see what is about to affect the request.

## 25. Attach Files

`Attach Files` always routes through Secure Intake.

There is no direct "picker -> model prompt" path.

## 26. Folder / Repo Workspace

Workspace selection is distinct from file upload.

Options:

```text
Choose Folder…
Choose Git Repository…
Recent Workspaces…
```

Workspace snapshot/provenance should include, when applicable:

- canonical root path;
- Git repository detection;
- HEAD SHA;
- branch/ref;
- dirty/clean state;
- selected read/write scope;
- excluded paths;
- capability lease/grant references for consequential operations.

Selecting a workspace does not grant write authority automatically.

## 27. Active Apps

`Active Apps` opens an explicit selector of discoverable applications/windows.

CAPT receives only the app/window/context selected by the user and only through an adapter/capability that supports it.

No global "inspect every application" privilege is implied.

Each captured app snapshot records provenance such as:

- application identity;
- selected window/resource;
- capture time;
- adapter/method;
- permissions used;
- digest where practical.

## 28. Screenshots

Screenshot selection supports explicit:

- screen;
- window;
- region;
- recent screenshot.

Captured images route through the same image metadata/security analysis where they enter persisted file context, while ephemeral screenshot context may use a lighter in-memory path only if it cannot escape the same safety/authority rules.

## 29. Clipboard History

Clipboard access is explicit and scoped.

The UI shows recent items for user selection. CAPT does not silently vacuum clipboard history into context.

Sensitive-type handling and retention controls are required before a broad persistent clipboard history feature ships.

---

# PART V — DEEP RESEARCH

## 30. Deep Research semantics

Deep Research is a governed execution strategy, not a prompt adjective.

Conceptual flow:

```text
User question
  -> research decomposition
  -> source discovery
  -> retrieval
  -> source normalization/provenance
  -> claim/evidence graph
  -> adversarial source checking
  -> synthesis
  -> ClaimGuard / verification boundaries
```

The system must preserve:

- citations/provenance;
- unsupported/contested claims;
- source conflicts;
- uncertainty;
- retrieval timestamps;
- distinction between model synthesis and verified claims.

## 31. Resource envelope

Deep Research needs a workload-specific governed resource budget.

The current fixed provider wall-clock behavior is not sufficient for serious long-context research/code review.

Introduce a governed workload/time profile concept, for example:

```text
INTERACTIVE_CHAT
DEEP_RESEARCH
CODE_REVIEW_DEEP
LONG_CONTEXT_ANALYSIS
COUNCIL_SYNTHESIS
```

Each profile may define bounded:

- wall-clock budget;
- token/context budget;
- model/provider restrictions;
- maximum retries;
- maximum external retrievals;
- financial ceiling where applicable;
- parallelism ceiling.

A provider's context limit is not evidence that a requested workload can complete inside the current wall-clock budget.

---

# PART VI — COHORT COUNCIL

## 32. Terminology

### Cohort

A distinct model/provider cognitive source.

Examples: Qwen3.8 MTPLX, an OpenAI model, Claude, Gemini, GLM, DeepSeek, etc.

### Vessel

A bounded execution perspective/configuration using a Cohort.

A Vessel may specify:

- role/perspective;
- instructions;
- allowed tools/capabilities;
- context slice;
- verification assignment;
- output contract;
- recursion/iteration policy;
- resource budget.

A Vessel is not itself a model, process, or authority source.

## 33. Hard limits

Initial public-release limits:

```text
MAX_DISTINCT_COHORTS = 10
MAX_LOGICAL_VESSELS  = 111
```

These are logical configuration ceilings.

They do not imply 111 simultaneous model processes or 10 simultaneous full-context calls.

Execution Governor determines actual concurrency using provider limits, RAM, GPU/CPU pressure, cost ceilings, time budgets, leases, and workload policy.

## 34. Council builder

Council configuration surface should provide:

- selected Cohorts with provider/model identity;
- local/cloud classification;
- health/readiness;
- Vessel list and Cohort assignment;
- per-Vessel role/purpose;
- synthesis mode;
- resource estimate before dispatch;
- governance/verification profile;
- explicit `Use Council` action.

## 35. Council modes

Initial modes may include:

### Independent convergence

Vessels answer independently before synthesis.

### Adversarial review

One or more Vessels attack findings/claims from others.

### Debate

Bounded rounds with explicit arguments/counterarguments.

### Independent vote

Useful only for questions where voting is meaningful; vote count is not truth.

### Adversarial tournament

Candidate answers/patches are attacked and progressively refined under bounded rounds.

The default should favor **independent convergence + adversarial adjudication**, not social imitation between models.

## 36. Council execution architecture

Conceptual flow:

```text
CouncilPlan
  -> RuntimeService admission
  -> per-Vessel governed work orders
  -> bounded scheduler
  -> evidence from each Vessel
  -> adjudication/synthesis work order
  -> dissent/conflict preservation
  -> final human-readable result
```

Each Vessel run produces its own provenance/evidence identity.

The synthesizer may consume Vessel evidence but cannot rewrite it.

## 37. Dissent and consensus

CAPT must preserve disagreement.

Public result may render:

```text
7/10 cohorts support finding A
2 disagree
1 reports insufficient evidence
```

but the UI must not imply majority vote establishes truth.

Council output distinguishes:

- converged finding;
- minority finding;
- unresolved conflict;
- insufficient evidence;
- verified fact where separately proven;
- recommendation/opinion.

## 38. Council anti-correlation controls

Where feasible:

- independent first-pass prompts before exposure to sibling answers;
- randomized/specified order only when methodologically useful;
- explicit evidence requirements;
- no silent majority overwrite;
- model/provider identity retained in provenance;
- duplicate/near-identical models do not count as epistemically independent merely because they run in separate Vessels.

---

# PART VII — LAYERED ARCHITECTURE

## 39. Recommended component boundary

```text
Native Swift UI
  ├─ Quarantine UI
  ├─ Project UI
  ├─ Result Renderer
  ├─ Composer Capability Palette
  └─ Council Builder
           |
           v
Operator Plane
  ├─ QuarantineService / scanner adapters
  ├─ ProjectStore
  ├─ WorkspaceResolver
  ├─ AppContext adapters
  ├─ CouncilPlanner
  └─ PresentationProjection
           |
           v
RuntimeService / canonical CAPT authority
  ├─ capabilities / leases
  ├─ execution admission
  ├─ ContextPack selection
  ├─ evidence / verification / ClaimGuard
  ├─ model dispatch
  ├─ workload/time/resource governance
  └─ council execution authority
```

## 40. What belongs outside RuntimeService

Operator/presentation concerns:

- file picker;
- project list/order/color/icon;
- collapsed raw JSON state;
- syntax highlighting;
- code-block copy UI;
- menu/chip presentation;
- scanner UI progress;
- local project organization.

## 41. What must remain authoritative inside or behind RuntimeService

- consequential execution admission;
- capability/lease enforcement;
- model dispatch authority;
- exact prompt/context binding;
- evidence creation;
- verification transitions;
- ClaimGuard acceptance;
- workload/time/cost ceilings that gate execution;
- council run admission/scheduling semantics where execution authority is involved.

---

# PART VIII — SECURITY AND PRIVACY

## 42. Quarantine is not a content trust boundary by itself

Files remain untrusted even after copying into quarantine.

Security depends on scanner isolation, parser hardening, resource ceilings, and explicit promotion/use decisions.

## 43. No credential bleed

Quarantine scanners, metadata tools, document parsers, and media analyzers must not inherit:

- OpenAI/OpenRouter/provider keys;
- GitHub tokens;
- cloud credentials;
- unrelated user secrets.

## 44. Project privacy

Projects may contain sensitive instructions/files/links/workspace paths.

Public release requirements:

- local private storage by default;
- no implicit cloud synchronization;
- no sending Project material to a cloud model unless that material is selected into a governed execution whose provider policy permits it;
- provider/local-cloud status visible before consequential dispatch;
- deleting Project membership does not silently delete underlying evidence/file quarantine objects unless the user chooses deletion.

## 45. Active Apps and clipboard privacy

Both features require explicit user selection and OS permission handling.

No ambient/background harvesting is part of this release design.

---

# PART IX — UX ACCEPTANCE

## 46. Public user success criteria

A nontechnical user should be able to:

- drag/select an arbitrary file and understand that CAPT is checking it before use;
- see a readable scan result without reading JSON;
- inspect metadata/raw details if desired;
- decide what happens to the file;
- create a Project and add instructions/files/skills/links;
- right-click a chat and add/move it to a Project;
- choose a repo/folder workspace from the composer;
- enable Deep Research without knowing CAPT internals;
- open a Council builder, select models and perspectives, and understand approximate scope before running;
- copy code exactly with one click;
- expand raw JSON in one click when needed.

## 47. Expert user success criteria

An expert should be able to recover:

- hashes;
- raw scan output;
- scanner versions/status;
- file provenance;
- project/context provenance;
- raw runtime envelopes;
- model/provider provenance;
- individual Vessel evidence;
- dissent/conflicts;
- verification/ClaimGuard boundaries;
- workload/resource profile.

---

# PART X — TEST AND RELEASE GATES

## 48. Secure Intake gates

Minimum automated cases:

- arbitrary extension accepted as opaque regular file;
- special filesystem nodes rejected;
- filename traversal cannot escape quarantine;
- symlink archive member cannot escape extraction root;
- `../` archive path rejected;
- archive expansion ceiling enforced;
- recursive archive depth enforced;
- scanner timeout yields `INCOMPLETE_SCAN`, not safe/clean;
- unavailable scanner is surfaced;
- hash immutable across scan;
- file cannot become chat/project context before explicit disposition;
- EXIF GPS presence accurately surfaced;
- malformed EXIF does not crash intake;
- metadata inconsistency rendered as uncertainty;
- stego-negative wording says "no indicators detected", never proof of absence;
- scanners receive no provider credentials.

## 49. Presentation gates

- normal mode never dumps raw JSON as the primary answer;
- raw JSON reachable in one interaction;
- code copy returns exact underlying block text;
- raw/debug fields remain available after human rendering;
- presentation preference does not mutate RuntimeService state.

## 50. Project gates

- create/update/delete Project metadata atomically;
- chat membership changes do not rewrite historical runtime state;
- only promoted FileReferences are selectable as Project files;
- instructions have explicit provenance in context assembly;
- Project inclusion does not bypass Skill Foundry governance;
- workspace root canonicalization prevents path escape;
- deleting a Project does not silently delete referenced quarantine originals.

## 51. Composer/context gates

- Attach Files always enters Secure Intake;
- workspace selection is read-only unless separate write authority is granted;
- Active Apps requires explicit app/window choice;
- clipboard item must be explicitly selected;
- screenshots record capture provenance;
- chips accurately reflect the execution request and can be removed before dispatch.

## 52. Deep Research gates

- research run uses an explicit workload profile;
- wall-clock budget is visible/recorded;
- provider timeout is not conflated with context limit;
- retrieved claims retain source provenance;
- conflicting sources remain visible;
- model synthesis cannot mark itself verified.

## 53. Council gates

- reject >10 distinct Cohorts;
- reject >111 logical Vessels;
- 111 Vessels never implies 111-way uncontrolled concurrency;
- each Vessel has separate evidence/provenance identity;
- synthesizer cannot mutate/rewrite sibling evidence;
- dissent remains visible;
- majority does not auto-create verified truth;
- Council plan is frozen/bound before consequential dispatch;
- cancellation/resource limits work per plan and per Vessel;
- local/cloud provider use remains visible.

---

# PART XI — ROLLOUT ORDER

## 54. Phase A — Secure Intake / Quarantine

Deliver first because every later file feature depends on it.

Includes baseline scanner contract, image metadata/stego heuristics, archive safety, scan result UI, and explicit user disposition.

## 55. Phase B — Human-First Result Renderer

Land early because every subsequent feature produces structured results that public users must understand.

## 56. Phase C — Projects

Add persistent ProjectStore, instructions/files/skills/links/workspace/governance, Project UI, and chat context menus.

## 57. Phase D — Composer Context Palette

Attach Files, workspace/repo, screenshots, clipboard selection, Active Apps adapter framework.

## 58. Phase E — Deep Research workload profiles

Add research strategy and governed wall-clock/resource profile support.

## 59. Phase F — Cohort Council

Add CouncilPlan, 10-Cohort/111-Vessel limits, bounded scheduler, independent evidence, adversarial adjudication, and dissent-preserving synthesis.

The Council UI may be previewed before execution support is complete only if it is visibly disabled/non-operational. No fake execution path is permitted.

---

# PART XII — NON-GOALS FOR THIS TRANCHE

## 60. Explicit non-goals

- proving arbitrary files are malware-free;
- proving arbitrary images contain no steganography;
- automatically executing uploaded binaries/scripts;
- silently ingesting uploads into model context;
- background surveillance of all applications;
- automatic persistent capture of all clipboard contents;
- cloud-syncing every Project by default;
- treating Project instructions as higher authority than CAPT runtime governance;
- treating Council majority as verification;
- launching 111 concurrent local model processes;
- replacing RuntimeService with the Project or Council subsystem;
- weakening one-use approval/replay protections for convenience.

---

# PART XIII — DESIGN DECISIONS / SELF-REVIEW CHECKLIST

## 61. Decisions intentionally made

1. Upload bytes always enter quarantine before interpretation.
2. File extension does not determine acceptance.
3. Special filesystem objects are not ordinary uploads.
4. Scanner results express uncertainty instead of claiming universal safety.
5. Stego detection explicitly uses indicator language.
6. Project files are references to promoted quarantine objects.
7. Project configuration represents context eligibility, not guaranteed prompt inclusion.
8. Human-readable rendering is default; raw JSON remains one click away.
9. Workspace selection is separate from upload.
10. Active Apps/clipboard are explicit, scoped selections.
11. Deep Research is a workload/execution strategy with its own resource profile.
12. Council distinguishes Cohorts from Vessels.
13. Distinct Cohort ceiling is 10; logical Vessel ceiling is 111.
14. Logical Vessel count is decoupled from execution concurrency.
15. RuntimeService remains the consequential execution authority.

## 62. Authority self-review

Checked:

- No UI operation creates verified truth.
- No Project operation creates Mission/Task/DriverRun authority.
- No scan result is automatically permission to ingest/use a file.
- No Council vote becomes verification.
- No scanner/parser receives model-provider credentials by design.
- No upload path bypasses quarantine.
- No Project file bypasses promotion eligibility.
- No workspace selection implies write capability.
- No presentation setting alters authoritative state.
- No long-context capability claim is treated as sufficient wall-clock capacity.

## 63. Ambiguity self-review

Resolved in this design:

- "all uploads" = arbitrary regular files accepted as opaque bytes; directories use Workspace; special filesystem nodes rejected.
- "steganography check" = best-effort indicator detection, never universal proof of absence.
- "Project files" = secure references to scanned/promoted objects, not raw ungoverned ingestion.
- "Cohort count" = distinct model/provider identities, max 10.
- "Vessel count" = logical execution perspectives, max 111, not concurrency.
- "raw JSON available" = collapsed by default, one interaction away.
- "public version" = Normal/human-readable rendering is default.

## 64. Implementation gate

This document is a design specification only.

No implementation should begin until the owner reviews and approves this written spec. After approval, the next artifact is a concrete implementation plan generated from this exact design and base/head lineage.
