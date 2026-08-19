# CAPT GPT Governed Verification + Local Tool Bridge Design

**Date:** 2026-08-19
**Authoritative implementation worktree:** `~/.capt-worktrees/inversion-labs-current-r2`
**Branch at design time:** `integration/inversion-labs-current-r2`
**Baseline head:** `cdae70f1c0c83bcd4920f16eaf3392db14c1fc59`

## 1. Purpose

Close the two remaining control-plane gaps between the CAPT Governed Operator Custom GPT and a full remote CAPT cockpit without creating a parallel runtime or an unrestricted shell path.

This tranche adds:

1. An authoritative RuntimeService verification command for tasks already in `awaiting_verification`.
2. A governed local tool execution bridge using CAPT's existing `ToolRequest`, `ToolResult`, capability, lease, reservation, evidence, verification, and ClaimGuard contracts.

This tranche does **not** add SSH, Docker, Chrome DevTools, Remote Desktop, or arbitrary network execution. Those are follow-on adapters using the same bridge.

## 2. Non-Negotiable Invariants

- RuntimeService/EventStore remain the sole authoritative state path.
- The GPT may request verification but may never supply or choose the verification outcome.
- The GPT may request a tool operation but may never invent a capability grant, lease, reservation, or authoritative ToolResult.
- Model/provider output remains evidence until independent verification completes.
- No generic shell-string endpoint is introduced.
- No raw EventStore mutation, RuntimeService token exposure, provider-key exposure, or approval bypass is introduced.
- Consequential operations fail closed when approval, capability, scope, identity, replay safety, or verification prerequisites are absent.
- Existing frozen CAPT contracts are reused wherever sufficient; no duplicate verification or tool-result schema is created.

## 3. Architectural Shape

The Custom GPT remains a reasoning/operator surface. It does not become a runtime authority.

```text
Custom GPT / MCP / CLI / TUI / Desktop
              |
              v
      canonical operator request
              |
              v
        RuntimeService command
              |
      +-------+--------+
      |                |
 verification       tool request
      |                |
      v                v
verification plane   policy -> grant -> lease -> reservation
      |                |
      v                v
 VerificationResult  bounded local adapter
      |                |
      +-------> Evidence / ClaimGuard <------+
                       |
                       v
                 terminal task state
```

Surface adapters expose RuntimeService-owned operations; they do not reimplement governance.

## 4. Verification Command

Introduce one authoritative command, conceptually `verify_pending_task`.

### 4.1 Input

The command accepts only identifiers and replay metadata needed to locate the pending work, for example:

- `taskId`
- optional `claimId` when a task has more than one pending claim
- caller idempotency/correlation metadata supplied through the normal authenticated command envelope

It does **not** accept `verified=true`, a ClaimGuard verdict, a fabricated `VerificationResult`, supporting evidence supplied by the GPT, or a terminal task state.

### 4.2 Preconditions

RuntimeService must reject unless:

- the task aggregate exists and is exactly `awaiting_verification`;
- the referenced claim belongs to that task and remains `proposed`/unresolved;
- at least one CAPT-authoritative evidence record is attached to the claim;
- no terminal verification/ClaimGuard decision already exists for the same claim;
- every evidence/artifact path resolves either inside the task's approved target scope or inside the exact CAPT-owned staging root bound to that task/driver run;
- replay/idempotency rules prove the request is new or safely replayable.

### 4.3 Durable verification baseline

The current live provider path computes a pre-dispatch repository tree digest and git-status baseline but does not place enough of that baseline into the claim evidence for a later verifier to reconstruct it solely from authoritative task/claim state. This tranche fixes that gap as part of the execution path.

Before provider/tool dispatch crosses its external boundary, the verification plane writes an immutable `verification-baseline.json` artifact in CAPT staging. The manifest contains the canonical target root, pre-dispatch tree digest, git-status digest/snapshot required by the verifier, task/driver-run IDs, and capture timestamp. CAPT hashes that manifest. After the claim exists, RuntimeService records both the baseline-manifest artifact hash and the produced-result artifact hash as CAPT-authoritative evidence on the claim.

The baseline manifest is not model output, and the caller cannot supply or alter its contents. Verification locates it through the claim's recorded evidence IDs, verifies the manifest's own digest before use, then recomputes the current repository/artifact state from disk. No verification decision may depend only on an idempotency receipt, conversation state, or a guessed staging path.

### 4.4 Verification execution

The verification plane reconstructs its inputs from the task/claim aggregates and their CAPT-authoritative evidence. For the current read-only model-operator path it independently verifies the baseline manifest, rechecks the result artifact digest, recomputes repository mutation state against the baseline, and emits a contract-valid `VerificationResult` using existing strategies such as `artifact_hashing` and `invariant_check`.

A failed check produces a negative/inconclusive verification result; it must never be converted into success by the surface adapter.

### 4.5 ClaimGuard and terminalization

After RuntimeService records the VerificationResult:

- ClaimGuard evaluates the bounded claim using the recorded verification.
- `accept` promotes the verified claim to `accepted` and transitions the task to `succeeded`.
- `qualify`, `reject`, or `escalate` preserve their exact authority semantics and must not be flattened to success.
- contradicted verification transitions the task to `failed` unless an existing CAPT contract requires escalation instead.
- the command returns the authoritative claim, verification, ClaimGuard, and task disposition IDs/state.

The command is idempotent: replay with the same idempotency key returns the same authoritative receipt and never performs verification twice.

## 5. Governed Local Tool Bridge

Add one canonical RuntimeService command family for local tools. Surface-specific names may differ, but all routes must resolve into the same CAPT Core tool operation.

The command family has two mutation stages:

- `prepare_tool_request`: canonicalize and freeze the requested operation, arguments, mission/task identity, root/scope, risk class, and registry binding; compute a `toolRequestDigest` and immutable `preparedExecutionDigest`; create the human-approval aggregate when the request is consequential; perform no external side effect.
- `execute_prepared_tool_request`: accept only the prepared request identity/digests plus the approval request ID when required; recompute/revalidate the binding, then enter the policy/grant/lease/reservation/execution path.

A sibling `PreparedApprovedToolExecution` value in CAPT's prepared-execution layer holds all non-secret deterministic tool inputs. Because the frozen v1 `HumanApprovalConsumption` contract requires the legacy field name `promptAssemblyDigest`, tool approvals place `toolRequestDigest` in that digest slot and persist `scope.approvalBinding.kind = "tool_request"` plus the same `toolRequestDigest`. RuntimeService checks both before consumption. This is a compatibility use of the frozen digest slot, not a claim that a tool request is a model prompt.

Preparation deterministically assigns `missionId`, `taskId`, `driverRunId`, and `toolRequestId` and binds them into the prepared digest. As with the existing model path, preparation does not need to materialize mission/task aggregates. `execute_prepared_tool_request` materializes the authoritative mission/task only after all preparation and approval checks pass, then drives the task through `ready -> assigned -> running -> awaiting_verification -> terminal`.

### 5.1 Initial allowlisted operations

The first tranche supports only:

- `filesystem.read`
- `filesystem.write`
- `filesystem.append`
- `filesystem.patch`
- `filesystem.delete`
- `git.status`
- `git.diff`
- `test.pytest`
- `process.argv`

`process.argv` accepts an argv array and bounded execution metadata. It never accepts a shell command string and never invokes `shell=True`, `zsh -c`, `bash -c`, `eval`, or equivalent command interpretation.

### 5.2 Tool registry and executable binding

The caller never supplies an executable path. `process.argv` requires a server-side `toolId` registered by CAPT. Each registry entry binds:

- canonical executable path;
- allowed argument grammar/subcommands;
- working-directory policy;
- timeout and output ceilings;
- network classification;
- filesystem scope expectations;
- consequential/read-only classification.

The initial `process.argv` registry contains exactly one plumbing/acceptance entry: `system.echo` bound to `/bin/echo`, with at most 32 UTF-8 arguments, 4096 input characters total, a 5-second timeout, a 64 KiB output ceiling, no network permission, and no filesystem write capability. It is still treated as consequential so the approval/consumption boundary is exercised.

Real development execution in this tranche uses the dedicated `git.*` and `test.pytest` adapters. Interpreters, shells, package-install commands, and arbitrary executable paths remain denied. Additional registered argv tools require a later reviewed registry change, not caller choice.

### 5.3 Risk and approval policy

- Pure reads (`filesystem.read`, `git.status`, `git.diff`) execute without a new human approval ceremony when RuntimeService policy authorizes that exact root and operation; they still use the governed task/capability/evidence/verification lifecycle.
- Writes (`write`, `append`, `patch`, `delete`) are consequential and require a one-use human approval bound to operation, normalized arguments, target root/path, and request digest.
- `test.pytest` is treated as consequential because test code can execute arbitrary project code; its exact root and argument vector are approval-bound.
- `process.argv` is consequential in this tranche, including `system.echo`; no process registry entry is downgraded to approval-free execution here.
- Approval consumption happens immediately before the external execution boundary, never at preparation time.

The Custom GPT may prepare a consequential tool request and present its approval, but cannot approve it on the user's behalf.

### 5.4 Capability lifecycle

For every tool execution RuntimeService owns this sequence:

`ToolRequest -> policy decision -> capability grant -> lease -> reservation -> adapter execution -> ToolResult -> consumption record`

The adapter receives only the effective scope/arguments after RuntimeService validation. It never receives authority to broaden them.

### 5.5 Filesystem semantics

All filesystem operations resolve through an authoritative root binding before touching disk.

- Canonicalize root and target with real-path resolution.
- Reject traversal, symlink escape, or any path outside the approved root.
- Mutations require optimistic preconditions where applicable (`expected_sha256` for update/delete; exact `old_string` match for patch).
- Writes are atomic when the existing filesystem layer can provide atomic replacement semantics.
- Mutation receipts include operation, canonical path, resulting digest, and verification status.
- A successful system call alone is not sufficient proof of a successful write; post-write digest/content verification is required.


### 5.6 ToolResult durability

The frozen event vocabulary has `TaskResultSubmitted` but no standalone `ToolResultRecorded` event. This tranche therefore persists every canonical `ToolResult` as deterministic JSON in CAPT staging, hashes the file, and submits the task result with `resultRef = "artifact://sha256/<hex>"`. RuntimeService then records an `artifact_hash` EvidenceRecord for that exact ToolResult artifact and attaches it to the task's claim.

A verifier resolves the `resultRef` only through matching CAPT-authoritative evidence; it never trusts a caller-supplied path. Transport adapters may display the ToolResult body, but the EventStore task reference plus evidence digest are the durable authority.

## 6. Evidence and Verification for Tool Operations

Tool execution produces a contract-valid `ToolResult`. CAPT then derives evidence appropriate to the operation:

- filesystem mutation: resulting artifact hash/content digest;
- git/test/process operation: command-exit evidence with exit code and output digest;
- state-sensitive operations: state assertion evidence where an authoritative aggregate exists.

The evidence is recorded by the verification plane, not by the GPT or external adapter.

Consequential tool tasks end at `awaiting_verification` until the verification plane evaluates the recorded evidence. Verification and ClaimGuard then determine the terminal task state using the same authority boundaries as model tasks.

Every operation in this local-tool bridge materializes a governed mission/task at execution time, proposes a bounded claim, records evidence, and passes through verification/ClaimGuard before terminal success. Read-only operations differ only in human-approval policy; they do not bypass task authority. Existing RuntimeService query operations such as identity/status/capabilities remain lightweight projections outside this tool-task bridge.

## 7. Idempotency, Failure, and Recovery

Every mutating or external-boundary tool request has a stable operation fingerprint and idempotency key.

- Before the external boundary, replay may safely return or resume only where CAPT can prove no side effect occurred.
- Once a reservation exists and the external boundary may have been crossed, an unknown result is recorded as `indeterminate`; CAPT does not silently retry.
- A completed ToolResult is immutable evidence of that invocation and is never re-executed merely because a client retried HTTP/MCP transport.
- Verification command replay returns the existing verification/ClaimGuard receipt.
- Runtime restart preserves open reservation/reconciliation state through EventStore/checkpoint authority.

Failures are classified, not collapsed:

- validation/scope failure -> denied/rejected before execution;
- approval missing/expired/mismatched -> fail closed before execution;
- adapter failure before boundary -> failed, safe-to-retry only when proven;
- unknown post-boundary outcome -> indeterminate/reconciliation required;
- verification contradicted -> task failed or escalated per CAPT state machine;
- ClaimGuard qualification/rejection/escalation remains distinct from verification status.

## 8. Surface Integration

The canonical operations are added first to RuntimeService capabilities. Surface adapters then project them:

- CAPT MCP/operator contract: add canonical verification-mutation and governed-tool operations routed through RuntimeClient. On the CAPT-governed profile, existing direct workspace filesystem/process mutations are either remapped to these RuntimeService operations or disabled; they cannot remain a parallel bypass.
- CAPT Actions gateway: expose bounded task verification and tool prepare/status/execute endpoints backed by RuntimeService commands.
- Custom GPT instructions: explicitly require exact human approval for consequential tool requests and prohibit supplying verification outcomes.
- CLI/TUI/Desktop may consume the same operations later without new governance semantics.

No surface is allowed to implement its own verification logic, capability issuance, approval consumption, or terminal state promotion.

## 9. Follow-On Adapter Contract

SSH, Docker, Chrome DevTools, and Remote Desktop are separate adapters in the next tranche. Each must register a distinct `toolId`/capability scope and declare whether the boundary is local process, remote host, container, browser, or desktop UI.

The follow-on adapter must still use the same lifecycle:

`request -> policy -> approval if consequential -> grant/lease -> reservation -> external boundary -> ToolResult -> evidence -> verification -> ClaimGuard`

No adapter may expose a raw transport escape hatch such as arbitrary SSH command strings, unrestricted Docker exec, arbitrary DevTools protocol messages, or unconstrained desktop input without a CAPT capability describing the exact operation/scope.

## 10. Test Strategy

Implementation is test-driven. Each behavior is introduced by a failing test before production code.

Required verification-command tests:

- rejects task not in `awaiting_verification`;
- rejects missing/mismatched claim;
- rejects claim without authoritative evidence;
- cannot accept a caller-supplied outcome/VerificationResult;
- successful verification records exactly one `ClaimVerified` event;
- ClaimGuard runs after verification and terminalizes according to its verdict;
- contradicted verification cannot become success;
- replay is idempotent and emits no duplicate verification/decision events.

Required tool-bridge tests:

- path traversal and symlink escape are rejected;
- unregistered `toolId` and executable injection are rejected;
- shell strings/interpreters are not accepted as `process.argv` escape hatches;
- consequential operations require exact one-use approval;
- approval mismatch/expiry/consumption blocks execution;
- reservation is recorded before external boundary;
- post-boundary exception becomes indeterminate without retry;
- successful write is independently re-hashed before verification;
- transport retry returns prior ToolResult without repeating the side effect.

## 11. Acceptance Gates

This tranche is accepted only when all of the following are proven against the live authoritative RuntimeService:

1. The previously proven Custom-GPT model smoke can be taken from `awaiting_verification` through the new verification command without supplying a verdict from the GPT.
2. RuntimeService emits authoritative verification and ClaimGuard state, and the task reaches the correct terminal state.
3. A read-only local tool request can run through the RuntimeService capability path and return a ToolResult, while the CAPT-governed MCP/GPT profile exposes no parallel direct filesystem/process mutation or execution bypass.
4. A harmless consequential local mutation can be prepared through the Custom GPT, stopped at exact human approval, explicitly approved, executed once, independently verified, and terminalized.
5. Repeating the same client request cannot repeat the side effect.
6. Runtime restart or gateway restart does not lose authoritative task/tool/verification state.
7. EventStore chain verification remains `ok` after all smoke tests.
8. Existing model approval/dispatch behavior and existing CAPT UI/runtime tests remain green.

The live smoke must preserve the distinction among observation, ToolResult, evidence, VerificationResult, ClaimGuard disposition, task state, and mission state in its report.

## 12. Source-of-Truth and Deployment Rule

Implementation is authored in the repository/worktree that actually supplies the running RuntimeService, not in a stale sibling checkout. Before every live restart, the process working directory/module path is rechecked.

RuntimeService is restarted only after tests pass and only through the existing managed service mechanism. The Actions gateway may be restarted independently, but a gateway restart is never evidence that RuntimeService code changed.

Any gateway or MCP change must consume the RuntimeService capability inventory dynamically enough to fail closed when the new command is unavailable; it must not fabricate support from its own schema.

## 13. Explicitly Out of Scope for This Tranche

- unrestricted shell access;
- arbitrary executable paths or interpreter execution;
- SSH/remote-host execution;
- Docker/container execution;
- Chrome DevTools/browser mutation;
- Remote Desktop input/control;
- arbitrary network egress;
- automatic approval on behalf of the human;
- caller-supplied verification or ClaimGuard outcomes;
- replacing EventStore, RuntimeService, existing approval semantics, or frozen contract authority.
