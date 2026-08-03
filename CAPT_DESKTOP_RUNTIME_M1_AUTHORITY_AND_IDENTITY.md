# CAPT Desktop Runtime M1 — Authority & Identity

## Who is the operator?

This is a single-user macOS desktop operator console. The operator is the local user
(`getpass.getuser()`). At authentication time the runtime service binds:

- `operatorId = "operator-" + <local user>`
- `sessionId = "sess-" + <random per connection>`

These are returned to the desktop in the auth response and captured by the client. Every
subsequent command envelope MUST carry the same `operatorId` and `sessionId`. A mismatch
is rejected as `unauthorized` by `RuntimeCommandService._validate_envelope`.

## What the session token does NOT grant

The per-connection session token authenticates the IPC connection. It is NOT treated as
unrestricted authority. Every command still passes through CAPT authority evaluation
(`RuntimeService.require_authority`) and aggregate invariants. The token alone cannot:

- approve a request on behalf of a different operator;
- widen an approval's scope;
- cancel a run the operator did not open;
- mutate CAPT databases, aggregates, event logs, evidence, or verification.

## Operator-ID spoofing is rejected

A command envelope claiming a different `operatorId` (e.g. `operator-someone-else`) is
rejected as `unauthorized` before any CAPT mutation. Verified by
`test_operator_spoofing_rejected` (test_desktop_m1.py) and
`test_operator_spoofing_rejected` (test_desktop_m1_security.py).

## Approval scope containment

The `HumanApprovalDecision` carries no `scope`. The authoritative scope is the
`HumanApprovalRequest.scope` recorded when the request was raised. An attempt to smuggle a
wider scope in the decision payload is ignored — the service builds the decision from the
bound operator, not the payload. Verified by `test_approval_scope_widening_rejected`.

## Expiry

A request past `expiresAt` cannot be approved (the aggregate raises `AuthorityViolation`
→ classified `unauthorized`). Denial of an expired request is still recorded for audit but
approval is refused.

## Explicit limitation (honest disclosure)

This M1 build makes NO enterprise identity, multi-user, or tenant-isolation claim. It is a
single-operator local desktop. Cross-user authority, SSO, and tenant boundaries are out of
scope for M1 and would require additional CAPT identity aggregates not introduced here.
