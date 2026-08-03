---
status: Accepted (M0-B)
date: 2026-08-03
relates_to: ADR-0111
---

# ADR-0127 — M0-B exclusions

## Context
M0-B is the read-only ExecutionDriver proof. Dominant risk is scope creep into
M0-C or multi-driver work while calling it M0-B.

## Decision
Explicitly OUT of M0-B (each prevented by a testable mechanism):

| # | Excluded | Prevention |
|---|---|---|
| 1 | Repository writes through a driver | `RepositoryWrite` not a legal driver op; dispatch rejects; `FilesystemPolicy.writesAllowed=false` |
| 2 | Git commit/push by driver | no git tool in `ContextSlice`; termination `onUnexpectedWrite: fail` |
| 3 | M0-C (governed isolated write) | `DriverRunAggregate` has no write-worktree state; no git operation in `capt_runtime` |
| 4 | Multi-driver orchestration | registry supports one active driver per run; no scheduler |
| 5 | Distributed event infrastructure | single SQLite (ADR-0104); no network imports |
| 6 | Real autonomous multi-agent execution | driver is a single read-only pass; no agent loop |
| 7 | Generalized Knowledge Bubble execution | `capt_solo/foundry/bubble.py` untouched |
| 8 | RuntimeAggregate | deferred to post-M0-B (Part 16); not implemented |

## Reversal conditions
A new ADR per item before any is reintroduced.
