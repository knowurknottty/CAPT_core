# Council recovery R3 — verified 2026-10-12

## Runtime receipts (read-only observations)

- Council `council-capt-donor-convergence-r1`: durable receipt `terminal`, `complete=true`, `replayForbidden=true`.
- All three latest cohort receipts were `rejected`, even though the enclosing command reported `accepted`.
- Qwen and MiMo: `AUTHORITYVIOLATION` on reused identifiers. Older Qwen run is lost, older MiMo completed but awaits verification.
- GLM: `PROVIDER_HTTP_ERROR`, HTTP 400, 24 physical HTTP attempts, last boundary `request_started`, DriverRun lost, reconciliation required.
- Exact GLM HTTP 400 request-field cause is unknown. Do not replay or assume response-body details.
- The autosaved user draft currently has 3 cohorts with 22 vessels each; old DriverRun identities cannot prove the edited configuration was executed.

## UI corrections

- Tk worker callbacks now use a main-thread queue; no worker calls Tk `after()` directly.
- Read-only execution lanes automatically reattach by durable run IDs after window restart, with historical configuration clearly marked unverified.
- Sanitized provider failure code, HTTP status, and number of HTTP requests display in the lanes.
- Runtime errors, rejection and reconciliation do not masquerade as verified success.
- Requests are blocked when durable Council ID or DriverRun identities already exist. A new Council ID AND Mission ID are required for new execution.
- Existing approval digests still bind the exact requested workflow; no automatic replay or approval occurs.
- Reconnect and safe detach actions are explicit. The window warns before closing during an active call.
- The copy says 'one governed cohort execution', not one physical HTTP request: a tool loop may make multiple HTTP requests.

## Runtime corrections

Implemented separately on the newer runtime source so current governance, encrypted Council receipts, and diagnostics are preserved.
Sequential cohorts now halt after a rejected predecessor. Blocked later cohorts receive durable sanitized receipts without consuming their approvals; the outer command exposes `partial_failure` and `outcome=incomplete`.

## Limitations

Provider transport returned an HTTP 400, but the model/provider request incompatibility is not yet diagnosed. Live service deployment requires a controlled RuntimeService restart; a source test alone does not prove the updated service is running.
