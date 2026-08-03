# CAPT Desktop Runtime M1 — Command Map

All commands are issued by the desktop over authenticated IPC and executed by
`RuntimeCommandService` → `RuntimeService` → CAPT aggregates → `EventStore`.

## Envelope (every command)

| Field | Source | Notes |
|---|---|---|
| commandId | desktop (hash of op+payload) | unique per command |
| operatorId | bound session (`operator-<localuser>`) | NOT taken from payload |
| sessionId | bound per-connection random | NOT taken from payload |
| schemaVersion | fixed `1.0.0` | mismatch → malformed |
| correlationId | desktop | trace |
| causationId | optional | for chained commands |
| idempotencyKey | desktop (or derived) | store-level duplicate suppression |
| timestamp | RFC3339 UTC | descriptive only |
| op | `create_mission` \| `submit_approval_decision` \| `cancel_task` \| `cancel_driver_run` | |
| payload | typed per op | |

## create_mission

Payload: missionId, objective, rawRequest, normalizedRequest, constraints,
successCriteria, terminationCriteria, unresolvedAmbiguities, requiresApproval,
requestedCapability, operation, scope, riskClassification, policyReason.

- If `requiresApproval` is false → creates MissionSpec only (accepted).
- If `requiresApproval` is true → creates MissionSpec + Task + HumanApprovalRequest
  (accepted; approval request appears before any driver executes).
- Idempotency: if mission already exists → idempotent/duplicate (no second mission).

## submit_approval_decision

Payload: requestId, decision (`approve`|`deny`), note (optional).

- `approve` → HumanApprovalDecided(state=approved). Approval permits ONLY the originally
  requested scope (the decision carries no scope; the request's scope is authoritative).
- `deny` → HumanApprovalDecided(state=denied). Must prevent execution.
- Expired request → approve refused (unauthorized).
- Already-decided request → already_terminal.
- Same idempotencyKey replay → idempotent/duplicate.
- operatorId/sessionId mismatch → unauthorized.

## cancel_task / cancel_driver_run

Payload: taskId OR driverRunId, reason (optional).

- Transitions the target aggregate to `cancelled` (terminal) via CAPT authority.
- Already terminal → already_terminal.
- Not found → not_found.
- Same idempotencyKey replay → idempotent/duplicate (no second cancellation).
- operatorId/sessionId mismatch → unauthorized.

## Response classification vocabulary

`status`: accepted | rejected | idempotent
`classification`: accepted | rejected | policy_denied | unauthorized | stale_version |
duplicate | expired | not_found | already_terminal | malformed | internal_failure

The desktop MUST NOT infer success merely because an IPC write succeeded; it reads the
classified receipt.
