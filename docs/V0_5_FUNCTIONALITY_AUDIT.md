# CAPT Core v0.5 Functionality Audit

**Audit target:** `main` after PR #35  
**Canonical merge:** `a621814925948af9fe245889736043930d9c9b51`  
**Purpose:** inventory the real v0.5 capability surface and separate code presence from tested, reachable, installed, and externally proven behavior.

## Classification vocabulary

- **PUBLIC_API** — supported in-process surface through `capt_solo.api` or explicitly documented public modules.
- **CLI** — directly exposed by the installed `capt` command.
- **HARNESS_OPERATOR** — exposed through authenticated `capt harness` runtime commands.
- **INTERNAL_RUNTIME** — wired and active inside the runtime but not a direct public command.
- **DESKTOP_OPERATOR** — available through the desktop/runtime client path.
- **INSTALLED_PROVEN** — exercised through an installed wheel outside the source tree.
- **LOCAL_REAL_PROCESS_PROVEN** — exercised against a real external process locally.
- **HOSTED_CI_PROVEN** — exercised by hosted CI.
- **TEST_PROVEN** — covered by automated unit/integration/acceptance tests.
- **PRESENT_NOT_PRODUCTIZED** — implemented but not polished as a primary user workflow.
- **NOT_PROVEN** — presence or intent is insufficient for a release claim.

## Executive result

CAPT Core v0.5 is not a thin memory library. It contains four substantial functional planes:

1. a local cognitive-state layer (`capt_solo`) with memory, lifecycle, sessions, procedures, prospective memory, retrieval feedback, CTP, KHSB, and Foundry/proof systems;
2. an authoritative governed runtime (`capt_runtime`) with an EventStore ledger, mission/task/approval/capability state, idempotent command processing, verification, ClaimGuard, checkpoints, replay, and authenticated IPC;
3. a memory-governance plane with ContextPack construction, repeated rotation, configurable 32K-relative trigger policy, stale-pack rejection, budgeting, and restart continuity;
4. external-driver and operator surfaces including OpenHarness, a bounded real-Hermes inspection path, desktop M1 operator actions, cancellation, human approval, runtime lifecycle control, and state replay.

The principal v0.5 limitation is **productization, not core architecture**: many capabilities are public APIs, internal services, or governed command primitives rather than a single polished end-user agent workflow. General unrestricted model-driven repository engineering is not proven.

## Feature census

| Area | Feature | Reachability | Evidence | v0.5 verdict |
|---|---|---|---|---|
| Memory | SQLite durable memory store | PUBLIC_API / CLI | installed import + tests | SHIPPED |
| Memory | store/get/update/delete/list/search | PUBLIC_API / CLI subset | generated API + tests | SHIPPED |
| Memory | namespaces, tags, provenance, confidence, metadata | PUBLIC_API | generated API + tests | SHIPPED |
| Memory | tiers and lifecycle states | PUBLIC_API | generated API + tests | SHIPPED |
| Memory | backup/restore/import/export/integrity | PUBLIC_API | generated API + tests | SHIPPED |
| Memory graph | aliases | PUBLIC_API | generated API | SHIPPED |
| Memory graph | typed relations / neighbors / graph path | PUBLIC_API | generated API | SHIPPED |
| Memory quality | duplicate detection and merge | PUBLIC_API | generated API | SHIPPED |
| Memory quality | conflict detection, recording and resolution | PUBLIC_API / CLI inspection | generated API + CLI | SHIPPED |
| Memory lifecycle | promote/pin/archive/restore/explain | CLI | CLI implementation | SHIPPED |
| Sessions | begin/list/status/checkpoint/resume/consolidate/close | CLI / public lifecycle classes | CLI + tests | SHIPPED |
| Procedures | procedure storage, listing, inspection, run history | PUBLIC_API classes / CLI | API exports + CLI | SHIPPED |
| Prospective memory | pending/ready intent tracking and resolution | PUBLIC_API classes / CLI | API exports + CLI | SHIPPED |
| Retrieval | retrieval feedback, adaptation state, reset | PUBLIC_API classes / CLI | API exports + CLI | SHIPPED |
| Search | pluggable SearchAdapter / SemanticAdapter seam | PUBLIC_API | generated API | SHIPPED SEAM; adapter-dependent behavior varies |
| CTP | begin/validate/commit/abort/note | PUBLIC_API | generated API + tests | SHIPPED |
| CTP | correlation IDs and idempotency keys | PUBLIC_API | generated API + tests | SHIPPED |
| CTP | receipts, audit trail, unfinished transaction recovery | PUBLIC_API / INTERNAL_RUNTIME usage | generated API + tests | SHIPPED |
| KHSB | publish/subscribe | PUBLIC_API / INTERNAL_RUNTIME | generated API + tests | SHIPPED |
| KHSB | request/reply, timeout, acknowledgement, pending messages | PUBLIC_API / INTERNAL_RUNTIME | generated API + tests | SHIPPED |
| KHSB | durable/cross-process messaging | — | explicitly absent | NOT IN v0.5 |
| Proof | evidence storage and requirement aggregation | `capt_solo.foundry` | generated API + tests | SHIPPED |
| Capability Registry | candidate/validated/proven/verified/degraded/deprecated/revoked/experimental lifecycle | `capt_solo.foundry` / CLI | API + CLI + tests | SHIPPED |
| ClaimGuard | support checking and governed claim downgrade | Foundry + runtime | tests + installed lifecycle | SHIPPED |
| Skill Foundry | candidate generation, validation, review, approval, publication | Foundry / CLI | API + CLI + tests | SHIPPED |
| Skill validation | staged validation harness | Foundry | tests | SHIPPED |
| Skill curation | duplicate/overlap/unsafe/incomplete/obsolete review | Foundry / CLI | API + CLI | SHIPPED |
| Knowledge Bubbles | build/import/quarantine/validate/approve/install/export | Foundry / CLI subset | API + tests | SHIPPED |
| Workflow Proof | independent proof for composed workflows | Foundry | API + tests | SHIPPED |
| Composition | workflow composition primitives | Foundry | generated API | SHIPPED / developer-facing |
| Governance | named-actor governed Foundry transitions | Foundry / CTP | tests | SHIPPED |
| Anti-token extraction | optional component integration | Foundry component | tests where dependency present | OPTIONAL / HOSTED CI DEGRADED |
| EventStore | authoritative ordered runtime event ledger | INTERNAL_RUNTIME | UNIT_TEST_PROVEN / INSTALLED_PROVEN | SHIPPED |
| EventStore | aggregate versions, global sequence, outbox transaction coupling | INTERNAL_RUNTIME | tests | SHIPPED |
| EventStore | hash-chain integrity / chain digest | INTERNAL_RUNTIME / health | tests | SHIPPED |
| Runtime commands | idempotency and duplicate suppression | HARNESS_OPERATOR / INTERNAL_RUNTIME | INSTALLED_PROVEN | SHIPPED |
| Missions | mission creation and persisted MissionSpec | HARNESS_OPERATOR / DESKTOP_OPERATOR / runtime CLI primitive | tests + desktop acceptance | SHIPPED |
| Tasks | authoritative task creation/transitions | INTERNAL_RUNTIME / desktop projection | tests | SHIPPED |
| TaskResolver | authoritative bounded task resolution | INTERNAL_RUNTIME | UNIT_TEST_PROVEN | SHIPPED |
| Human approval | approval request before consequential execution | DESKTOP_OPERATOR / runtime service | M1 acceptance | SHIPPED |
| Human approval | approve/deny decision | DESKTOP_OPERATOR / HARNESS command primitive | M1 acceptance | SHIPPED |
| Cancellation | cancel task | DESKTOP_OPERATOR / HARNESS command primitive | tests | SHIPPED |
| Cancellation | cancel driver run | DESKTOP_OPERATOR / HARNESS command primitive | M1 acceptance | SHIPPED |
| Policy | policy evaluation | INTERNAL_RUNTIME | tests | SHIPPED |
| Capability control | grants and leases | INTERNAL_RUNTIME | tests | SHIPPED |
| Capability control | scope/max-use/time-bound enforcement | INTERNAL_RUNTIME / DriverHost | tests | SHIPPED within tested boundaries |
| DriverHost | bounded external dispatch | INTERNAL_RUNTIME | tests | SHIPPED |
| Driver registry | driver registration/selection boundary | INTERNAL_RUNTIME | tests/package | SHIPPED |
| OpenHarness | canonical fixed-function OpenHarness driver | HARNESS_OPERATOR / INTERNAL_RUNTIME | UNIT_TEST_PROVEN | SHIPPED, bounded |
| Hermes | packaged Hermes driver | HARNESS_OPERATOR | installed + LOCAL_REAL_PROCESS_PROVEN | SHIPPED, bounded read-only inspection |
| Hermes | unrestricted repo engineering | — | explicitly unproven | NOT IN v0.5 |
| Verification | artifact hash evidence | INTERNAL_RUNTIME | INSTALLED_PROVEN | SHIPPED |
| Verification | frozen VerificationResult contract | INTERNAL_RUNTIME | INSTALLED_PROVEN | SHIPPED |
| Verification | persisted ClaimVerified / EvidenceRecorded events | INTERNAL_RUNTIME | INSTALLED_PROVEN | SHIPPED |
| Verification | ClaimGuard decision persistence | INTERNAL_RUNTIME | INSTALLED_PROVEN | SHIPPED |
| Checkpoint | checkpoint creation with integrity metadata | HARNESS_OPERATOR / INTERNAL_RUNTIME | INSTALLED_PROVEN | SHIPPED |
| Recovery | stop/restart/reopen same ledger | HARNESS_OPERATOR | INSTALLED_PROVEN | SHIPPED |
| Recovery | resume without repeating completed execution | HARNESS_OPERATOR | INSTALLED_PROVEN | SHIPPED |
| Runtime IPC | authenticated Unix-domain socket | HARNESS_OPERATOR / DESKTOP_OPERATOR | INSTALLED_PROVEN | SHIPPED |
| Runtime IPC | per-start token file with restricted mode | INTERNAL_RUNTIME | tests | SHIPPED |
| Operator identity | connection-bound operator/session identity | DESKTOP_OPERATOR | tests + M1 acceptance | SHIPPED, single-user model |
| Memory Governor | active runtime MemoryTriggerEngine/Governor | INTERNAL_RUNTIME | tests | SHIPPED |
| Context accounting | estimated token accounting | INTERNAL_RUNTIME | tests | SHIPPED; estimate, not exact tokenizer |
| Context policy | 32,768-token-relative trigger interval | INTERNAL_RUNTIME | tests | SHIPPED |
| Context policy | configurable retrieval/compression/checkpoint/consolidation/hard-stop steps | HARNESS command primitive / desktop command service | tests | SHIPPED |
| ContextPack | construction | INTERNAL_RUNTIME | tests | SHIPPED |
| ContextPack | first/second/repeated rotation | INTERNAL_RUNTIME | tests | SHIPPED |
| ContextPack | stale-pack rejection | INTERNAL_RUNTIME | adversarial tests | SHIPPED |
| ContextPack | context budget enforcement | INTERNAL_RUNTIME | tests | SHIPPED |
| ContextPack | restart continuity | INTERNAL_RUNTIME | tests | SHIPPED |
| Context isolation | external driver receives authorized ContextPack rather than raw memory | INTERNAL_RUNTIME | tests | SHIPPED within tested path |
| Harness lifecycle | start | CLI | installed lifecycle | SHIPPED |
| Harness lifecycle | health | CLI | installed lifecycle | SHIPPED |
| Harness lifecycle | capabilities | CLI | installed lifecycle | SHIPPED |
| Harness lifecycle | generic governed command relay | CLI | tests/installed path | SHIPPED, advanced-user surface |
| Harness lifecycle | checkpoint | CLI | installed lifecycle | SHIPPED |
| Harness lifecycle | resume | CLI | installed lifecycle | SHIPPED |
| Harness lifecycle | stop | CLI | installed lifecycle | SHIPPED |
| Desktop M1 | authenticated local operator client | DESKTOP_OPERATOR | acceptance | SHIPPED / not yet polished product UX |
| Desktop M1 | mission creation + authoritative projections | DESKTOP_OPERATOR | acceptance | SHIPPED |
| Desktop M1 | approval queue / approve / deny | DESKTOP_OPERATOR | acceptance | SHIPPED |
| Desktop M1 | cancel active run | DESKTOP_OPERATOR | acceptance | SHIPPED |
| Desktop M1 | reconnect and reconstruct state | DESKTOP_OPERATOR | acceptance | SHIPPED |
| Desktop M1 | duplicate-free replay | DESKTOP_OPERATOR | acceptance | SHIPPED |
| Desktop M1 | polished signed/notarized desktop distribution | — | not claimed | NOT IN v0.5 |
| Contracts | canonical JSON schemas | developer surface | hosted CI | SHIPPED |
| Contracts | generated Python/TypeScript bindings | developer surface | hosted CI | SHIPPED |
| Contracts | drift detection and reproducible generation | CI | HOSTED_CI_PROVEN | SHIPPED |
| Contracts | cross-language fixture parity | CI | HOSTED_CI_PROVEN | SHIPPED |
| Packaging | wheel build and non-editable install | distribution | HOSTED_CI / release proof | SHIPPED |
| Packaging | deterministic wheel with fixed SOURCE_DATE_EPOCH | distribution | two-build evidence | SHIPPED |
| Packaging | generated public API reference + CI drift check | documentation/tooling | HOSTED_CI_PROVEN | SHIPPED |
| Security | gitleaks secret scan | CI | HOSTED_CI_PROVEN | SHIPPED gate |
| Security | dependency audit | CI | HOSTED_CI_PROVEN | SHIPPED gate |
| Security | optional anti-token dependency provenance on hosted CI | CI | dependency unavailable | DEGRADED_OPTIONAL_DEPENDENCY |
| Security | encryption at rest | — | absent | NOT IN v0.5 |
| Security | multi-user authorization | — | absent | NOT IN v0.5 |
| Security | cryptographically signed audit chain | — | absent | NOT IN v0.5 |

## What a user can actually do today

### Directly through `capt`

The installed CLI exposes memory review/lifecycle operations, sessions, procedures, prospective memory, retrieval feedback/adaptation, Foundry operations, one canonical runtime mission primitive, and the standalone harness lifecycle/command relay.

The harness command service accepts governed operations for mission creation, approval decisions, task/run cancellation, memory trigger policy updates, fixed OpenHarness inspection, approved Hermes inspection, checkpoint, shutdown, and resume.

### Directly through Python

`capt_solo.api` exposes the local memory/lifecycle/CTP/KHSB surface. `capt_solo.foundry` exposes proof, capabilities, ClaimGuard, Skill Foundry, Knowledge Bubbles, governance, composition, curation, workflow proof, and the optional anti-token component.

### Through the desktop/runtime client

The M1 acceptance path proves authenticated connection, mission creation, approval request, denial preventing execution, approval of a bounded capability, driver-run cancellation, reconnect, persisted projections, replay, and duplicate suppression. This is real runtime behavior but is not yet a polished signed/notarized consumer desktop product.

## Evidence strength by plane

| Plane | Highest evidence class |
|---|---|
| CAPT Solo public memory/API | installed import + automated tests |
| CTP/KHSB | generated public API + automated tests |
| Foundry/proof | automated tests + CLI/API availability |
| EventStore/runtime state | INSTALLED_PROVEN |
| Runtime lifecycle/recovery/idempotency | INSTALLED_PROVEN |
| ContextPack/Memory Governor | TEST_PROVEN + installed policy queries |
| Desktop governed operator path | acceptance-test proven |
| OpenHarness | TEST_PROVEN fixed-function path |
| Hermes | LOCAL_REAL_PROCESS_PROVEN bounded read-only path |
| Hosted build/contracts/security | HOSTED_CI_PROVEN |
| General autonomous engineering | NOT_PROVEN |

## Public-launch gaps versus architecture gaps

There is no evidence of a foundational runtime architecture blocker in v0.5. The high-value remaining gaps are mainly product and trust-surface gaps:

| Gap | Type | Launch significance |
|---|---|---|
| General model-driven engineering beyond bounded inspection | capability/product | HIGH if marketed as a full coding-agent harness; LOW if v0.5 is marketed as governed infrastructure |
| Polished TUI/desktop workflow | usability | HIGH for general users; LOW for technical preview |
| Rewritten v0.5 Hermes compatibility skill | integration | MEDIUM; does not block core release |
| Model-adapter configuration guides | DX | MEDIUM |
| Cross-model continuity demonstration | proof/marketing | MEDIUM-HIGH; very strong public demo opportunity |
| ContextPack observability | DX/operations | MEDIUM |
| Scoped coverage policy | engineering governance | MEDIUM |
| Private vulnerability-reporting channel | trust/ops | HIGH before broad security-oriented publicity |
| Optional anti-token hosted provenance | security integration | MEDIUM; explicitly degraded, optional |
| Encryption at rest / signed receipts / multi-user auth | higher-trust security | NOT a v0.5 blocker if boundaries remain explicit |
| Open issues #6-#12 describing legacy Hermes/bioCAPT paths | repository optics/scope | HIGH until triaged as current, external-integration, or historical |

## Open-issue scope warning

At audit time, issues #6 through #12 remain open in `CAPT_core` and describe security/provenance/duplicate-tree behavior under old `~/.hermes/biocapt...` or bioCAPT request-construction paths. Those issue bodies do not by themselves demonstrate that the merged standalone v0.5 harness has the same defects.

Before public launch they should be individually reproduced against current v0.5 or reclassified/moved/closed with provenance. Leaving them untriaged makes the public repository appear to carry active security defects in the canonical runtime.

## Release decision

### Suitable announcement now

v0.5 is suitable for a public technical announcement if described as a **release-proven local-first cognitive/runtime infrastructure release for developers and evaluation**. Strong defensible claims include durable model-independent state, proof/ClaimGuard, authoritative event history, governed execution boundaries, idempotent restart/recovery, memory/context governance, and a real external Hermes process demonstrated through a bounded installed-wheel operator path.

### Not suitable claim yet

Do not market v0.5 as a turnkey autonomous coding agent, an unrestricted Hermes governance layer, a multi-user secure service, an encrypted cognitive store, or a cryptographically trusted audit platform.

### Recommended v0.6 theme

v0.6 should primarily convert the v0.5 architecture into a cohesive operator product:

1. general governed model work under explicit capability/lease/verification contracts;
2. polished CLI/TUI/desktop operator workflow;
3. model adapter setup and discovery;
4. rewritten and separately proven Hermes compatibility package;
5. cross-model continuity proof/demo;
6. better ContextPack/memory observability;
7. security/issue triage and scoped coverage policy;
8. optional trust upgrades such as encrypted exports or signed attestations only if they can be fully proven.

## Bottom line

**v0.5 is technically publishable now as infrastructure.** The argument for waiting for v0.6 is not that v0.5 lacks substance; it is that v0.6 can make the existing substance obvious, easy to operate, and compelling to users who do not want to work directly with APIs and governed command envelopes.
