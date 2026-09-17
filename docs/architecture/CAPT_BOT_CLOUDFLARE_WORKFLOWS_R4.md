# CAPT Bot Cloudflare Workflows Orchestration R4

**Status:** Approved for implementation
**Date:** 2026-09-09
**Parent:** `docs/architecture/CAPT_BOT_CLOUDFLARE_R3.md`

## Goal

Add Cloudflare Workflows as a free-tier-native durable orchestration substrate without moving scheduling, retry, cancellation, approval, verification, or terminal truth out of CAPT.

Workflows is a remote state machine, not arbitrary compute. `CloudflareWorkClass.ARBITRARY_COMPUTE` remains unroutable under `free_only`. Sandbox and Containers remain structurally unavailable on the current Free account and must stay dark.

## Governing invariants

1. RuntimeService + EventStore remain the authority plane.
2. Cloudflare readiness, instance status, or provider output is evidence, not CAPT terminal truth.
3. Unknown external effect state becomes reconciliation-required; uncertainty is never retry permission.
4. A Workflow name is not authority. Dispatch requires a human-adopted, digest-valid `CloudflareResourceBinding`.
5. Workflows cannot create, modify, deploy, or delete Workflow definitions through the runtime bridge.
6. The native bridge exposes only typed orchestration operations:
   - `workflow.instance.start`
   - `workflow.instance.status`
   - `workflow.instance.event`
   - `workflow.instance.step_evidence`
7. No generic Workflow command surface is introduced.
8. Provider credentials remain environment/keychain-backed references and never enter durable evidence.
9. Free-plan provider ceilings are outer limits, not spending permission.
10. Successful technical execution that violates the declared economic envelope is a failed CAPT execution.

## Free-tier envelope

Current verified provider limits for Workers Free:
- Workflows steps: 3,000/day.
- Workflow active CPU: 10 ms per step.
- Workflow persisted state: 1 GB-month.
- Workflows share the Workers request budget.

CAPT internal admission uses a 10% safety margin:
- `workflow_steps_per_day = 2_700`.

R4 does not attempt to meter persisted GB-month locally. Instead, payloads are intentionally small: mission/task IDs, operation IDs, digests, event names, and bounded metadata. Large state or artifacts belong in D1 or CAPT evidence stores.

The provider currently states that Free users are not billed for Workflows step/storage overage; nevertheless, CAPT fails closed at its internal step ceiling rather than relying on provider rejection.

## Routing semantics

Add:
- `CloudflareSurface.WORKFLOWS = "workflows"`
- `CloudflareWorkClass.DURABLE_ORCHESTRATION = "durable_orchestration"`
- `CloudflareFreeEstimate.workflow_steps`
- `CloudflareUsageSnapshot.workflow_steps`

`DURABLE_ORCHESTRATION` routes only to Workflows. `ARBITRARY_COMPUTE` remains `CLOUDFLARE_FREE_NATIVE_SURFACE_UNAVAILABLE`.

Reservations remain operation-scoped, durable, and transactionally serialized in `CloudflareUsageLedger`.

## Resource discovery and adoption

Extend `CloudflareResourceKind` with `WORKFLOW`.

Read-only inventory adds `GET /accounts/{account_id}/workflows`, with complete pagination validation. Each row must provide:
- provider Workflow UUID as `resource_id`;
- Workflow `name` as the human/provider name.

Every candidate remains `adopted=false`, `adoptionAuthority=human_required`.

Existing adoption semantics apply unchanged:
read-only inventory -> exact proposal -> one-use `HumanApprovalRequest` -> human approval -> atomic approval-consumption + binding creation.

Workflow bindings do not carry a network endpoint. Runtime dispatch resolves the exact Workflow alias through `CloudflareResourceBindingRegistry` immediately before any API secret lookup.

## Instance identity and exactly-once effect intent

CAPT precomputes the Workflow instance ID before dispatch so a lost response can reconcile the same external effect without inventing a second instance.

Canonical R4 instance identity:
`capt_<sha256(account_id || workflow_resource_id || operation_id)[0:64]>`

The `cf_` reserved prefix is never used.

Start request:
`POST /accounts/{account_id}/workflows/{workflow_name}/instances`
with the canonical `instance_id`.

A start response must return the same instance ID. Any disagreement is `CLOUDFLARE_WORKFLOW_INSTANCE_ID_MISMATCH`.

If dispatch outcome is ambiguous, the reservation remains locked and CAPT reconciles via:
`GET /accounts/{account_id}/workflows/{workflow_name}/instances/{instance_id}`.

R4 never retries start under a new instance ID.

## Typed operations

### workflow.instance.start

Inputs:
- operation ID
- adopted Workflow alias
- bounded params object
- declared maximum `workflow_steps`

Preconditions:
- adopted Workflow binding exists and passes digest validation
- step estimate is nonnegative and within CAPT daily envelope
- payload canonical JSON size <= 32 KiB
- secret reference resolves

Effects:
- reserve step budget
- POST instance using CAPT-owned instance ID
- validate returned instance identity/status
- commit reservation only on classified provider acknowledgement
- preserve reservation on ambiguous post-dispatch outcome
- release reservation only when dispatch is proven not started

### workflow.instance.status

Read-only GET for the known alias + instance ID.

Returns a closed provider-status vocabulary:
`queud`, `running`, `paused`, `errored`, `terminated`, `complete`, `waitingForPause`, `waiting`, `rollingBack`.

Provider status is evidence only. It does not mark CAPT mission/task completion.

### workflow.instance.event

Inputs:
- operation ID
- adopted Workflow alias
- known instance ID
- event type
- bounded event body

Event names use a closed identifier grammar and body canonical JSON <= 16 KiB.

The event operation ID is included in the body envelope so provider-side Workflow code can deduplicate if designed to do so. Cloudflare's API does not provide a CAPT-controlled idempotency key for event delivery; therefore an ambiguous event response becomes `CloudflareWorkflowIndeterminate` and must not be blindly resent.

### workflow.instance.step_evidence

Read-only GET of full step output for a known instance.

If the provider returns JSON, CAPT normalizes/digests it. If the provider returns `application/octet-stream`, R4 treats the output as binary evidence and stores it through the existing `CloudflareBinaryArtifactSpool`, with the same size/digest/chunk-read integrity rules used by Browser binary evidence.

Sensitive provider output marked `[REDACTED]` remains provider-redacted.

## Payload bounds

- start params canonical JSON: <= 32 KiB
- event body canonical JSON: <= 16 KiB
- event type: <= 100 chars, `[A-Za-z0-9_.:-]+`
- workflow alias: existing resource alias grammar
 - instance ID: CAPT-generated only
- binary step evidence: existing 32 MiB artifact ceiling

Oversized payloads fail pre-dispatch.

## Runtime ownership

`RuntimeComposition` owns:
- one `CloudflareUsageLedger`
- one `CloudflareBinaryArtifactSpool` when native Cloudflare is enabled
- one `CloudflareResourceBindingRegistry`
- one native bridge
- one `CloudflareWorkflowOrchestrator` surface

All surfaces share the same planner, registry, and bridge instance.

## Explicit exclusions

R4 does not:
- deploy or create Workflow definitions;
- delete or modify Workflows;
- pause/resume/terminate instances;
- schedule cron triggers;
- expose generic arbitrary compute;
- use Sandbox or Containers;
- use Workers Builds as generic compute;
- perform a live Workflow start/event during implementation;
- adopt a live Workflow automatically.

Read-only `wrangler workflows list` already established that the current account has zero deployed Workflows. A future first deployment/adoption is a separate human-authorized tranche.

## Verification gates

Required before commit:
1. focused Workflow tests;
2. all Cloudflare tests;
3. targeted Ruff E9/F/I on changed files;
4. contract drift if contracts change;
5. `git diff --check`;
6. `tests/capt_runtime`;
7. full repository suite through CAPT Node;
8. exact staged-file review;
9. clean worktree after commit.
