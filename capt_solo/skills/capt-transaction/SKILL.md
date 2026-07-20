---
name: capt-transaction
description: Wrap a multi-step operation in a CAPT Solo CTP transaction for auditability and idempotency.
---

# CAPT Solo — Transaction Workflow

Use this skill when an operation has multiple steps that should be recorded as
one auditable unit (deploy, migration, batch edit).

## When to use
- You are about to do something with side effects you may need to prove later.
- You want idempotency so a retry never double-applies.

## Steps
1. Begin:
   - Tool: `capt_begin_transaction`
   - `correlation_id`: a short human-readable id for the operation
   - `idempotency_key`: a unique key; reusing it after commit/abort is rejected.
2. Do the work (each step can be its own memory or tool call).
3. Validate before commit:
   - Tool: `capt_begin_transaction` is not needed again; use the engine's
     `validate(tx_id, {"ok": true})` via a script if you want an audit note.
4. Commit:
   - Tool: `capt_commit_transaction` with the `tx_id` from step 1.
   - Returns a receipt with `status: "committed"`.
5. If something went wrong, abort instead:
   - Tool: `capt_abort_transaction` with the `tx_id`.

## Pitfalls
- A `tx_id` can only be finalized once. Calling commit twice raises an error.
- The `idempotency_key` is global — pick something unique per operation.
- Transactions are append-only; "abort" records the rollback, it does not delete
  the history (that is the audit trail, by design).

## Verification
`capt_health` shows `ctp_integrity: true`; the receipt `status` matches your
final action.
