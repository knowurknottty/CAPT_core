# CAPT Initial Release ToolBroker + Terminal Backend Design

Date: 2026-08-19
Branch base: `5ec276e891cf9fbfff2ce619a742f4b0f210c1ee`
Status: approved architecture, implementation not started

## 1. Mission

Ship CAPT's initial general-purpose execution surface without making Hermes the runtime or creating a second authority plane.

CAPT will own tool admission, capability scope, effect classification, execution lifecycle, idempotency, recovery, provenance, evidence, and operator-visible readiness. Existing mature implementation code may be adapted behind CAPT interfaces when appropriate, but no adapter may bypass RuntimeService governance.

The initial terminal backend set is exactly:

1. `local`
2. `ssh`
3. `docker`

No Modal, Daytona, Vercel Sandbox, Singularity/Apptainer, or other backend is part of the initial release gate.

Browser automation for the initial release uses Chrome DevTools Protocol (CDP). Generic browser-agent or accessibility-driven browser automation is not the primary browser path.

## 2. Release tool set

The initial release target is the checked set from the approved operator configuration:

- Web Search & Scraping
- Browser Automation
- Terminal & Processes
- File Operations
- Code Execution
- Vision / Image Analysis
- Video Analysis
- Image Generation
- Video Generation
- BFL FLUX 3 Video
- Text-to-Speech
- Skills
- Task Planning
- Memory
- Context Engine
- Session Search
- Clarifying Questions
- Task Delegation
- Cron Jobs
- Computer Use
- A2A (Agent-to-Agent)

Explicitly excluded from the initial release gate because they were not selected:

- X (Twitter) Search
- Home Assistant
- Spotify
- Yuanbao
- BioCAPT

An excluded tool may remain present elsewhere in the repository, but it must not be advertised as part of the initial release completeness claim.

## 3. Authority model

RuntimeService and EventStore remain authoritative.

The native macOS app, CLI, TUI, and any setup surface are renderers/controllers only. They may request configuration changes and execution, but they do not own tool authority or effect settlement.

A new CAPT `ToolBroker` is the only general-purpose runtime entry point for tool execution. It sits below governed command admission and above implementation adapters.

The mandatory call chain is:

`operator surface -> authenticated RuntimeService command -> approval/capability admission -> ToolBroker -> adapter -> effect/result settlement -> EventStore/provenance/evidence`

No adapter may be invoked directly by a normal operator path.

## 4. Tool descriptor contract

Every tool is registered with a typed descriptor containing at minimum:

- stable tool id
- display name
- tool family
- supported operations
- required capability scopes
- effect class per operation
- supported terminal backends, if applicable
- platform constraints
- executable/runtime prerequisites
- credential prerequisites
- model modality prerequisites
- network requirements
- timeout/cancellation support
- idempotency support level
- artifact outputs
- evidence/provenance policy
- readiness probe

Tool readiness is one of:

- `available`
- `degraded`
- `unavailable`
- `unverified`

`unavailable` and `unverified` are first-class truthful states. The UI must not turn installed code, a configured credential reference, or a plausible environment into a PASS claim.

## 5. Capability and approval semantics

Permissions are operation-scoped, not a single monolithic `tools` grant.

Examples:

- `file.read:/repo`
- `file.write:/repo/subtree`
- `terminal.exec:local`
- `terminal.exec:docker:<profile>`
- `terminal.exec:ssh:<host-profile>`
- `browser.cdp.read:<session>`
- `browser.cdp.interact:<session>`
- `network.fetch:<host-pattern>`
- `cron.create:<namespace>`

A lease binds tool id, operation, target, backend, scope, expiry, usage ceiling, and operator/session identity. Revocation is terminal for subsequent checks.

Approval policy may group low-risk read operations, but mutating/external effects must remain distinguishable by operation and target. One approval must never silently widen into unrelated tool authority.

## 6. Effect taxonomy

ToolBroker classifies each operation before dispatch:

### Pure/read-only

Examples: DOM query, file read, search result fetch, readiness probe.

No durable external mutation is expected. Results still receive provenance and may produce evidence.

### Ephemeral external effect

Examples: opening a browser tab, moving a pointer, starting a transient local process.

The effect may alter live environment state but is not intended as a durable business/system mutation.

### Durable local effect

Examples: file write, patch, local artifact creation, cron persistence.

Unrestricted `terminal.exec` and `code.execute_python` are conservatively classified `durable_local` in the release descriptors because arbitrary shell/Python code can persist local mutations. A future read-only command profile must use a distinct operation/descriptor with enforceable restrictions; CAPT must not infer read-only safety from command text.

Settlement must record before/after identity where the adapter can provide it.

### Durable remote effect

Examples: remote SSH write, remote command with side effects, external service mutation, A2A consequential action.

Requires explicit target binding and stricter recovery semantics.

### Resource-creation effect

Examples: Docker container creation, generated media artifact creation, persistent browser profile creation.

The created resource identity must be captured for cleanup/reconciliation.

Effect class participates in approval, capability scope, idempotency, recovery, evidence, and UI presentation.

## 7. ToolBroker lifecycle

Each admitted tool execution gets a stable execution id and follows a monotonic lifecycle:

`prepared -> admitted -> dispatching -> effect_observed? -> settling -> completed | failed | cancelled | indeterminate`

The ToolBroker persists enough state before external dispatch to recover without blind redispatch.

For every operation it records:

- execution id
- admitted command/idempotency identity
- tool + operation
- adapter version/identity
- capability/lease identity
- backend identity
- target identity
- effect class
- request digest
- dispatch boundary
- result/error digest
- created resource ids, if any
- settlement status
- cancellation state
- provenance/evidence references

An adapter may not mark an operation completed until ToolBroker settlement succeeds.

## 8. Crash and replay rules

Tool execution idempotency lives at the ToolBroker boundary, not only inside an individual adapter.

On RuntimeService or process restart:

- `prepared` and never dispatched -> safe to abandon or re-admit under normal policy
- `dispatching` with no proof of effect -> `indeterminate` unless adapter-specific reconciliation proves otherwise
- effect observed but not settled -> reconcile by stable effect/resource identity; do not redispatch blindly
- completed -> exact replay returns prior settled result
- cancelled -> cannot be silently resumed unless the operation contract explicitly allows governed resume

Every adapter that can create a durable or remote effect must implement either deterministic idempotency or reconciliation. Otherwise it is not eligible for mutating release use.

## 9. Terminal backend abstraction

Terminal/process execution uses a backend-neutral request envelope containing:

- argv or shell command according to operation contract
- working directory
- environment allowlist
- stdin policy
- timeout
- stdout/stderr limits
- filesystem scope
- network policy
- resource limits where supported
- cancellation token

The adapter returns a normalized process result with exit status, bounded output metadata, timestamps, backend identity, and effect/resource identities.

### 9.1 Local

Local is the default backend.

Requirements:

- canonical/symlink-aware cwd and filesystem scope checks before spawn
- bounded stdout/stderr capture
- timeout and process-tree cancellation
- explicit environment inheritance policy
- no implicit sudo
- process identity captured for reconciliation

### 9.2 SSH

SSH is a first-class release backend, not a shell-string wrapper around `ssh`.

Requirements:

- named host profiles
- strict host-key verification by default
- credentials referenced through approved secret storage/agent mechanisms
- no raw private key material persisted in CAPT state
- bounded remote cwd
- command quoting/argv semantics defined and tested
- timeout/cancellation behavior
- remote process/effect identity where obtainable
- target host fingerprint included in provenance
- configurable network/egress restrictions on the local side

Unknown or changed host keys fail closed.

### 9.3 Docker

Docker is a first-class release backend.

Requirements:

- named execution profiles
- explicit image identity
- explicit mounts with read/write mode
- resource limits
- network mode/policy
- working directory
- environment allowlist
- container identity captured before consequential execution
- cancellation/cleanup policy
- no Docker socket pass-through unless an explicitly approved specialized profile requires it

Image tag alone is not sufficient provenance when an immutable digest can be resolved.

## 10. Chrome DevTools browser adapter

Browser Automation uses Chrome/Chromium DevTools Protocol.

The CDP adapter owns:

- browser discovery/launch
- isolated CAPT browser profile by default
- debugging endpoint/session establishment
- target/tab lifecycle
- navigation
- DOM/query/evaluation read operations
- click/type/scroll interaction
- screenshot capture
- bounded download/upload handling when separately authorized
- console/network diagnostics useful for verification
- deterministic session cleanup/reconciliation where possible

Read operations and interaction operations have distinct capability/effect classes.

CDP debug endpoints must not be exposed broadly on the LAN. CAPT-launched Chrome should bind the debugging interface to loopback unless a separately governed remote-browser configuration explicitly states otherwise.

The adapter records browser process identity, CDP endpoint class, target id, frame/loader identity where relevant, and navigation/result digests sufficient to explain what was operated on.

## 11. Network isolation

Terminal, Docker, SSH, CDP, web search, scraping, A2A, and media-provider adapters may all touch networks. Network access is therefore policy, not an incidental implementation detail.

ToolBroker requests carry a network policy that can express:

- none
- loopback only
- explicit host allowlist
- profile-defined egress
- unrestricted, only when explicitly authorized

Docker profiles should prefer isolated networks and explicit egress. CDP debug transport is loopback by default. SSH targets are explicit profiles, not arbitrary model-supplied destinations without admission.

## 12. Non-terminal tool adapters

The release should reuse existing proven CAPT components and mature external implementations through typed adapters rather than duplicate functionality.

### Direct CAPT-native families

The following should prefer existing CAPT-native components where already authoritative or substantially implemented:

- Memory
- Context Engine
- Skills / Foundry
- Task Planning where CAPT task state already supplies the primitive
- Session Search when backed by CAPT-owned session state
- Clarifying Questions as an operator interaction primitive

### Provider-backed media/model families

Vision, video analysis, image generation, video generation, BFL FLUX 3 Video, and TTS are adapters to configured provider/model capabilities. Readiness requires both implementation availability and the required model/provider capability. A text-only model does not make a video-analysis tool available.

### External execution families

Web search/scraping, Computer Use, Task Delegation, Cron Jobs, and A2A receive explicit adapters and effect policies. Existing reusable implementations may be imported/adapted, but ToolBroker remains the authority boundary.

## 13. A2A

A2A is part of the selected initial tool set and must have an explicit protocol contract rather than being represented as generic task delegation.

The release adapter must distinguish:

- peer discovery/identity
- capability advertisement
- task/request submission
- message/result receipt
- cancellation
- consequential remote actions

Remote peer identity and endpoint identity are provenance inputs. A2A requests cannot inherit local filesystem/process authority unless separately and explicitly granted.

## 14. Cron Jobs

Cron/scheduled execution must be durable and restart-safe.

Persisted schedule state records stable job identity, schedule, requested operation, capability reference/policy, enabled state, last run, next run, and result/effect references.

A scheduled run must re-check authority at execution time. Creating a schedule is not a perpetual bypass around lease expiry, credential revocation, or changed policy.

## 15. Computer Use

Computer Use is distinct from CDP browser automation.

It is allowed for desktop/system UI workflows that cannot be expressed through a narrower adapter. It receives a higher effect/risk classification than DOM reads and must be scoped to an approved host/session.

Where a narrower deterministic interface exists, such as CDP for browser interaction or direct file/process APIs, CAPT should prefer the narrower interface.

## 16. Operator configuration

A CAPT release setup surface exposes terminal backend selection in this order:

1. Local — run directly on this machine
2. SSH — run on an approved remote machine
3. Docker — run in an isolated container with configured resources

The tool checklist exposes the selected initial tool set and readiness state.

Configuration stores references and policy, not raw secrets.

Native macOS UI, TUI, and CLI must read the same underlying operator/runtime projections so they cannot disagree about which backend or tool is active.

## 17. Native macOS integration

Swift remains a renderer/controller.

The native app adds operator views for:

- active terminal backend
- configured SSH/Docker profiles
- tool readiness and reason
- capability/approval requirements
- active tool executions
- cancellation
- indeterminate/reconciliation-required executions

Swift does not execute shell commands, Docker, SSH, or CDP directly.

## 18. Error model

Errors are typed at the ToolBroker boundary and retain adapter detail without leaking secrets.

Minimum categories include:

- authority violation
- capability expired/revoked
- unsupported operation
- prerequisite unavailable
- credential unavailable/revoked
- network policy denied
- target/scope violation
- backend unavailable
- timeout
- cancellation
- adapter failure
- effect indeterminate
- reconciliation failed
- artifact integrity failure

Timeout is not automatically equivalent to "no effect." For mutating/external operations, a timeout after dispatch may require `indeterminate` and reconciliation.

## 19. Security invariants

- No adapter widens capability scope.
- No raw credential material is persisted in EventStore, evidence, session cache, or tool results.
- Filesystem scope checks are canonical and symlink-aware before dispatch.
- Docker socket access is denied by default.
- SSH host-key verification is strict by default.
- CDP debug endpoints are loopback by default.
- Model-supplied hostnames, paths, container images, or commands remain untrusted input until admitted.
- Read-only evidence is never promoted to verification automatically.
- Tool success does not imply task/mission success or universal correctness.

## 20. Implementation decomposition

This architecture is intentionally larger than one implementation plan. Delivery is split into four independently verifiable slices that preserve one shared contract:

- **Slice A — ToolBroker substrate:** descriptors/readiness, capability/effect contracts, durable lifecycle/settlement/recovery, Local terminal, File Operations, Code Execution.
- **Slice B — Remote/container execution:** Docker and SSH profiles, network policy, durable-effect reconciliation, credential/host identity handling.
- **Slice C — Browser/web/desktop execution:** Chrome CDP, Web Search & Scraping integration, Computer Use boundary, browser/network recovery tests.
- **Slice D — intelligence/media/orchestration + product surface:** CAPT-native memory/context/skills/task/session/clarify adapters; provider-backed vision/video/image/BFL/TTS; Cron, Delegation, A2A; unified CLI/TUI/native readiness and installed-release reconciliation.

Each slice gets its own implementation plan and RED→GREEN acceptance gate. A later slice may depend on a verified prior slice, but no slice may redefine ToolBroker authority or effect semantics locally.

## 21. Implementation sequence

Implementation proceeds in dependency order:

1. Tool descriptor, readiness, capability/effect contracts
2. ToolBroker lifecycle, idempotency, settlement, recovery
3. Local terminal/process backend
4. File Operations and Code Execution over the local substrate
5. Docker backend
6. SSH backend
7. Chrome CDP browser adapter
8. Web search/scraping adapter integration
9. CAPT-native memory/context/skills/task/session/clarify adapters
10. Provider-backed vision/media/TTS adapters
11. Cron, delegation, A2A, and Computer Use
12. Unified CLI/TUI/native readiness and execution surfaces
13. Installed-artifact acceptance and release reconciliation

This ordering keeps CDP after the process substrate and prevents terminal-dependent tools from each inventing their own process lifecycle.

## 22. Required tests

### Contract/unit

- descriptor schema and registry uniqueness
- readiness truth table
- effect classification
- capability scope, expiry, usage ceiling, and revocation
- idempotency fingerprint conflicts
- secret redaction
- backend request normalization

### Local backend

- bounded cwd
- symlink escape denial
- stdout/stderr bounds
- timeout
- process-tree cancellation
- file read/write scope
- real code execution

### Docker

When Docker is available on the release machine:

- real container start/exec/result
- mount scope
- resource/profile propagation
- network policy
- cancellation/cleanup
- restart reconciliation
- credential/reachability loss negative case

If Docker is unavailable, the release result is `integrated_unavailable`, not verified PASS.

### SSH

When a qualified SSH target is available:

- strict host-key success
- changed/unknown host-key rejection
- bounded remote cwd
- real remote command/result
- timeout/cancel
- connection loss and reconciliation behavior

If no qualified target exists, the release result is `integrated_unverified`, not verified PASS.

### CDP

- launch/discover isolated Chrome
- connect only to approved debug endpoint
- navigate a deterministic test page
- DOM read
- click/type/scroll
- screenshot
- target/session cleanup
- kill RuntimeService/browser during an in-flight interaction and prove no blind redispatch
- debug-port exposure negative test

### Recovery and concurrency

- RuntimeService death during Docker/terminal/CDP execution
- simultaneous independent executions
- exact retry returns settled result without duplicate effect
- ambiguous effect becomes `indeterminate`
- reconciliation resolves by stable resource/effect identity where supported
- revoked credential/capability during execution fails visibly and cannot authorize a new effect

### Full release

- full Python suite
- contract drift checks
- full Swift suite
- `swift build --product CAPTNativeMac`
- installed wheel CLI/TUI smoke
- installed signed CAPT.app smoke
- installed runtime tool-readiness projection
- real selected-tool acceptance matrix with PASS / unavailable / unverified reasons

## 23. Release claim rule

"Integrated for full functionality" means the selected tool has a real adapter, governed admission path, readiness probe, typed failure semantics, and test coverage.

It does not mean every external provider/service is necessarily available on the test machine.

The final release report must distinguish:

- implemented + verified on real environment
- implemented + unavailable due to missing external prerequisite
- implemented + unverified due to unavailable qualified test target
- blocked by code defect
- out of release scope

No missing environmental prerequisite may be converted into a fabricated PASS.

## 24. Qwen/CAPT design review provenance

The approved architecture was reviewed through the governed CAPT runtime using local provider `mtplx` / model `qwen3.8-27b-mtplx`.

The successful review produced:

- mission `m-model-55a6db846e5df5352af94d9f`
- task `m-model-55a6db846e5df5352af94d9f-task-1`
- DriverRun `dr-model-55a6db846e5df5352af94d9f`
- `verificationId = null`

Qwen's output is design-review evidence, not independent verification. Its highest-value findings incorporated here were ToolBroker-owned effect settlement/idempotency, per-adapter scoped authority, Local-before-Docker/SSH-before-CDP dependency sequencing, network isolation, and separation of read-only versus durable/external effects.

## 25. Non-goals

This release slice does not:

- make Hermes authoritative
- add excluded setup backends
- auto-approve tool use
- collapse evidence into verification
- promise provider availability that was not tested
- expose unrestricted CDP or SSH endpoints
- grant persistent cron authority without execution-time revalidation
- make Computer Use the default mechanism for deterministic browser/file/process operations
- merge BioCAPT into the initial general tool release
