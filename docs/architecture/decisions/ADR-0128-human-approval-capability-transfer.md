---
status: Proposed (post-M0-B governed-write integration)
date: 2026-09-28
relates_to: ADR-0103, ADR-0107, ADR-0108, ADR-0110, ADR-0127
---

# ADR-0128 — HumanApproval-to-Capability authority transfer

## Context

CAPT already separates human decisions, governance policy, capability grants,
leases, tool execution, evidence, verification, and ClaimGuard disposition.
However, a `CapabilityGrant` carrying a `requires_approval` condition was not
causally bound to the exact `HumanApprovalRequest` that authorized it. A role
label such as `human_operator` proves neither which approval was consumed nor
that the grant preserves the approved capability, operation set, scope, and
external commitment.

This gap becomes security-critical when CAPT admits governed write work. A UI
approval must not be merely adjacent to authority; it must be the exact,
single-use parent of that authority.

## Decision

A grant that requires human approval MUST be created only through an atomic
RuntimeService transfer:

`HumanApprovalRequest -> human decision -> PolicyDecision -> consume approval + CapabilityGrant`

The transfer is `RuntimeService.issue_grant_from_human_approval(...)`.

The RuntimeService must prove, before commit:

- the approval is actually `approved`, unexpired, and has exactly one remaining
  authority-transfer use;
- `grant.approvalRequestId` names that exact request;
- approval, PolicyDecision, and grant agree on mission, task, capability,
  operation set, scope, subject, conditions, and capability-use budget;
- PolicyDecision and grant agree on the policy bundle digest;
- any `externalCommitments` are byte-for-byte equal across approval, policy
  decision, and grant;
- grant issuance does not precede the human decision;
- the grant does not outlive the approval expiry;
- the command fingerprint is recomputed from the semantic transfer
  `{requestId, grant, useId}` rather than trusted from a caller.

Approval consumption and `CapabilityGranted` are appended in one
`EventStore.commit_command(...)` transaction. The consumption is durable as
`HumanApprovalConsumedForCapability`. The approval cannot mint a second grant.

The legacy `issue_grant(...)` path rejects any grant that carries
`requires_approval` or an `approvalRequestId`; such grants must use the atomic
transfer.

`externalCommitments` are provenance bindings only. Recording a digest-bound
external agreement (for example a WorkContract) never creates CAPT authority.

## Why RuntimeService owns the transfer

`HumanApprovalAggregate` continues to own only approval lifecycle state and
`CapabilityAggregate` continues to own only capability lifecycle state.
Neither aggregate mutates the other. ADR-0103 requires cross-aggregate
invariants to live in an explicit application-service transaction; therefore
RuntimeService is the sole authority-transfer coordinator.

## Idempotency and replay

The operation fingerprint is:

`fingerprint("issue_grant_from_human_approval", {"requestId": ..., "grant": ..., "useId": ...})`

The same idempotency key with the same semantic fingerprint returns the recorded
result without another approval consumption or grant. The same key with changed
semantics is an `IdempotencyConflict`.

This extends ADR-0108; it does not weaken ToolBroker's independent
effect-level idempotency and reconciliation rules.

## Alternatives considered

- **Treat `requires_approval` as a descriptive grant condition only:** rejected.
  It cannot prove which human decision caused authority.
- **Put approval state inside `CapabilityAggregate`:** rejected. It violates
  aggregate ownership and duplicates HumanApproval lifecycle state.
- **Let the adapter assert that approval happened:** rejected. Adapter claims
  are not RuntimeService authority.
- **Consume approval before issuing a grant in two commands:** rejected. A crash
  between commands could burn approval without authority or leave ambiguous
  lineage.
- **Let an external WorkContract create authority:** rejected. Economic intent
  and CAPT execution authority remain separate control planes.

## Consequences

Positive:

- Human consent has exact, durable lineage into executable capability.
- Operation/scope/subject/policy drift fails closed.
- Approval reuse cannot mint multiple grants.
- External contracts can be audit-bound without becoming an authority source.
- The resulting grant remains compatible with the existing lease,
  reservation/finalization, ToolBroker, evidence, verification, and ClaimGuard
  pipelines.

Costs:

- Approval-bound execution must use the trusted
  `activate_approved_capability` command route (or the equivalent internal
  helper), which derives PolicyDecision, grant, and lease semantics from durable
  approval state rather than accepting them from the operator payload.
- Existing generic HumanApproval flows may omit `operations`; those remain
  valid, but they cannot be converted into executable capability until an exact
  operation set exists.
- The command surface now exposes `activate_approved_capability`; its payload
  is deliberately limited to `requestId` and `executionContextId`.

## Reversal conditions

1. CAPT adopts a more general monotone delegation graph that subsumes
   HumanApproval-to-grant transfer while preserving exact causal lineage.
2. HumanApproval and Capability authority are intentionally merged under a new
   aggregate ownership ADR with equivalent atomicity and replay guarantees.

Either change requires a new ADR and migration evidence.

## Evidence

- `capt_runtime/services.py` — exact approval/policy/grant equality checks and
  atomic `issue_grant_from_human_approval`.
- `capt_runtime/aggregates/human_approval.py` — bounded approval state,
  operations, use consumption, and external commitments.
- `capt_runtime/aggregates/capability.py` — grant state preserves
  `approvalRequestId` and external commitments.
- `contracts/schema/common.schema.json` —
  `HumanApprovalCapabilityConsumption` and `ExternalCommitment`.
- `contracts/schema/event.schema.json` —
  `HumanApprovalConsumedForCapability`.
- `tests/capt_runtime/test_human_approval_capability_binding.py` — drift,
  replay, one-use, and legacy-bypass negative tests.
- `tests/capt_runtime/test_verified_work_runtime_e2e.py` — real ToolBroker
  `file.write` + `terminal.exec`, authoritative evidence, verification-plane
  result, ClaimGuard acceptance, and replay without redispatch.
- `capt_runtime/approved_capability_authority.py` — derives policy, grant, and
  lease only from durable HumanApproval state and performs authoritative
  post-write readback.
- `tests/capt_runtime/test_approved_capability_command_surface.py` — proves the
  routable operator surface rejects semantic-authority injection and exact
  replay does not remint authority.
