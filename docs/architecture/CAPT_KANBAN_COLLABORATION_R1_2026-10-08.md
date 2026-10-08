# CAPT Core Collaborative Kanban — R1

**State:** Native Swift work queue implemented and unit-tested; R2 durable
multi-actor coordination is not yet release-certified.

## Donor assessment and integration choices

| Reference | Useful design element | CAPT-native disposition |
| --- | --- | --- |
| [saltbo/agent-kanban](https://github.com/saltbo/agent-kanban) | Agent-native tasks, claims, dependencies, independent human review, session provenance | Adopt the behavioral model; retain CAPT EventStore, RuntimeService and HumanApproval rather than importing Realmroot/Enbor/D1 |
| [BloopAI/vibe-kanban](https://github.com/BloopAI/vibe-kanban) | Isolated coding worktrees, diff/PR/test view, inspectable sessions | Adapt as governed CAPT Node/ToolBroker integrations, not an unrestricted embedded terminal; upstream README says product is sunsetting |
| [appsoftwareltd/vscode-agent-kanban](https://github.com/appsoftwareltd/vscode-agent-kanban) | Plan/Todo/Implement, task-specific context refresh and optional Git worktrees | Use a chat-bound task context seed and receipts; Markdown exports may be artifacts but never authoritative status |
| [sinedied/kanbrawl](https://github.com/sinedied/kanbrawl) | Compact lanes, agent-readable operations, real-time board synchronization | Use a lightweight native projection; do not copy its JSON file store or allow free-form state changes |

**IP boundary:** original implementation against CAPT's contracts; no copied
donor source. Review licenses before any later source-level cherry-picking.
A donor's UI state or task file cannot itself confer CAPT capability.

## R1 native implementation

Files:
- `CAPTKanbanProjection.swift` — pure derivation from CAPT task, mission,
  approval and DriverRun projections, with optional chat-bound Council charter.
- `KanbanBoardView.swift` — searchable six-column native board:
  Planned, Ready, Execution?, Needs verification, Blocked/recovery, Closed history.
- `CAPTOperatorStore.swift` — safe continuation composer and explicit
  per-DriverRun human review actions with required evidence note.
- `MissionBrowserView.swift` — direct **Open Kanban** and **Prepare continuation
  in Chat** controls.

`Execution?` is intentionally NOT labeled live. An event-sourced
`running` marker is not evidence of worker liveness.

Lane mapping is derived only:
`pending -> Planned`, `ready/assigned -> Ready`,
`running -> Execution?`, `awaiting_verification -> Needs verification`,
`suspended/failed -> Blocked/recovery`,
`succeeded/cancelled -> Closed history`.
No board drag/drop state writes. Preserves all historical records.

## User workflow

1. Open **Kanban** in the native sidebar and leave **Actionable** on to focus
   on work that needs intervention. Disable it for the full backlog.
2. Search for a mission ID, task ID, issue term, assigned driver, or model.
3. Open **Inspect** to read actual task/DriverRun state from RuntimeService.
4. For a suspended/failed task, choose **Continue**. CAPT opens a new Chat
   containing original objective, authority context, task identity,
   dependencies and the recovery constraints. Sending the prompt remains
   a separate human action; subsequent model/tool access is governed.
5. For an actionable HumanApproval, choose **HumanApproval** to review it in
   the existing Approvals tab. Never treat an expired stored approval as valid.
6. For a completed DriverRun whose task awaits verification, inspect task,
   DriverRun and supporting Evidence. In **Review verified evidence…**, enter
   a substantive note and explicitly accept or reject. The receipt goes
   through `submit_provider_result_review`; CAPT, not the UI, decides
   the resulting task/mission state.
7. Use **Cancel task…** only when you intend a real terminal cancellation;
   a confirmation dialog explains the consequence.

The same continuation action now appears in the Missions detail view.

## Participant and evidence semantics

- **Humans:** author approvals, reviews and continuation requests.
- **Agents/Bots:** linked through recorded DriverRun/task assignment and
  governed delegation when present; no implied worker heartbeat.
- **Cohorts:** declared cohort IDs may be displayed only when a task ID
  matches an attached Council charter. An approval's provider/model binding
  is a model strategy, not proof of a completed cohort output.
- **Vessels:** displayed as **declared perspectives** only where recorded in
  a matching cohort. They are not separate inference calls or independent
  reviewers absent receipt-backed artifacts.

R1 shows provenance-bound participants and supports human task triage;
it does **not** yet have a durable generic comment/claim/ownership
mutation surface for arbitrary humans, agents, cohorts and vessels.
No marketing claim should describe R1 as full bi-directional collaboration.

## R2 requirements — runtime ownership, not local Swift inventions

1. Authoritative `WorkItem` or `TaskCollaboration` aggregate with typed
   append-only notes, contribution identity, dependency constraints,
   claim/assignment and collaborator scope.
2. Add `work_queue`, `work_item_get`, `task_contribution_list` read
   operations with pagination and evidence-level access control; compose
   with one CAPT EventStore.
3. Add guarded mutation commands for authenticated humans, Bots, agents,
   cohorts and vessels; no peer can self-approve human-only states.
4. Versioned per-participant work claims/leases with expiry, optimistic
   concurrency, idempotency, crash recovery, and explicit reconcile.
5. Human-first realtime board updates from event sequence cursors; scoped
   websocket/SSE or polling without leaking private task data.
6. GitHub issue intake and per-issue worktree/PR/testing pipeline gated by
   CAPT Node and ToolBroker, independent verification and evidence links.
7. CAPT-Bot R5 composition and lifecycle acceptance: one RuntimeService,
   EventStore, ToolBroker, verification/claim plane.
8. Strong unit/integration/AX tests for every consequential control and
   multi-actor race/authority case.

**No second SQLite/Markdown/JSON task database.**

## Restart/reconciliation evidence

The resident runtime was upgraded after a checkpoint. The historical
CAPT Core issue-resolution task, which had been stored `running` since
September 25 without any durable DriverRun/ToolExecution, was
**conservatively suspended** with a separate `MissionStateChanged` to
`suspended` on the original mission. Neither state claims completion.
A watchdog was repaired locally to query the exact aggregate states
instead of trusting truncated projections.

The retry/continuation path is still gated: original task attempt capacity
is exhausted and should not be replayed. Plan a fresh successor task with
a new effect identity only after existing work has been reconciled.
