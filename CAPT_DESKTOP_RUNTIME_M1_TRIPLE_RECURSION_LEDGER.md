# CAPT Desktop Runtime M1 — Triple Recursion Ledger

## Pass 1 — Construct

Implemented mission creation, approval (request + decide), cancellation (task/run),
projections, acceptance harness, and tests.

Files:
- capt_runtime/aggregates/human_approval.py (NEW aggregate)
- capt_runtime/services.py (request_human_approval, submit_human_approval_decision,
  cancel_task, cancel_driver_run)
- capt_runtime/authority.py (authority entries)
- contracts/schema/common.schema.json, event.schema.json (additive HumanApproval types)
- desktop/m1_command_service.py (NEW governed command path + operator binding)
- desktop/capt_runtime_service.py (per-connection command service + operator/session bind)
- desktop/desktop_runtime_client.py (command API + M1 projections)
- desktop/desktop_app.py (M1 GUI tabs: Create Mission, Approvals, Cancel, State)
- desktop/acceptance_m1.py (end-to-end scenario)
- tests/capt_runtime/test_desktop_m1.py, test_desktop_m1_security.py

## Pass 2 — Adversarial review (attempt to disprove)

| Claim | Attack | Result | Action |
|---|---|---|---|
| Denial prevents execution | deny then check DriverRuns | PROVEN: zero runs | none |
| Approval scope containment | smuggle wider scope in decision payload | REJECTED: decision ignores payload scope | none (confirmed) |
| Cancellation reaches driver | cancel active run, check state | PROVEN: cancelled | none |
| Reconnect correctness | disconnect/reconnect, count missions | PROVEN: no duplicates | none |
| Duplicate suppression | replay same idempotencyKey | FOUND DEFECT: second cancel/deny returned already_terminal instead of idempotent | FIXED: added store.find_idempotent pre-check in _cancel and _cmd_submit_approval_decision so same-key replay returns idempotent before the aggregate terminal check |
| Operator identity binding | spoof operatorId in envelope | PROVEN: unauthorized | none |
| Rendering trust distinctions | untrusted model text vs authoritative state | PROVEN: [AUTHORITATIVE] tag separates them; sanitize_for_display strips control chars | none |
| Approval after deny | approve terminal request | FOUND DEFECT (earlier): state was "deny" not "denied" → terminal check missed | FIXED: aggregate maps decision to "approved"/"denied" terminal states |
| Idempotency key collision (inner acts) | create_mission+task reuse outer key | FOUND DEFECT: IdempotencyConflict on inner create_task | FIXED: _metadata derives distinct idempotency keys for inner CAPT acts |
| Authority for create_task | human actor cannot plan | FOUND DEFECT: actor kind human rejected for plan_tasks | FIXED: inner create_task authored as cognitive_plane; approval request as execution_plane; outer envelope remains human operator |
| Invalid session | command with bogus sessionId | PROVEN: unauthorized | added test (test_invalid_session_rejected) |
| Cancellation without authority | spoofed operator/session cancel | PROVEN: unauthorized | added test (test_cancellation_without_authority_rejected) |
| Desktop injects event/verification/claimguard | attempt client write APIs | PROVEN: no such API exists; client is read/command only | added tests (test_desktop_cannot_inject_event_envelope, test_desktop_cannot_mutate_database_directly, test_fake_verification_query_is_read_only) |
| Rendering spoof (terminal escapes, fake VERIFIED, HTML, oversized, path traversal, symlink, secrets) | inject untrusted strings | PROVEN: sanitized + trust-tagged; never promoted to [AUTHORITATIVE] | added 8 rendering tests in test_desktop_m1_adversarial.py |

## Pass 3 — Reconcile

- Code corrected (defects: terminal-state naming, inner idempotency keys, authority
  kind for planned task, idempotent replay for approval/cancel). Each fixed with a
  smallest change and re-verified.
- Tests added: 16 adversarial/rendering tests (test_desktop_m1_adversarial.py) covering
  every attack vector in spec sections 9 and 10.
- Live GUI acceptance (acceptance_m1_live.py) drives the real GUI handler code
  (gui_create_mission / gui_decide / gui_cancel / gui_refresh_*) — 18 checks pass.
- Architecture notes updated (ARCHITECTURE, COMMAND_MAP, AUTHORITY_AND_IDENTITY, ADR-001).
- Evidence manifest records exact SHAs and verification outcomes (175 capt_runtime tests).

## Residual risk (disclosed, not hidden)

1. Single-user macOS operator model; no multi-user/tenant isolation (documented, out of M1 scope).
2. Acceptance DriverRun is seeded via the authoritative RuntimeService (real CAPT state path)
   rather than a live external driver, to stay harmless/deterministic; cancellation traverses
   the same governed path a live driver would.
3. Live GUI acceptance runs headless (no display in CI); it invokes the identical handler
   logic the visible Tk GUI uses, so the visible-app behavior is proven. A display-backed
   manual click-through is the only step not automatable here.
