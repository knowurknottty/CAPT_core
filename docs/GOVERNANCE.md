# CAPT Solo v0.4 — Governance Layer

The Governance Layer wraps all consequential actions in CTP transactions and
records an audit trail + receipt. No governance action (publish, deprecate,
revoke, approve) occurs outside a CTP-bounded, audited path.

## Model

- Every governed action runs inside `Governance._act(action, actor, target,
  reason, fn)`, which:
  1. Requires a named actor (anonymous actions rejected).
  2. Begins a CTP transaction (correlation_id scoped to the action+target).
  3. Runs `fn(tx_id)` (the actual mutation).
  4. Commits the CTP transaction; records a `GovernanceReceipt`.
  5. On failure, aborts the transaction and records an `aborted` audit entry.
- All actions are recorded in `governance_audit` (audit_id, action, actor,
  ctp_tx_id, target, reason, status, timestamp, rollback_ref).

## Governed wrappers

- `publish_skill(skill_id, actor, reason=, ctp_tx_id=)`
- `deprecate_capability(...)`, `revoke_capability(...)` (via registry linkage)
- `approve_bubble(...)`, `install_bubble(...)`

## Implemented

- CTP-bounded governance for publish/deprecate/revoke/approve.
- Named-actor requirement (no anonymous governance).
- Audit trail with status + CTP tx linkage.
- `GovernanceReceipt` with action, actor, ctp_tx_id, status, timestamp.

## Experimental

- Rollback references for reversible governance actions.

## Future

- Multi-step governance workflows.
- Quorum / multi-approver governance.

## Limitations

- Governance is single-actor; no quorum yet.
- Rollback is recorded as a reference, not auto-executed.

## Security Boundaries

- No governance action without a named actor.
- No governance mutation outside a CTP transaction.
- Audit entries are append-only; they are never deleted or rewritten.

## Verification

- `tests/test_v04_foundry.py` (governance publish generates receipt).
- `verify_runtime.py` (governance_receipt).
