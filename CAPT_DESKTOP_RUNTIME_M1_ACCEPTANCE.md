# CAPT Desktop Runtime M1 — Acceptance Report

## Scenario A — headless acceptance (desktop/acceptance_m1.py, real runtime)

| # | Step | Result |
|---|---|---|
| 1 | launch CAPT Runtime (authoritative service over local IPC) | PASS |
| 2 | launch desktop (client) | PASS |
| 3 | authenticate | PASS (operator-knowurknot) |
| 4 | create mission from GUI-equivalent command | PASS — MissionSpec created |
| 5 | verify CAPT creates MissionSpec | PASS |
| 6 | verify TaskGraph appears | PASS |
| 7 | verify approval request appears before driver execution | PASS |
| 8 | deny the first request | PASS — state=denied |
| 9 | prove no DriverRun executes | PASS — zero runs for mission after denial |
| 10 | recreate/retry the bounded mission | PASS — new mission + new approval |
| 11 | approve the read-only request | PASS — state=approved |
| 12 | prove DriverRun starts with only approved capabilities | PASS — cap.fs.read only, no widening |
| 13 | cancel the active run | PASS — governed cancel command |
| 14 | prove cancellation recorded and reconciled | PASS — state=cancelled |
| 15 | disconnect desktop | PASS |
| 16 | reconnect | PASS |
| 17 | prove mission/approval/denial/cancellation/events/evidence remain | PASS |
| 18 | replay runtime state | PASS — deterministic |
| 19 | prove no duplicate mission/approval/DriverRun/cancellation | PASS |

Exit code: 0. Final marker: `CAPT_DESKTOP_M1_ACCEPTED`.

## Scenario B — LIVE GUI acceptance (desktop/acceptance_m1_live.py)

Drives the SAME handler logic the visible Tk GUI buttons invoke
(`DesktopApp.gui_create_mission` / `gui_decide` / `gui_cancel` / `gui_refresh_*`),
proving the visible desktop app's behavior, not a parallel client.

| Check | Result |
|---|---|
| connect | PASS (runtime 0.1.0) |
| gui_create_mission accepted | PASS |
| mission_spec authoritative | PASS |
| taskgraph authoritative | PASS |
| approval_request before execution | PASS |
| deny accepted (state=denied) | PASS |
| denial prevents DriverRun | PASS (0 runs) |
| duplicate denial idempotent (same key replay) | PASS |
| reconnect preserves denied state (digest equal) | PASS |
| approve accepted (state=approved) | PASS |
| driverrun begins after approval (running) | PASS |
| approval scope bounded (cap.fs.read /tmp, no widening) | PASS |
| cancel accepted (state=cancelled) | PASS |
| cancellation authoritative | PASS |
| reconnect reconstructs identical state (digest equal) | PASS |
| no duplicate missions / approvals / cancellations | PASS |

Exit code: 0. Final marker: `CAPT_DESKTOP_M1_LIVE_GUI_ACCEPTED`.

## Required outcomes proven

- Mission creation uses real CAPT commands (MissionCreated event). ✓
- Denial prevents execution (no DriverRun after deny). ✓
- Approval permits only bounded execution (approved capability == requested cap.fs.read). ✓
- Cancellation is authoritative and reconciled (DriverRun → cancelled). ✓
- Reconnect reconstructs state (no duplicates; projection digest stable). ✓
- Operator identity bound (spoofing rejected). ✓
- M0 remains green (175 capt_runtime tests pass). ✓
- Contract drift clean. ✓
- Live GUI acceptance passes (visible GUI code paths). ✓
- Exact-SHA evidence: see CAPT_DESKTOP_RUNTIME_M1_EVIDENCE_MANIFEST.json. ✓
- Draft PR open (see final report). ✓
