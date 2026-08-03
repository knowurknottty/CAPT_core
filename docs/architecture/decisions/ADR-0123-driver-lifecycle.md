---
status: Accepted (M0-B)
date: 2026-08-03
relates_to: ADR-0120
---

# ADR-0123 — Driver lifecycle state machine

## Context
M0-B requires a driver lifecycle (created, queued, running, suspended, completed,
cancelled, failed, reconciled) and recovery after restart. M0-A's
`DriverRunAggregate` already defines most of these states.

## Decision
Extend the M0-A `DriverRunState` machine with `queued` (between created and
running) to model the dispatch queue. Keep the terminal set
{completed, failed, cancelled, reconciled}. Reconciliation is entered from `lost`
(interrupted execution detected at restart). The state machine remains the sole
owner of driver-run lifecycle; the driver process can only REQUEST transitions via
observations/claim proposals — CAPT decides.

## Legal transitions
created → queued → running → (suspended ⇄ running) → completed | failed | cancelled
running → lost → reconciled (via CAPT reconciliation)
terminal states immutable except explicit reconciliation transition where justified.

## Consequences
- `DriverRunStateMachine` centralizes all legal transitions and terminal checks.
- Checkpoint recovery reconstructs `DriverRun` state from the ledger, never from
  driver memory.

## Reversal conditions
None for M0-B.
