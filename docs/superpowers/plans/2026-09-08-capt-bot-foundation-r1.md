# CAPT Bot Foundation R1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first authoritative CAPT Bot substrate without creating a parallel runtime or weakening existing governance.

**Architecture:** Extend the closed CAPT contracts, aggregate ownership model, RuntimeService authority map, and EventStore write path. Bot identity composes cognition/locality/collaboration policy but never owns live capability grants or secrets. Cognitive, skill, and Lab Board state each receive their own aggregate and authority rules.

**Tech Stack:** Python 3.8+, JSON Schema 2020-12, generated Python/TypeScript contracts, SQLite EventStore, pytest.

**Spec:** `docs/architecture/CAPT_BOT_FOUNDATION_R1.md`

## Global Constraints

- Preserve deny-by-default authority semantics.
- EventStore remains the only authoritative mutation path.
- No production code before a failing test.
- No new runtime dependency.
- Bot identity must remain independent of model and live credentials/capabilities.
- Human-only Lab Board blockers must be enforced below the UI.
- Generated contracts must be regenerated from schema source; never hand-edit generated bindings.

---

### Task 1: Contract surface

**Files:** create `contracts/schema/bot.schema.json`; modify `contracts/schema/event.schema.json`, `contracts/schema/index.json`; regenerate bindings.

**Produces:** closed schemas for BotManifest, CognitiveCandidate, SkillCandidate, LabBoardItem and seven new authoritative event payloads.

- [ ] Write contract tests that reference the new definitions/events and fail because they are absent.
- [ ] Run focused tests and confirm RED.
- [ ] Add minimal schema definitions and event union entries.
- [ ] Regenerate contracts and run drift/parity checks.
- [ ] Commit.
### Task 2: Authoritative aggregates

**Files:** create `capt_runtime/aggregates/bot.py`, `cognitive_candidate.py`, `skill_candidate.py`, `lab_board.py`; modify `capt_runtime/aggregates/__init__.py`; test `tests/capt_runtime/test_bot_foundation_aggregates.py`.

**Produces:** disjoint state ownership and transition rules, including human-only unblock and human/governance-only cognitive/skill final promotion.

- [ ] Write aggregate tests first and verify RED.
- [ ] Implement minimal pure state machines.
- [ ] Add them to `ALL_AGGREGATES` and prove ownership remains disjoint.
- [ ] Run focused aggregate suite GREEN.
- [ ] Commit.

### Task 3: Locality compiler

**Files:** create `capt_runtime/bot_locality.py`; test `tests/capt_runtime/test_bot_locality.py`.

**Produces:** deterministic onboarding-intent to execution-locality policy compilation with local-only privacy preservation and safe defaults.

- [ ] Write RED tests for local-only private data, cloud-eligible public research, and invalid contradictory settings.
- [ ] Implement the compiler without granting capabilities.
- [ ] Run focused tests GREEN.
- [ ] Commit.

### Task 4: Governed service persistence

**Files:** modify `capt_runtime/authority.py`, `capt_runtime/governed_service.py`; test `tests/capt_runtime/test_bot_foundation_service.py`.

**Produces:** EventStore-backed commands for registration, cognition proposal/decision, skill candidate transitions, and Lab Board transitions.

- [ ] Write RED service tests proving idempotency and authority boundaries.
- [ ] Add deny-by-default authority acts and service methods.
- [ ] Prove a non-human cannot clear `blocked_human` and cognition cannot self-promote.
- [ ] Run focused service tests GREEN.
- [ ] Commit.

### Task 5: Regression and contract gates

- [ ] Run Bot foundation tests plus aggregate/authority/EventStore suites.
- [ ] Run generated-contract drift and TypeScript parity.
- [ ] Run full Python suite using the repository environment that includes Textual.
- [ ] Run `git diff --check`.
- [ ] Record exact results and remaining non-goals in the implementation note.