# CAPT Desktop Runtime M1 — Verification Report

All commands run with /opt/homebrew/bin/python3.12 (Homebrew-managed; /usr/bin/python3 untouched).
Repository: /Users/knowurknot/CAPT_core. Branch: feat/capt-desktop-runtime-m1.
Base SHA: sha1:9d4fee12bc6147d7fe5da9e5025e8eb32911293a.

## Commands & results

| Command | Result |
|---|---|
| `python3.12 desktop/gate0_activation.py` | CAPT_RUNTIME_ACTIVE (10/10) |
| `python3.12 -m pytest tests/capt_runtime/test_desktop_m0.py -q` | 5 passed |
| `python3.12 -m pytest tests/capt_runtime/test_desktop_m1.py -q` | 7 passed |
| `python3.12 -m pytest tests/capt_runtime/test_desktop_m1_security.py -q` | 11 passed |
| `python3.12 -m pytest tests/capt_runtime/test_desktop_m1_adversarial.py -q` | 16 passed |
| `python3.12 -m pytest tests/capt_runtime -q` | 175 passed |
| `python3.12 -m pytest tests/capt_runtime/test_contracts.py -q` | 7 passed (cross-language parity) |
| `python3.12 contracts/tools/check_drift.py` | DRIFT CHECK: OK (11 generated files match schema) |
| `python3.12 desktop/acceptance_m1.py` | exit 0 → CAPT_DESKTOP_M1_ACCEPTED |
| `python3.12 desktop/acceptance_m1_live.py` | exit 0 → CAPT_DESKTOP_M1_LIVE_GUI_ACCEPTED |
| `python3.12 desktop/acceptance_m0.py` | exit 0 → CAPT_DESKTOP_M0_PROVEN |
| `python3.12 desktop/desktop_app.py --m1 --headless` | exit 0 (live GUI headless render) |
| `git diff --check` | clean |
| secret scan (GitGuardian/gitleaks) | no bare hex; digests carry sha1:/sha256: |

## M1-specific test inventory

tests/capt_runtime/test_desktop_m1.py (7):
- test_create_mission_real_command
- test_deny_prevents_execution
- test_approve_permits_bounded_execution
- test_operator_spoofing_rejected
- test_duplicate_create_is_idempotent
- test_cancel_driver_run
- test_reconnect_reconstructs_state

tests/capt_runtime/test_desktop_m1_security.py (11):
- duplicate CreateMission, duplicate approval, conflicting approval, stale approval,
  expired approval, duplicate cancellation, unauthenticated command, operator spoofing,
  schema mismatch, approval scope widening, rendering trust labeling.

tests/capt_runtime/test_desktop_m1_adversarial.py (16):
- unauthenticated command, invalid session, operator-ID spoofing, approval for
  nonexistent request, cancellation-without-authority, desktop-cannot-inject-event,
  desktop-cannot-mutate-db, fake-verification-read-only, terminal-escape-stripped,
  fake-verified-not-trusted, html-inert, oversized-truncated, path-traversal-inert,
  symlink-inert, secret-not-trusted, render-authoritative-vs-untrusted.

## Live GUI acceptance

desktop/acceptance_m1_live.py drives the visible GUI handler logic
(DesktopApp.gui_create_mission / gui_decide / gui_cancel / gui_refresh_*) over
authenticated IPC to the authoritative runtime. 18 checks, all passing
(CAPT_DESKTOP_M1_LIVE_GUI_ACCEPTED).

## Security findings

- Operator-ID spoofing: rejected (unauthorized). ✓
- Session token not treated as unrestricted authority. ✓
- Approval scope widening attempt: ignored (decision carries no scope). ✓
- Expired approval: approve refused (unauthorized). ✓
- Unauthenticated IPC command: rejected. ✓
- Duplicate commands: suppressed (idempotent). ✓
- No desktop-local authoritative state; CAPT owns all aggregates. ✓

## Residual risks

1. Single-user macOS operator model; no multi-user/tenant isolation (documented, out of scope).
2. Acceptance DriverRun is seeded via the authoritative RuntimeService (real CAPT state path)
   rather than a live external driver, to remain harmless and deterministic; the cancellation
   command still traverses the same governed path a live driver would.

## Not started (per scope limits)

packaging, signing, notarization, distribution, M2, multi-agent orchestration, plugin
marketplaces, Mode B Hermes interception, RuntimeAggregate/Manifest/Identity, general
repository-write automation.
