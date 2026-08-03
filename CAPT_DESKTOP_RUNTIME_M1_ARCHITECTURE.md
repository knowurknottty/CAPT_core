# CAPT Desktop Runtime M1 — Architecture

## Runtime-first convergence (M1 reframe)

The desktop is an instrumentation harness used to prove CAPT Runtime. All
authority, planning, orchestration, and idempotency live in the runtime. The
desktop is thin: authenticated transport, command submission, projection
rendering, operator interaction, local UX.

```
Desktop (UNTRUSTED operator surface — thin)
   |  authenticated IPC (Unix socket + per-connection token)
   |  command envelope: commandId, operatorId, sessionId, schemaVersion,
   |    correlationId, idempotencyKey, timestamp, op, payload (OperatorMissionIntent)
   v
RuntimeCommandService  (per authenticated connection; bound to operatorId+sessionId)
   |  transport envelope validation (required fields, schema, op, identity binding)
   |  assembles the HumanApprovalDecision contract from operator input + bound identity
   |  delegates to RuntimeService  <-- ALL authority/planning/orchestration here
   v
CAPT RuntimeService + EventStore  (AUTHORITATIVE)
   |  require_authority (capt_runtime.authority)
   |  planning: builds MissionSpec / TaskNode / HumanApprovalRequest from intent
   |  orchestration: create_mission_with_approval commits 3 aggregates in ONE transaction
   |  idempotency replay: find_idempotent pre-check (no duplicate aggregates)
   |  aggregate mutation (CAPT aggregates own all state)
   |  transactional event commit (EventStore.commit_command)
   v
CAPT RuntimeService + EventStore  (AUTHORITATIVE)
   missions, tasks, human_approval, capabilities, driver_runs, claims,
   events, evidence, verification, ClaimGuard, checkpoints, replay
```

The desktop never builds aggregates, evaluates authority, plans tasks, or
mutates CAPT state. Those live in `capt_runtime`. The only desktop-owned
concerns are: per-connection operator/session binding (transport
authentication), command routing, contract assembly for the operator
decision, and receipt/error *presentation* (the classification string is the
runtime's own error category, not a re-derived desktop taxonomy).

## What moved into Runtime (convergence delta)

- **Planning** (`_build_mission_spec`, `_build_task`, `_build_approval_request`)
  → `RuntimeService._build_*_from_intent`. The runtime owns mission logic.
- **Orchestration** (chain create_mission → create_task → request_human_approval)
  → `RuntimeService.create_mission_with_approval(intent, metadata)`: one
  governed transaction, outer idempotency key, correct actor kind per
  aggregate (human mission, cognitive_plane task, execution_plane approval).
- **Idempotency replay** (`find_idempotent` pre-checks for approval/cancel)
  → `RuntimeService.submit_human_approval_decision` / `cancel_task` /
  `cancel_driver_run` check `store.find_idempotent` before the aggregate
  transition (which would otherwise raise IllegalTransition on a terminal
  target). The desktop no longer duplicates this logic.
- **Error classification** (`_classify_error` re-mapped `errors.py` categories)
  → removed; the desktop presents `exc.category` from `capt_runtime.errors`
  (the runtime owns the taxonomy). No duplicate classification.
- **Contract** (`OperatorMissionIntent`) added — the operator→runtime input is
  now an explicit, validated contract (stronger contract, thinner client).

## New CAPT contracts (ADR-DT-M1-001, additive under 1.0.0)

- `OperatorMissionIntent` (common.schema.json) — high-level operator intent;
  runtime owns all planning from it.
- `HumanApprovalRequest` (common.schema.json) — bounded request for operator authorization.
- `HumanApprovalDecision` (common.schema.json) — operator approve/deny, idempotent by key.
- Event types `HumanApprovalRequested`, `HumanApprovalDecided` (event.schema.json).
- Stream prefix `human_approval-` added to `StreamId` pattern.
- `HumanApprovalAggregate` (capt_runtime/aggregates/human_approval.py).
- Authority entries: `request_human_approval` (execution/governance/system),
  `submit_human_approval_decision` (human), `cancel_task`/`cancel_driver_run`
  (execution/human/system).

## Command boundary

| Command | Happy path | Rejections (runtime categories) |
|---|---|---|
| `create_mission` | accepted | malformed (validation), unauthorized (transport), duplicate (idempotent) |
| `submit_approval_decision` | accepted | unauthorized (transport), not_found, illegal_transition, authority (expired), duplicate (idempotent), malformed |
| `cancel_task` / `cancel_driver_run` | accepted | unauthorized (transport), not_found, illegal_transition, duplicate (idempotent), malformed |

Every response explicitly classifies: accepted | rejected | idempotent, plus a
`classification` drawn from the runtime's error taxonomy
(`capt_runtime.errors` `.category`): validation, authority, concurrency,
idempotency, integrity, not_found, illegal_transition, capability_denied,
reconciliation_required, plus the desktop-local transport terms malformed /
unauthorized for envelope/identity rejections.

## Operator identity

- The runtime service binds `operatorId = "operator-" + local user` and a per-connection
  `sessionId` at authentication time.
- The command envelope MUST carry the same `operatorId`/`sessionId`; mismatch → `unauthorized`
  (transport rejection, before any runtime call).
- The decision's `operatorId` is assembled by the desktop from the bound session, never
  from the operator payload (prevents operator-ID spoofing and scope widening).
- Single-user macOS desktop: NO enterprise identity, multi-user, or tenant-isolation claim.

## Projections

`desktop_runtime_client.project_authoritative_state` rebuilds the full view from final
aggregate snapshots (idempotent) + event timeline. Duplicate/out-of-order event delivery is
safe because projections read snapshots, not replayed events. Reconnect reconstructs state
deterministically from the same authoritative data.
