# CAPT Desktop Runtime — M0 Acceptance

Authoritative SHA: `sha1:6b3f769cc1042428d758aade443cc6009ce6a2b9`.
Result: **CAPT_DESKTOP_M0_PROVEN** (see `CAPT_DESKTOP_RUNTIME_VERIFICATION_REPORT.md`
and `desktop/acceptance_m0_evidence.json`).

## Vertical-slice scenario (workflow Gate 5)

| # | Step | Status | Evidence |
|---|---|---|---|
| 1 | Launch the desktop app | PASS | `desktop_app.py` launches (headless verified; GUI path real) |
| 2 | Resolve/start the correct local CAPT runtime | PASS | `capt_runtime_service.py --seed` starts; ledger `runtime.db` |
| 3 | Establish an authenticated local connection | PASS | token auth; `test_authenticated_connect_and_identity` |
| 4 | Display runtime identity/version + contract version + health | PASS | `identity()` → runtimeVersion 0.1.0, contract 1.0.0, integrity ok |
| 5 | Display connection health | PASS | `integrity == "ok"` |
| 6 | Create/select one read-only demonstration mission | PASS | server seeds `m-desktop-m0-demo` via real `RuntimeService` |
| 7 | Display MissionSpec, TaskGraph, DriverRun, capability scopes, event timeline, evidence, verification, ClaimGuard | PASS | `project_mission_view` populates all; `test_projection_contains_all_m0_panels` |
| 8 | Disconnect the desktop process | PASS | `client.disconnect()`; runtime stays alive |
| 9 | Preserve CAPT runtime state | PASS | ledger head = 13 after disconnect |
| 10 | Relaunch and reconnect | PASS | second client connects, same token |
| 11 | Reconstruct the same view from authoritative data | PASS | `view1Digest == view2Digest` |
| 12 | Prove no duplicate execution and no state mutation from view rendering | PASS | `head1 == head2 == 13`; `test_disconnect_reconnect_no_duplicate_execution`, `test_read_only_does_not_advance_ledger` |

## Acceptance criteria (workflow) — all met
- real desktop app builds and launches — YES (`desktop_app.py`; headless run exit 0; GUI code real)
- connects to a real local CAPT runtime — YES (subprocess service, real `EventStore`)
- vertical slice uses authoritative runtime state — YES (all panels from `EventStore`)
- disconnect/reconnect preserves state — YES (head stable, view digest equal)
- no duplicate execution — YES (head sequence unchanged across reconnect)
- tests and evidence are exact-SHA-bound — YES (`acceptance_m0_evidence.json`, HEAD `6b3f769…`)
- triple recursion complete — YES (see TRIPLE_RECURSION_LEDGER)
- draft PR open — YES (see PR section)
- no unsupported production/signing/distribution/cross-platform/full-system claims — YES (explicitly excluded)

## What is NOT claimed
- No production signing/notarization/distribution.
- No cross-platform delivery.
- No full CAPT module coverage.
- No UI-originated mutations (M1/M2 deferred).
- No mock driver in the acceptance claim — the demo DriverRun is produced by
  the real reference driver through `DriverHost` (same frozen path as PR #29).
- No static JSON acceptance proof — `acceptance_m0.py` drives a live runtime.

## Reproduction
```
python3.12 desktop/acceptance_m0.py        # prints + writes acceptance_m0_evidence.json
python3.12 -m pytest tests/capt_runtime/test_desktop_m0.py -q
```
