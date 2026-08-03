---
status: Accepted (M0-B)
date: 2026-08-03
relates_to: ADR-0120, ADR-0123
---

# ADR-0124 — Driver reconciliation

## Context
M0-B requires reconciliation that detects duplicate observations, missing
receipts, interrupted execution, orphaned runs, stale leases, and expired budgets
— with NO automatic re-execution without policy approval.

## Decision
Reconciliation is a read-only CAPT procedure over the event ledger + driver-run
state. It emits a `DriverReconciliationRecord` listing detected anomalies and a
recommended disposition (`DriverReconciliationResult`), but performs NO driver
re-invocation and NO state mutation beyond recording the report. Re-execution
requires an explicit policy-approved command (governance act), never automatic.

## Result enum
`reconciled_completed`, `reconciled_failed`, `reconciliation_requires_human`,
`safe_to_retry`, `retry_forbidden`, `external_state_unknown`.

## Consequences
- `reconciliationStatus` on `DriverRun` drives whether a run is promotable.
- Orphaned runs (no parent mission/task or no lease) are flagged, not silently
  adopted.

## Reversal conditions
Only if a later gate defines an explicitly policy-approved auto-retry authority
plane; out of scope for M0-B.
