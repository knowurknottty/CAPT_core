# CAPT Desktop Runtime M1 — Command Map

All commands are issued by the desktop over authenticated IPC and executed by
`RuntimeCommandService` (thin) → `RuntimeService` (authoritative) → CAPT
aggregates → `EventStore`. The desktop does NOT plan or orchestrate; it
submits an `OperatorMissionIntent` and the runtime owns all planning.

## Envelope (every command)

| Field | Source | Notes |
|---|---|---|
| commandId | desktop (hash of op+payload) | unique per command |
| operatorId | bound session (`operator-<localuser>`) | NOT taken from payload |
| sessionId | bound per-connection random | NOT taken from payload |
| schemaVersion | fixed `1.0.0` | mismatch → malformed |
| correlationId | desktop | trace |
| idempotencyKey | desktop | store-level duplicate suppression |
| timestamp | RFC3339 UTC | descriptive only |
| op | `create_mission` \| `submit_approval_decision` \| `cancel_task` \| `cancel_driver_run` | |
| payload | typed per op | `create_mission` payload is a validated `OperatorMissionIntent` |

## create_mission

Payload: `OperatorMissionIntent` (schemaVersion, missionId, objective, scope,
requiresApproval, plus optional constraints/successCriteria/terminationCriteria/
unresolvedAmbiguities/budget/requestedCapability/operation/riskClassification/
policyReason/taskId/requestId).

- The runtime (`RuntimeService.create_mission_with_approval`) builds the
  MissionSpec, TaskNode, and (when `requiresApproval`) HumanApprovalRequest,
  and commits them in ONE transaction under the operator command's
  idempotency key.
- If `requiresApproval` is false → MissionSpec + Task only.
- If `requiresApproval` is true → MissionSpec + Task + HumanApprovalRequest
  (the approval request appears before any driver executes).
- Idempotency: replay of the same idempotencyKey → idempotent/duplicate
  (no second mission; reconstructed result).

## submit_approval_decision

Payload (operator input): requestId, decision (`approve`|`deny`), note (optional).

- The desktop assembles the full `HumanApprovalDecision` contract
  (schemaVersion, operatorId from bound session, decidedAt, idempotencyKey,
  correlationId, sessionId) and submits it.
- `approve` → HumanApprovalDecided(state=approved). Approval permits ONLY the
  originally requested scope (the decision carries no scope; the request's
  scope is authoritative).
- `deny` → HumanApprovalDecided(state=denied). Must prevent execution.
- Expired request → approve refused (runtime `authority` category).
- Already-decided request (different key) → `illegal_transition`.
- Same idempotencyKey replay → idempotent/duplicate.
- operatorId/sessionId mismatch → unauthorized (transport).

## cancel_task / cancel_driver_run

Payload: taskId OR driverRunId, reason (optional).

- The runtime transitions the target aggregate to `cancelled` (terminal) via
  CAPT authority, after an idempotency pre-check.
- Already terminal (different key) → `illegal_transition`.
- Not found → `not_found`.
- Same idempotencyKey replay → idempotent/duplicate (no second cancellation).
- operatorId/sessionId mismatch → unauthorized (transport).

## Response classification vocabulary

`status`: accepted | rejected | idempotent
`classification`: drawn from the runtime error taxonomy (`capt_runtime.errors`
`.category`) — validation, authority, concurrency, idempotency, integrity,
not_found, illegal_transition, capability_denied, reconciliation_required — plus
the desktop-local transport terms `malformed` / `unauthorized` for envelope and
operator/session identity rejections.

The desktop MUST NOT infer success merely because an IPC write succeeded; it reads the
classified receipt.
