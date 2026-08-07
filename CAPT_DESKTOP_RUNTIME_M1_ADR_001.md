# ADR-DT-M1-001: Human Approval & Cancellation Contracts

## Status
Accepted (M1 implementation).

## Context
The Treasure Chest Desktop Runtime workflow requires M1 governed operator actions:
create a bounded mission, submit it, review a bounded approval request, approve/deny,
prove denial prevents execution, prove approval permits only authorized action, and cancel
an active task/DriverRun.

Phase 1 recovery found that `RuntimeService` had:
- NO `HumanApprovalRequest`/`HumanApprovalDecision` aggregate,
- NO `request_human_approval` / `submit_human_approval_decision` methods,
- cancellation supported at the `TaskAggregate`/`DriverRunAggregate` level (terminal state
  `cancelled`) but NO `cancel_task`/`cancel_driver_run` service methods.

The workflow's contract-discipline rule requires proving a gap before extending frozen
contracts and documenting an ADR/version decision. The gap is proven (above).

## Decision
1. Add `HumanApprovalRequest` and `HumanApprovalDecision` contract types to
   `common.schema.json` (additive; contract version remains `1.0.0` — no breaking change).
2. Add event types `HumanApprovalRequested`, `HumanApprovalDecided` to `event.schema.json`
   and the `human_approval-` stream prefix to the `StreamId` pattern.
3. Add `HumanApprovalAggregate` (capt_runtime/aggregates/human_approval.py) owning ONLY
   approval state; it never mutates missions, tasks, runs, capabilities, evidence, or
   verification.
4. Add `RuntimeService.request_human_approval`, `submit_human_approval_decision`,
   `cancel_task`, `cancel_driver_run`.
5. Add authority entries: `request_human_approval` (execution/governance/system),
   `submit_human_approval_decision` (human), `cancel_task`/`cancel_driver_run`
   (execution/human/system).
6. Keep contract version `1.0.0` (additive extension). A future breaking change would
   warrant a major version bump per ADR-0101; this is not one.

## Consequences
- Desktop approval/cancellation now flow through real CAPT authority and the event ledger.
- Denial prevents execution; approval permits only the requested scope; cancellation is
  authoritative and reconciled.
- The `EventEnvelope`/`StreamId` contracts were extended (not broken); cross-language
  bindings regenerated and parity tests pass.
- No desktop-local mission or approval state is authoritative; CAPT remains the single
  authority.
