# CAPT Desktop Runtime M1 — Architecture

## Authority boundary (unchanged from M0)

```
Desktop (UNTRUSTED operator surface)
   |  authenticated IPC (Unix socket + per-connection token)
   |  command envelope: commandId, operatorId, sessionId, schemaVersion,
   |    correlationId, causationId, idempotencyKey, timestamp, typed payload
   v
RuntimeCommandService  (per authenticated connection; bound to operatorId+sessionId)
   |  schema + command validation
   |  operator/session identity binding (rejects spoofed operator/session)
   |  CAPT authority evaluation (RuntimeService.require_authority)
   |  aggregate mutation (CAPT aggregates own all state)
   |  transactional event commit (EventStore.commit_command)
   v
CAPT RuntimeService + EventStore  (AUTHORITATIVE)
   missions, tasks, human_approval, capabilities, driver_runs, claims,
   events, evidence, verification, ClaimGuard, checkpoints, replay
```

The desktop never writes to the ledger, aggregates, evidence, or verification records.
It issues governed commands and renders read-only projections.

## New CAPT contracts (ADR-DT-M1-001, additive under 1.0.0)

- `HumanApprovalRequest` (common.schema.json) — bounded request for operator authorization.
- `HumanApprovalDecision` (common.schema.json) — operator approve/deny, idempotent by key.
- Event types `HumanApprovalRequested`, `HumanApprovalDecided` (event.schema.json).
- Stream prefix `human_approval-` added to `StreamId` pattern.
- `HumanApprovalAggregate` (capt_runtime/aggregates/human_approval.py).
- Authority entries: `request_human_approval` (execution/governance/system),
  `submit_human_approval_decision` (human), `cancel_task`/`cancel_driver_run`
  (execution/human/system).

## Command boundary (Phase 2)

Required M1 commands and their classified responses:

| Command | Happy path | Rejections |
|---|---|---|
| `create_mission` | accepted | malformed, unauthorized (spoof), duplicate (idempotent) |
| `submit_approval_decision` | accepted | unauthorized, not_found, already_terminal, expired, duplicate (idempotent), malformed |
| `cancel_task` / `cancel_driver_run` | accepted | unauthorized, not_found, already_terminal, duplicate (idempotent), malformed |

Every response explicitly classifies: accepted | rejected | idempotent, plus a
`classification` of: accepted, rejected, policy_denied, unauthorized, stale_version,
duplicate/idempotent, expired, not_found, already_terminal, malformed, internal_failure.

## Operator identity (Phase 3)

- The runtime service binds `operatorId = "operator-" + local user` and a per-connection
  `sessionId` at authentication time.
- The command envelope MUST carry the same `operatorId`/`sessionId`; mismatch → `unauthorized`.
- The decision's `operatorId` is taken from the bound session, never from the payload
  (prevents operator-ID spoofing and scope widening).
- Single-user macOS desktop: NO enterprise identity, multi-user, or tenant-isolation claim.
  This limitation is documented in CAPT_DESKTOP_RUNTIME_M1_AUTHORITY_AND_IDENTITY.md.

## Projections (Phase 7)

`desktop_runtime_client.project_authoritative_state` rebuilds the full view from final
aggregate snapshots (idempotent) + event timeline. Duplicate/out-of-order event delivery is
safe because projections read snapshots, not replayed events. Reconnect reconstructs state
deterministically from the same authoritative data.
