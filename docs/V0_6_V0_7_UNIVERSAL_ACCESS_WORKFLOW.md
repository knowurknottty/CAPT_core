# CAPT Universal Access — Canonical MCP + CAPT Lite Integration Workflow

**Status:** canonical execution workflow
**Scope:** close CAPT v0.6 release blockers, modernize CAPT Workspace MCP into the universal CAPT MCP Gateway, and build CAPT Lite as a protocol-compatible constrained deployment profile.

## Governing objective

Every person, application, agent, device, and operating system should be able to use CAPT either:

1. directly through CAPT Core where the host can run it; or
2. through CAPT MCP Gateway and/or CAPT Lite where full Core deployment is impractical.

The system must preserve one authority model. CAPT Lite and MCP MUST NOT become independent competing runtimes or sources of truth.

## 5-pass architectural conclusions

### Pass 1 — Current-state truth

- `knowurknottty/CAPT_core` is the canonical CAPT Core repository.
- `knowurknottty/capt-workspace-mcp` is the canonical active MCP foundation.
- CAPT Workspace MCP v0.1 is currently a governed stdio worksurface with 14 filesystem/git/development tools, fail-closed roots, mandatory read-back verification, receipts, hash-chained audit, argv-only execution, and adversarial tests.
- It does not currently bind RuntimeService or expose CAPT memory/mission/approval/evidence/model semantics.
- No canonical CAPT Lite implementation exists. CAPT Lite is therefore a new implementation grounded in current Core contracts rather than a migration of old code.
- Historical bioCAPT/FrankenCAPT MCP implementations are reference material only and MUST NOT become runtime authority.

### Pass 2 — Primary architecture correction

The missing abstraction is not another runtime. It is a **transport-independent CAPT Operator Contract**.

All operator-facing surfaces should consume one logical contract:

```text
CLI
TUI
Native Desktop
MCP Gateway
CAPT Lite
Future Web/Mobile Clients
        |
        v
CAPT Operator Contract
        |
        v
Authenticated Runtime Client / RuntimeService
        |
        v
EventStore + Governance + Memory + Evidence + Drivers
```

The Operator Contract defines stable user/operator concepts and hides internal runtime implementation details.

### Pass 3 — MCP role

CAPT Workspace MCP evolves into **CAPT MCP Gateway**, preserving the existing governed workspace tools and adding CAPT operator tools.

The existing 14 workspace tools remain a valuable execution worksurface. They are not replaced.

MCP Gateway responsibilities:

- translate MCP requests into Operator Contract operations;
- preserve operator identity, approval, capability/scope, idempotency, evidence, and receipts;
- expose runtime state without granting direct ledger authority;
- preserve existing workspace root/allowlist/read-back/audit controls;
- support local stdio first;
- add streamable HTTP as the remote/browser/mobile transport when security/auth is ready;
- never write EventStore directly;
- never promote model output directly;
- never bypass RuntimeService governance.

### Pass 4 — CAPT Lite role

CAPT Lite is a **protocol-compatible constrained deployment profile**, not a mini-Core fork.

All Lite tiers use the same Operator Contract vocabulary, capability IDs, receipts, provenance semantics, and version negotiation as Core.

#### Lite L0 — Connected client

No independent authority.

Capabilities:

- Core discovery/health;
- provider/model status and selection;
- mission submit/status/cancel;
- approvals list/decide;
- evidence/verification/claim inspection;
- memory query/store when connected;
- checkpoint/resume request;
- portable connection/profile configuration.

Target environments:

- browsers through a gateway;
- iOS/iPadOS;
- Android;
- thin desktop apps;
- IDE extensions;
- chat applications;
- MCP clients;
- constrained devices with networking.

#### Lite L1 — Portable continuity

Adds local non-authoritative continuity:

- bounded local session cache;
- portable ContextPack envelope;
- durable local preferences;
- pending request/receipt cache;
- checkpoint/resume token handling;
- encrypted/OS-backed local secrets where available;
- explicit synchronization with Core.

Core remains authoritative.

#### Lite L2 — Disconnected operation

Future/offline profile:

- explicitly bounded offline queue;
- local evidence cache;
- limited memory lifecycle;
- reconciliation protocol;
- conflict/provenance handling;
- later synchronization to Core.

L2 MUST NOT silently merge conflicting authoritative state.

### Pass 5 — Release/program sequencing

Universal access work depends on closing the current CAPT Core v0.6 operator/release blockers first. The MCP/Lite implementation then binds to a stable Operator Contract instead of chasing moving APIs.

---

# Program invariants

1. **RuntimeService remains authority.**
2. **EventStore remains authoritative runtime event truth.**
3. **CAPT Lite is not CAPT Core 2.0.**
4. **MCP is not a governance bypass.**
5. **Existing workspace MCP security controls are preserved or strengthened.**
6. **No UI, Lite client, or MCP transport writes the ledger directly.**
7. **Provider/model registration is not equivalent to execution support.**
8. **Capabilities are versioned and discoverable.**
9. **Every mutation carries identity, idempotency, scope, receipt, and evidence semantics where applicable.**
10. **Disconnected Lite state is explicitly non-authoritative until reconciled.**
11. **Local vs remote/cloud behavior must be visible to users and clients.**
12. **Protocol failures fail closed rather than guessing or silently degrading governance.**

---

# Phase A — Close CAPT Core v0.6 P0 blockers

Before freezing the Operator Contract, resolve the evidence-backed current blockers:

## A1. Branch/repository hygiene

- merge/normalize v0.6 planning lineage;
- remove committed Swift `.build/` artifacts from UI PR/history as appropriate;
- add correct nested `.build/` ignore rules;
- retarget UI implementation to canonical `main` lineage;
- run normal main-target CI.

## A2. Governed real-model execution

Implement a real provider execution path behind DriverHost/RuntimeService governance.

Initial target: OpenAI-compatible adapter family, with LM Studio as the first live proof.

Required proof:

- real model selected;
- mission/task created;
- capability/approval honored;
- model actually executes;
- artifacts/evidence persisted;
- VerificationResult produced;
- ClaimGuard disposition produced;
- no direct UI/provider bypass.

## A3. True cross-model continuity

Execute the real Model A -> checkpoint -> process exit -> Model B -> resume proof with distinct actual model identities.

Capture:

- mission/task IDs;
- provider/model IDs;
- DriverRun IDs;
- ContextPack/checkpoint IDs;
- artifact/evidence hashes;
- EventStore head before/after;
- no-repeat proof;
- verification and ClaimGuard result.

## A4. Public CLI alignment

Either implement the promised normal-human commands:

```text
capt doctor
capt start
capt status
capt stop
```

or deliberately replace public documentation/release gates with the actual canonical command surface.

No documented command may be fictional.

## A5. Native desktop product

Ship a real launchable native desktop application, not merely a Swift package/library.

macOS first is acceptable for v0.6 if other platform status is explicit.

## A6. Automated human-interface acceptance

Run the engineered macOS `osascript`/Accessibility acceptance suite in a real Aqua session.

Headless projection tests do not count as GUI proof.

---

# Phase B — Freeze CAPT Operator Contract v1

Create a transport-independent contract package/spec that can be consumed by Core clients, MCP, Lite, UI, and future SDKs.

Recommended domains:

## Runtime

- status
- health
- capabilities
- checkpoint
- resume
- shutdown/cancel semantics

## Mission

- create
- get/status
- list
- cancel

## Approval

- list pending
- inspect request
- decide approve/deny

## Memory

- store
- get
- search
- lifecycle/query status
- context policy/status

## Evidence

- list/get evidence
- verification status
- claim explanation/ClaimGuard disposition
- provenance/event references

## Provider/model

- list providers
- provider health/capability status
- list models
- select model at default/mission/temporary scope
- distinguish LOCAL/REMOTE/HYBRID/UNKNOWN

## Operator presentation

- CaveCAPT verbosity preference
- diagnostics level

Each request/response must specify:

- schema/protocol version;
- request ID;
- operator/client identity;
- session/mission scope where relevant;
- idempotency key for mutations;
- capability/scope request where relevant;
- authoritative vs projection classification;
- typed error code;
- receipt/evidence references.

Add compatibility tests proving CLI/TUI/Desktop all map to this contract without duplicating authority logic.

---

# Phase C — CAPT MCP Gateway v1

Repository: `knowurknottty/capt-workspace-mcp`.

Do not discard the existing v0.1 worksurface architecture.

## C1. Preserve existing tools

Keep the existing governed filesystem/git/development tool family:

- workspace_status
- workspace_bind
- directory_list
- file_read
- file_write
- file_append
- file_patch
- file_delete
- verify_write
- capture_evidence
- run_command
- run_pytest
- git_status
- git_diff

Retain:

- fail-closed roots;
- executable allowlists/deny rules;
- `shell=False` argv execution;
- mandatory read-back verification;
- safe-path/TOCTOU defenses;
- mutation receipts;
- tamper-evident audit chain;
- concurrency serialization where required.

## C2. Add Core client adapter

Add a module such as:

```text
capt_workspace_mcp/captcore/
  client.py
  contract.py
  mapping.py
  errors.py
```

It should bind the CAPT Operator Contract to the canonical RuntimeClient/RuntimeService transport.

No copy of RuntimeService belongs in this repo.

## C3. Add CAPT operator MCP tools

Initial stable tool family:

### Runtime

- `capt_status`
- `capt_capabilities`
- `capt_checkpoint`
- `capt_resume`

### Mission

- `capt_mission_create`
- `capt_mission_get`
- `capt_mission_list`
- `capt_mission_cancel`

### Approval

- `capt_approvals_list`
- `capt_approval_decide`

### Memory

- `capt_memory_store`
- `capt_memory_get`
- `capt_memory_search`
- `capt_context_status`

### Evidence

- `capt_evidence_get`
- `capt_verification_get`
- `capt_claim_explain`

### Providers/models

- `capt_providers_list`
- `capt_provider_test`
- `capt_models_list`
- `capt_model_select`

Do not expose unstable internal classes merely because they exist.

## C4. Composite governed engineering flow

The key MCP value is composition of CAPT governance with the existing workspace worksurface.

Example:

```text
capt_mission_create
 -> approval/capability lease
 -> file_read/run_command/file_write
 -> mandatory workspace receipt/readback
 -> CAPT artifact/evidence registration
 -> VerificationResult
 -> ClaimGuard
```

This should become the canonical MCP engineering demonstration.

## C5. MCP transports

### v1 required

- stdio

### next required

- MCP Streamable HTTP with explicit authentication and TLS deployment guidance

Do not add remote transport until operator identity/authz semantics are implemented and tested.

Legacy SSE may be supported only if a real client requires it; do not make it architectural.

## C6. MCP tests

Preserve the existing adversarial suite and add:

- MCP <-> real RuntimeService integration;
- identity propagation;
- approval denial proves no execution;
- approval allows only approved scope;
- idempotency replay;
- runtime unavailable;
- stale token/session;
- Core version mismatch;
- evidence/receipt correlation;
- workspace receipt -> CAPT evidence linkage;
- model/provider query;
- governed real-model mission;
- restart/resume through MCP;
- no direct ledger mutation;
- no secret leakage;
- concurrency ordering.

---

# Phase D — CAPT Lite v1 repository/package

Create CAPT Lite only after Operator Contract v1 is stable enough to bind.

Preferred repository/package naming should be decided once, e.g.:

- repository: `knowurknottty/capt-lite`
- package: `capt_lite`

## D1. L0 connected-client implementation

Implement the Operator Contract client with transport adapters.

Recommended transports:

- direct local RuntimeClient where Python/local IPC exists;
- MCP stdio adapter for applications embedding Lite with a local Gateway;
- authenticated HTTP transport when MCP/Core remote gateway is available.

Core capabilities exposed through Lite must be dynamically discovered rather than hard-coded as guaranteed.

## D2. Portable implementation strategy

Keep the protocol model language-neutral.

Provide an initial reference implementation in Python if useful, but define schemas in a form that permits:

- Swift/iOS/macOS clients;
- Kotlin/Android clients;
- TypeScript/browser/extension clients;
- Rust/Go embedded/server clients.

Lite is successful only if non-Python clients can implement the same contract without embedding Python.

## D3. L1 continuity profile

Add after L0 proves interoperability:

- local cache database;
- bounded portable ContextPack representation;
- encrypted credential/reference storage appropriate to host;
- receipt/provenance cache;
- last-authoritative-state marker;
- explicit connected/disconnected status;
- replay-safe pending operations where permitted.

All cached state must carry authority metadata such as:

- AUTHORITATIVE_CORE
- CACHED_FROM_CORE
- LOCAL_PENDING
- LOCAL_NON_AUTHORITATIVE
- CONFLICTED

## D4. L2 offline profile

Defer until a real use case requires it.

Before implementation, specify:

- conflict resolution policy;
- provenance merge rules;
- offline mutation whitelist;
- evidence semantics;
- synchronization and replay rules;
- privacy/security boundary.

---

# Phase E — Universal device/application coverage

Maintain a generated/tested coverage matrix.

Target categories:

## Full Core capable

- macOS
- Linux workstation/server
- Windows where runtime tests pass
- containers/VMs

## Lite/native client

- iOS
- iPadOS
- Android
- browser/PWA
- Swift native clients
- Kotlin native clients
- TypeScript clients

## MCP clients

- Claude Desktop and other stdio MCP clients
- IDEs/editors supporting MCP
- agent hosts
- local automation tools

## Remote/gateway

- browser clients
- mobile clients
- thin devices
- SBC/NAS/home server setups

For each environment record:

- Core direct: YES/NO/PARTIAL
- MCP: YES/NO/PARTIAL
- Lite: YES/NO/PARTIAL
- transport
- authentication
- tested version
- test artifact
- known limitations.

The public goal is not that every device runs Core. The goal is that every reasonable device/application has a supported path to CAPT capabilities.

---

# Phase F — Security architecture for universal access

Threat-model new remote/client boundaries before public remote transport.

Required controls:

- operator/client identity;
- authentication;
- per-capability authorization;
- approval binding;
- scope binding;
- idempotency;
- replay protection where applicable;
- TLS for remote transport;
- secret redaction;
- local-vs-cloud disclosure;
- audit correlation IDs;
- rate/size limits;
- bounded request/input sizes;
- untrusted-output sanitization;
- protocol-version rejection/fallback rules;
- explicit disconnect/offline state.

Workspace MCP's existing controls are additive and should remain enforced for workspace operations.

---

# Phase G — Test engineering program

Create automated suites at each boundary.

## G1. Contract conformance

Generate/run identical Operator Contract scenarios against:

- direct RuntimeClient;
- CLI adapter;
- TUI operator layer;
- native desktop client contract;
- MCP adapter;
- CAPT Lite reference client.

Expected semantic outcome must be identical where capability exists.

## G2. MCP conformance

Run real MCP clients over stdio.

Test:

- initialize/capability negotiation;
- tools/list;
- tool schemas;
- errors/isError semantics;
- concurrent calls;
- cancellation;
- Core unavailable/reconnect;
- governed mutation lifecycle;
- workspace+Core evidence chain.

## G3. Lite conformance

Test L0 from multiple languages or generated fixtures where practical.

At least one non-Python client proof should exist before claiming universal Lite interoperability.

## G4. Cross-platform CI

Minimum target matrix after portability work:

- macOS arm64
- Linux x86_64
- Windows x86_64

Add mobile/browser tests as corresponding clients exist.

## G5. Failure engineering

Test:

- dropped connections;
- Core restart;
- stale auth;
- schema mismatch;
- duplicate requests;
- out-of-order responses;
- oversized payloads;
- unavailable provider;
- approval timeout;
- client crash/reconnect;
- Lite stale-cache behavior.

---

# Phase H — Documentation and distribution

## CAPT Core

Document:

- direct/local use;
- MCP Gateway use;
- CAPT Lite use;
- how authority differs across surfaces.

## MCP Gateway

README should explain:

- existing workspace capabilities;
- CAPT runtime capabilities;
- configuration;
- permissions/security;
- supported clients/transports;
- install commands;
- integration examples;
- evidence/receipt model.

## CAPT Lite

Documentation should be device-oriented:

- "Use CAPT from iPhone/iPad"
- "Use CAPT from Android"
- "Use CAPT from a browser"
- "Use CAPT from an MCP application"
- "Use CAPT from a constrained Linux device"
- SDK/contract documentation for implementers.

## Capability matrix

Generate a public matrix from conformance evidence rather than prose claims.

---

# Versioning

Recommended independent but compatible versions:

- CAPT Core runtime version
- CAPT Operator Contract version
- CAPT MCP Gateway version
- CAPT Lite version

Clients negotiate contract/capabilities rather than assuming package versions imply feature parity.

A client must fail clearly on an incompatible contract rather than silently invoking an incorrect fallback.

---

# v0.6 / v0.7 boundary

## v0.6 required

- current Core P0 release blockers closed;
- Operator Contract v1 extracted/frozen;
- MCP Gateway stdio integration with core runtime/memory/mission/approval/evidence/model query tools;
- existing workspace tools preserved;
- real MCP <-> Core governed mission proof;
- CAPT Lite L0 connected-client reference implementation;
- at least one Core + MCP + Lite conformance scenario;
- accurate public capability/device matrix.

## v0.7 targeted

- MCP Streamable HTTP secure remote transport;
- CAPT Lite L1 portable continuity/cache;
- native iOS/iPadOS and Android client implementations or SDK proofs;
- browser/TypeScript Lite client;
- broader Windows/Linux/native GUI polish;
- multi-provider remote/local interoperability testing.

## Later

- Lite L2 disconnected mutation/synchronization;
- multi-device conflict resolution;
- cross-device provenance reconciliation;
- distributed/enterprise identity and policy architecture;
- edge/appliance hardening.

---

# Required end-to-end acceptance demonstrations

## Demo 1 — MCP governed engineering

```text
MCP Client
 -> capt_mission_create
 -> approval
 -> workspace file/tool operation
 -> workspace read-back receipt
 -> CAPT evidence registration
 -> verification
 -> ClaimGuard
 -> evidence inspection through MCP
```

## Demo 2 — Lite universal client

```text
CAPT Lite client
 -> connect/negotiate Operator Contract
 -> runtime health
 -> provider/model selection
 -> create governed mission
 -> approval decision
 -> inspect evidence
 -> checkpoint/resume
```

## Demo 3 — Surface equivalence

Execute one semantically identical mission through:

- CLI
- TUI/Desktop operator layer
- MCP
- CAPT Lite

Prove all mutations appear in the same RuntimeService/EventStore authority chain and produce equivalent typed receipts/evidence.

## Demo 4 — Failure isolation

Disconnect MCP/Lite client during work, restart the client, reconnect, and prove:

- Core state is intact;
- completed work is not repeated;
- stale client state is not promoted as authoritative;
- user/client receives explicit recovery status.

---

# Exit criteria

The universal-access program is complete for a release tier only when:

1. each claimed surface binds the same Operator Contract;
2. no surface bypasses RuntimeService authority;
3. workspace MCP security controls remain intact;
4. every MCP mutation receives CAPT governance/evidence treatment;
5. Lite identifies authoritative vs cached/pending state explicitly;
6. supported devices/apps appear in a tested capability matrix;
7. an unsupported platform has an explicit supported alternative path;
8. documentation commands/configurations are mechanically validated;
9. real installed-package/client proofs exist;
10. claims are no stronger than the evidence.

## Ultimate product criterion

> A user or application should not need to care whether CAPT is running locally, reached through MCP, or projected through CAPT Lite. The available capability set may differ, but memory, governance, evidence, identity, receipts, and authority semantics remain recognizably CAPT everywhere.
