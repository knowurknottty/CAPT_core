# InversionSandbox R2: Persistent Governed Leases Design

## Problem

InversionSandbox R1 proves a one-shot local Docker boundary before untrusted code starts. It hardens the container, attests Docker's applied state, binds the observed identity into ToolExecution evidence, and provides fail-closed none/allowlist/unrestricted networking without weakening `terminal.docker`.

The remaining lifecycle gap is persistence. A multi-step task currently pays container creation/attestation/cleanup cost on every invocation and cannot intentionally preserve in-sandbox tmpfs state or a bounded working process across governed commands.

Persistence introduces a harder problem than simple container reuse: CAPT must distinguish resource existence from authorization, survive crashes without silently recreating external state, prevent stale or foreign container adoption, and preserve the existing ToolExecution/capability reservation semantics for every consequential command.

R2 adds persistent resource lifecycle only. It does not introduce a second authorization lease, a second lifecycle server, or an in-container agent authority.

## Decision

Add a durable CAPT `SandboxLeaseAggregate` representing one persistent InversionSandbox resource.

The name `SandboxLease` describes bounded resource lifetime only. It grants zero permission. CAPT's existing `CapabilityAggregate.lease` remains the sole capability lease and is revalidated immediately before every consequential sandbox operation.

All public fields use `sandboxLeaseId`; the unqualified field `leaseId` remains reserved for capability leases.

R1 one-shot execution remains the default and behaviorally unchanged. Persistent behavior is selected only by explicit lifecycle operations or an explicit `sandboxLeaseId` on `terminal.inversion_sandbox`.

## Authority Model

`SandboxLeaseAggregate` owns only resource facts: requested lifetime, immutable profile bindings, external Docker identities, lifecycle state, attestation evidence, and reconciliation facts.

It must never own or infer policy decisions, grants, capability operations, HumanApproval decisions, ToolExecution results, verification judgments, or claims.

Every consequential lifecycle action is still a normal governed ToolExecution:

- `sandbox.inversion.create` reserves and consumes one authorized capability use;
- `terminal.inversion_sandbox` execution against a `sandboxLeaseId` reserves and consumes its own authorized capability use;
- `sandbox.inversion.close` is separately admitted and audited;
- system cleanup may close expired/revoked resources only through a system-authored ToolExecution backed by a dedicated platform cleanup CapabilityGrant/lease scoped to `sandbox.inversion.close`; it never borrows, extends, or manufactures a user capability.

A live sandbox does not imply a live permission. Capability revocation, expiry, exhausted uses, operation mismatch, scope mismatch, or HumanApproval failure blocks the next consequential action even when the Docker container is healthy.

The immutable sandbox owner references are `operatorId`, `sessionId`, and creation `executionContextId`. R2 does not support cross-session lease transfer. A request from a different owner/session is rejected before Docker contact.

## Aggregate State Machine

The durable states are:

`reserved -> created -> running -> closing -> closed`

`reserved`, `created`, `running`, or `closing` may transition to `indeterminate` when CAPT cannot prove the external world state. `indeterminate` may transition only through explicit reconciliation to `running`, `closing`, or `closed`; it may never transition back to `reserved` or `created` by recreating resources.

State meanings are exact:

- `reserved`: EventStore has committed the sandbox identity and immutable requested contract, but CAPT has not yet proven a created external resource.
- `created`: all lease-owned Docker objects exist stopped and match the authorized contract; creation attestation is durable.
- `running`: the profile-owned persistent entrypoint is running and the sandbox is eligible for separately governed execs.
- `closing`: cleanup has begun or is being reconciled; no new exec is admitted.
- `closed`: CAPT has positive evidence that lease-owned workload/guardian/network resources are absent; host bind-mount contents are not deleted.
- `indeterminate`: CAPT has evidence that an external transition may have occurred but cannot prove the current resource state. New exec is denied until reconciliation.

A create failure proven to have occurred before any external effect may move `reserved` directly to `closed` with `closeReason=create_failed_no_effect`. This is not a successful sandbox creation.

## Immutable Lease Record

The aggregate binds at minimum:

- `sandboxLeaseId`, `profileId`, and canonical profile digest;
- immutable workload image ID/digest;
- `securityProfileDigest`, `networkPolicyDigest`, and `filesystemScopeDigest`;
- profile-owned persistent entrypoint digest;
- `operatorId`, `sessionId`, `executionContextId`, and creation ToolExecution ID;
- Docker endpoint/daemon identity observed at creation;
- requested `createdAt` and bounded `expiresAt`;
- workload container ID;
- guardian container ID when allowlist mode is used;
- internal network ID and name when allowlist mode is used;
- creation attestation digest and lifecycle side-effect identity;
- last reconciliation time/reason/evidence and closure receipt when applicable.

The record is append-only in meaning: an existing `sandboxLeaseId` is never rebound to a replacement container, guardian, network, image, profile, owner, or daemon identity.

Docker labels are discovery hints, not authority. CAPT-managed objects are labeled with the sandbox lease ID plus profile/security/network/filesystem digests. EventStore state remains authoritative; a labeled object without a matching aggregate is an orphan to report/quarantine, never a resource to adopt automatically.

## Public Control Surfaces

Add an independent `sandbox.inversion` lifecycle tool with operations:

- `create`: create and start a persistent sandbox under a named persistent-capable profile;
- `inspect`: return durable lease state plus current read-only Docker observation when available;
- `close`: stop/remove lease-owned runtime resources and durably record closure.

`terminal.inversion_sandbox` gains optional `sandboxLeaseId`.

Without `sandboxLeaseId`, the existing R1 one-shot path is used unchanged.

With `sandboxLeaseId`, the request targets the already-running lease-owned container. The request may supply only the command inputs already admitted by the terminal contract; it may not change image, user, mounts, network mode, guardian policy, resource limits, persistent entrypoint, or lease lifetime.

R2 does not add implicit routing between `terminal.docker`, one-shot InversionSandbox, and persistent InversionSandbox.

## Persistent-Capable Profiles

Persistence is opt-in per named InversionSandbox profile. A persistent-capable profile must declare an operator-owned `persistent_entrypoint_argv`; requests cannot override it.

The entrypoint exists only to keep the attested container alive between governed execs. It is not an agent, command broker, policy engine, shell session, or credential service.

Persistent readiness fails closed when the entrypoint is absent or invalid. R2 does not assume `sleep`, a shell, Python, or another binary exists in arbitrary images.

## Create Flow

1. ToolBroker admits `sandbox.inversion.create` through the ordinary descriptor/policy/HumanApproval/capability reservation path.
2. RuntimeService durably creates `SandboxLeaseAggregate` in `reserved` state before Docker mutation. The lease ID and immutable contract are now available for crash discovery labels.
3. The backend repeats R1 preflight: local Docker endpoint, immutable local images only, seccomp present, profile/network/filesystem validity, and unchanged daemon identity.
4. CAPT creates the workload and, for allowlist mode, the internal network and guardian in stopped state with lease labels. No workload code has started.
5. CAPT re-inspects and attests the exact created objects. The observed side-effect identity binds sandbox lease ID, object IDs, image IDs, all policy digests, daemon identity, and attestation digest.
6. RuntimeService atomically records ToolExecution `effect_observed` and transitions the SandboxLease from `reserved` to `created` with those exact identities. Only after that durable commit may CAPT start lease-owned processes.
7. CAPT starts the guardian when applicable, proves its exact policy digest readiness, starts the profile-owned persistent entrypoint, and verifies the workload is running with the same identity.
8. RuntimeService atomically records SandboxLease `created -> running`, capability consumption, and ToolExecution settlement using the existing multi-stream transaction/idempotency discipline. Any ambiguity preserves the observed identity and becomes `indeterminate`.

If CAPT crashes after Docker objects are created but before the aggregate reaches `created`, restart reconciliation searches only for objects labeled with the already-durable `sandboxLeaseId` and proves their full identity before changing state.

## Persistent Exec Flow

A persistent exec is a new ToolExecution, not a continuation of the create ToolExecution.

Before each exec CAPT must:

- load the live SandboxLease aggregate from EventStore;
- require `state == running` and `now <= expiresAt`;
- require exact operator/session ownership;
- revalidate the current capability lease immediately before dispatch;
- inspect the workload and prove container ID, image ID, daemon identity, non-root user, read-only rootfs, capability/security options, mounts, resource limits, labels, and exact network attachments still match the lease;
- when allowlist mode is active, prove the same guardian/internal-network identities remain present and the workload has no extra egress attachment.

Execution uses non-privileged Docker exec semantics with the profile's numeric UID:GID, explicit bounded working directory, literal argv, explicit bounded environment only, and no parent-environment inheritance. R2 never passes privileged exec flags.

Before launching the command, ToolExecution records an effect identity containing at minimum `sandboxLeaseId`, workload container ID, lease attestation digest, operation fingerprint, command digest, and current resource-observation digest. The external command may start only after that identity is durably observed.

A command success/failure settles only that ToolExecution; it does not alter the sandbox lifecycle when the resource remains proven healthy.

A host-side exec timeout does not prove that the in-container process terminated. R2 therefore must not claim timeout cleanup or automatically reuse the sandbox. If termination cannot be positively proven, the ToolExecution becomes `indeterminate` and the SandboxLease becomes `indeterminate`; further exec is blocked until reconciliation or close. R2 never kills/recreates the sandbox merely to hide exec ambiguity.

## Filesystem Semantics

The R1 read-only root filesystem remains mandatory. Persistence exists only in already-authorized writable surfaces:

- lease-lifetime tmpfs such as `/tmp` and `/run`;
- explicitly admitted writable bind mounts within the existing filesystem scope.

No mount may be added, removed, widened, or have RO/RW state changed while a sandbox lease is live.

Closing a sandbox removes container tmpfs with the container. It never deletes host bind-mount contents. Promotion of files from a sandbox into a durable CAPT artifact remains governed by the existing artifact promotion boundary; sandbox closure is not artifact adoption.

## Network Semantics

The network policy is immutable for the lifetime of a sandbox lease.

`none` remains disconnected. `unrestricted` remains available only for profiles that explicitly authorize it. `allowlist` retains the R1 internal-network + dual-homed guardian topology and immutable platform-deny precedence.

For persistent allowlist leases, workload, guardian, and internal network remain lease-owned resources until close. Each exec revalidates exact attachment topology. A request cannot patch allow rules, remove platform denies, connect another network, or replace the guardian. Different egress requires a new sandbox lease under a newly admitted profile/policy.

## Lifetime and Expiration

Persistent profiles define `default_ttl_seconds` and `max_ttl_seconds`. Requests may only narrow the profile maximum. Infinite TTL is forbidden.

R2 defaults to 30 minutes and caps operator-configurable profile maxima at 24 hours. The effective `expiresAt` must not exceed the creating capability lease's `validUntil`; the dedicated platform cleanup capability may outlive the creating user capability solely to remove the resource.

An expired sandbox denies new exec immediately. Expiration schedules or triggers closure through runtime reconciliation; it never extends itself and never creates a replacement resource.

Capability revocation likewise blocks new exec immediately. Revocation may trigger cleanup through the dedicated platform cleanup capability, but inability to clean does not weaken revocation: the resource can remain present while unusable and reported for reconciliation. If the platform cleanup capability is unavailable, CAPT reports cleanup pending and performs no Docker mutation.

R2 requires startup reconciliation of all non-closed leases. Every persistent exec/close performs target-specific live reinspection as part of admission. Create performs normal R1 runtime preflight and never scans Docker inventory for a reusable resource. R2 may expose an operator/system sweeper hook; a background scheduler is not required for admission correctness because every exec/close rechecks expiry and live state.

## Close Flow

`sandbox.inversion.close` is idempotent with respect to a `sandboxLeaseId`.

For a `created` or `running` lease, or an `indeterminate` lease whose owned object identities can be positively proven, CAPT transitions to `closing`, prevents new exec, then removes only objects whose immutable IDs and labels match the lease record. Allowlist cleanup orders workload before guardian before internal network unless an earlier absence is already positively proven.

A repeated close on `closed` returns the durable closure receipt and performs no destructive discovery by name.

If a close crashes or Docker returns ambiguous state, CAPT records `indeterminate` with the last proven identities. Reconciliation may complete cleanup only after exact identity checks. CAPT never deletes a container merely because its name resembles a CAPT sandbox.

`closed` requires positive evidence that all lease-owned runtime objects are absent. Cleanup ambiguity cannot be represented as `closed`.

## Restart and Reconciliation

Reconciliation begins from EventStore, not Docker inventory. For each non-closed sandbox lease CAPT compares the durable immutable record against exact Docker observations and lease labels.

A matching live object may restore an `indeterminate` lease to `running` only when the reconciliation reason permits reuse and the persistent entrypoint, security contract, image, daemon, mounts, labels, network topology, guardian policy, and expiry are all proven. A lease marked `indeterminate` because exec termination is unknown may not return to `running` without positive evidence that the ambiguous command terminated; absent that evidence it may proceed only to `closing` or `closed`. An expired matching object proceeds to `closing`, not `running`.

A missing expected object, unexpected extra network attachment, changed immutable ID, changed daemon identity, mismatched label/digest, changed guardian, or unprovable process state becomes `indeterminate`. CAPT does not recreate, rename, reconnect, or substitute resources automatically.

A Docker object carrying CAPT sandbox labels but lacking a matching EventStore lease is reported as an orphan. R2 may offer explicit cleanup only through a separately admitted cleanup ToolExecution backed by the dedicated platform cleanup capability; it never adopts the object into a new or existing lease.

Reconciliation itself records evidence and reason codes so a later verification/ClaimGuard decision can distinguish recovered truth from uninterrupted execution.

## Service and Ownership Boundaries

Add `capt_runtime.aggregates.sandbox_lease.SandboxLeaseAggregate` with explicit `OWNED_FIELDS` and immutable references consistent with the existing aggregate ownership map.

RuntimeService owns durable commands such as:

- `reserve_sandbox_lease`;
- `record_sandbox_created`;
- `record_sandbox_running`;
- `begin_sandbox_close`;
- `record_sandbox_closed`;
- `mark_sandbox_indeterminate`;
- `reconcile_sandbox_lease`.

Authoritative state transitions are authored only by the execution plane or system. Human/governance authority still controls capability issuance/revocation and HumanApproval; cognition cannot mutate sandbox lifecycle state.

Lifecycle commands use optimistic aggregate versions and existing EventStore idempotency. Where a CAPT transition touches SandboxLease, ToolExecution, and capability consumption at one logical settlement boundary, RuntimeService must use the existing multi-stream transaction mechanism rather than independent best-effort appends.

QueryService may expose read-only lease lookup/listing and reconciliation projections. Read APIs do not mutate or infer external state.

The backend remains responsible only for Docker observation/mutation and returns evidence. It never writes EventStore directly and never authorizes itself.

## Failure Semantics

- Unknown sandbox lease: reject before Docker mutation.
- Owner/session mismatch: reject before Docker contact.
- Lease not `running`: persistent exec rejects; `indeterminate` never degrades to best effort.
- Expired/revoked/exhausted capability: reject before command dispatch even if resource exists.
- Docker daemon/endpoint identity mismatch: mark or preserve `indeterminate`; never rebind.
- Container/image/profile/security/filesystem/network mismatch: deny exec; preserve evidence; require reconciliation/close.
- Guardian unavailable or policy mismatch: deny exec and mark the lease `indeterminate` when previously-running topology can no longer be proven.
- Exec host timeout with unproven process termination: ToolExecution and SandboxLease become `indeterminate`; no automatic retry.
- Create failure before any observed external effect: settle failed and close the reserved lease with no resource identity.
- Create/close failure after an observed effect: preserve side-effect identity; if exact cleanup is positively proven, settle failed/closed, otherwise mark `indeterminate` and require reconciliation.
- Cleanup of one resource must never broaden deletion to name/prefix matches.
- No failure path may fall back to one-shot execution, `terminal.docker`, unrestricted networking, another image, or a new container.

## Verification Gate

R2 is accepted only after unit, integration, crash-reconciliation, and real-Docker adversarial tests prove:

- `sandboxLeaseId` never grants or substitutes capability authority;
- create ordering is durable reservation -> stopped resources -> applied attestation -> ToolExecution effect observation -> guardian readiness -> workload start -> running lease;
- capability revocation/expiry blocks the next exec immediately;
- expired sandbox TTL blocks exec and is eligible only for cleanup;
- owner/session mismatch cannot reuse a lease;
- persistent exec reattests exact container/image/security/mount/network identities before dispatch;
- root/privileged exec and parent environment inheritance are impossible;
- allowlist policy/topology cannot widen during a live lease;
- a timeout with unknown in-container termination quarantines the lease instead of retrying;
- explicit close removes workload, guardian, and internal network and proves absence before `closed`;
- repeated close is idempotent and does not delete by fuzzy naming;
- crash during create reconciles labeled exact resources without recreation;
- crash during exec preserves ToolExecution uncertainty without corrupting resource identity;
- crash during close resumes only exact-identity cleanup;
- startup reconciliation never adopts Docker-only orphan resources;
- missing/mutated/replaced resources become `indeterminate` rather than reconstructed;
- R1 one-shot `terminal.inversion_sandbox` remains behaviorally unchanged;
- `terminal.docker` remains behaviorally unchanged.

The final repository gate also requires focused Ruff with zero new diagnostics, `git diff --check`, contract-generation drift checks, real Docker tests using already-local immutable images only, and the full existing test suite.

## Backward Compatibility

R2 is additive. Existing R1 profile fields, one-shot requests, result evidence, network behavior, and cleanup semantics remain unchanged unless a profile explicitly opts into persistence and the caller explicitly uses the lifecycle surface.

No automatic migration converts a one-shot profile or ToolRequest into a persistent lease.

## Non-Goals

R2 does not add:

- OpenSandbox SDK/API compatibility or a second lifecycle server;
- an injected `execd`, Jupyter kernel, PTY/session multiplexer, or command daemon;
- credential injection or credential brokering;
- snapshots, pause/resume, checkpoint/restore, or container cloning;
- dynamic mount mutation or writable root filesystems;
- live network-policy mutation;
- browser/VNC/desktop surfaces;
- Kubernetes, gVisor, Kata, Firecracker, or another runtime claim;
- cross-session sandbox transfer or shared multi-tenant leases;
- automatic replacement of missing/failed Docker objects.

Those capabilities require separate tranches because each changes a trust or lifecycle boundary. R2's sole purpose is to make the already-proven R1 boundary durable, reusable, expiring, and truthfully recoverable.

## R1 Relationship

R2 builds directly on merged InversionSandbox R1 commit `e35635b74f24cfda6c60ee4904e57567ee8aa30b` (PR #149). R1 applied-security attestation and guardian design remain normative wherever this document does not explicitly strengthen persistent-lifecycle behavior.
