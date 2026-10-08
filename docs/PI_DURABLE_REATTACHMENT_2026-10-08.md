# PI Durable Request Reattachment — Implementation and Acceptance

## Mechanism

- **Before** invoking the model compiler, RuntimeService writes a durable
  `pi-admission:pp-…` claim into its existing encrypted idempotency ledger.
  Every admission is bound to the fingerprint of the original prompt,
  runtime preferences, model, provider and request scope. A duplicate
  with a changed payload is refused.
- The original prompt-proposal EventStore transition remains the completion
  authority. The separate admission is deliberately not proof of completion.
- `pi_request_status(proposalId)` is an authenticated, read-only runtime
  query; it never schedules a provider operation. It reports:
  - `completed`: a real PromptProposal exists; returns the authoritative
    persisted snapshot, including compiler status and stage records.
  - `in_progress`: a live, locally tracked attempt is still executing.
  - `indeterminate`: admitted but no committed proposal exists and there
    is no tracked live attempt. The external provider might have charged.
  - `not_found`: no admission or proposal exists; this is **not**
    evidence that an earlier pre-admission attempt never happened.
- `safeToAutoRetry` is always false. The service never automatically sends
  a second model request after an ambiguous transport or process failure.
  The original admission survives daemon restarts.
- Swift persists the `piRequestID` **before dispatch** inside the encrypted
  native chat session. Its coordinator uses a stable attempt identity for
  command idempotency and proposal identity. The native UI offers
  **Check original PI request**, and startup/reconnect performs read-only
  reconstruction of an unresolved stored attempt. A completed proposal
  reenters the normal explicit HumanApproval review path.
- No independent bot, worker, or client may manufacture PI completion from
  a timeout; only the PromptProposal EventStore aggregate is authoritative.

## Negative and restart checks

The test suite covers:
- Same attempt while the mocked compiler is blocked; a duplicate returns
  an in-progress receipt without a second provider invocation.
- Completed proposal retrieval and same-key idempotent replay.
- Simulated exception **after the external boundary**, EventStore closure
  and reopening: status stays indeterminate and the same-key replay
  cannot invoke the provider again.
- Same proposal identity with different prompt is rejected.
- Unknown or invalid proposal IDs never infer safe retry.
- Authenticated Unix socket query of a completed simulated PI request
  returns its proposal and leaves the ledger head sequence unchanged.
- Swift JSON session round-trip persists the pending attempt identity;
  legacy session JSON without the optional field still decodes.

## Code tests before deployment

- Clean dedicated worktree Core Python: **1,979 passed, 70 skipped,
  13 deselected**. Log:
  `~/capt-node-workspace/pi-reattach-python-full.log`.
- Native Swift: **152 passed, 9 skipped, 0 failures**. Log:
  `~/capt-node-workspace/pi-reattach-swift-final.log`.
- These tests do not send paid model requests.

## Release limitations

- An in-progress attempt that loses its runtime process becomes
  `indeterminate`; this is a deliberate safety state, not a failure
  to recover and replay.
- **Stop waiting for PI** abandons only the local UI wait. It does not
  guarantee cancellation of a remote provider invocation or refund.
- A user may deliberately start a new request after inspecting receipts;
  that is a *different* action and may incur new usage. No automated
  replay is permitted.
- Generic multi-service/HTTP operation reattachment, provider billing
  reconciliation, and progress streaming require independent contracts.
