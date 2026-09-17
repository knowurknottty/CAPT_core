# CAPT Bot Crew + Standup R2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add governed transient delegate assignments and a deterministic standup projection over CAPT Bot/Lab Board state.

**Architecture:** Delegate Assignment is a new EventStore aggregate whose state coordinates registered Bots but grants no authority. Standup is a pure read projection over existing aggregate snapshots. Both extend RuntimeService/replay rather than introducing a parallel store.

**Tech Stack:** Python 3.8+, JSON Schema 2020-12, generated Python/TypeScript bindings, SQLite EventStore, pytest.

**Spec:** `docs/architecture/CAPT_BOT_CREW_STANDUP_R2.md`

## Global Constraints

- Preserve authority-absent-by-default.
- Delegate assignment never grants a capability or credential.
- Parent/delegate/Mission/Task references must resolve before commit.
- Closed event contracts and deterministic replay are mandatory.
- Standup projection is read-only.

---

### Task 1: Delegate contracts and aggregate

**Files:** `contracts/schema/bot.schema.json`, `contracts/schema/common.schema.json`, `contracts/schema/event.schema.json`, `capt_runtime/aggregates/delegate_assignment.py`, generated bindings, tests.

**Interfaces:** `DelegateAssignmentAggregate.create(spec)`, `.transition(current, to_state, actor, reason, at)`.

- [ ] Write failing contract/aggregate tests for role, depth, expiry, and terminal transitions.
- [ ] Run the tests and confirm RED for missing types/aggregate.
- [ ] Add closed schemas/events and minimal aggregate implementation.
- [ ] Regenerate contracts and confirm tests GREEN.

### Task 2: Runtime admission and replay

**Files:** `capt_runtime/authority.py`, `capt_runtime/governed_service.py`, `capt_runtime/replay.py`, `tests/capt_runtime/test_delegate_assignment_service.py`.

**Interfaces:** `GovernedRuntimeService.assign_delegate(spec, metadata)` and `transition_delegate_assignment(assignment_id, to_state, reason, metadata)`.

- [ ] Write failing service tests proving parent/delegate/Mission/Task/depth/expiry admission.
- [ ] Confirm invalid references and delegation policy fail before EventStore mutation.
- [ ] Implement RuntimeService admission and closed event writes.
- [ ] Add replay-equivalence coverage and confirm GREEN.

### Task 3: Standup projection

**Files:** `capt_runtime/lab_standup.py`, `tests/capt_runtime/test_lab_standup.py`.

**Interfaces:** `build_lab_standup(store) -> dict`.

- [ ] Write failing projection tests for crew, active delegates, human tasks/requests/blockers, active/verifying/waiting/done sections.
- [ ] Implement deterministic read-only projection with no secrets or authority objects.
- [ ] Confirm projection does not mutate EventStore sequence or aggregate versions.
- [ ] Run focused tests, full suite, contract drift, Python/TypeScript parity, fatal/import lint, and `git diff --check` before commit.
