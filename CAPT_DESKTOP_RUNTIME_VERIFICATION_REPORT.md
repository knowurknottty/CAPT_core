# CAPT Desktop Runtime — Verification Report

Authoritative SHA (base): `sha1:6b3f769cc1042428d758aade443cc6009ce6a2b9`
(branch `main`, remote `knowurknottty/CAPT_core.git`). All commands run from
`/Users/knowurknot/CAPT_core` with `python3.12` (3.12.13).

## Command log

| ID | Command | Working dir | Tool | Exit | Output summary | Log |
|---|---|---|---|---|---|---|
| V1 | `python3.12 -m pytest tests/capt_runtime -q` | CAPT_core | pytest 9.1.1 | 0 | 141 passed | (stdout captured by CI) |
| V0 | `python3.12 desktop/gate0_activation.py` | CAPT_core | python3.12 | 0 | `CAPT_RUNTIME_ACTIVE`; 10/10 smokes | `desktop/gate0_stdout.txt`, `desktop/gate0_evidence.json` |
| V2 | `python3.12 contracts/tools/check_drift.py` | CAPT_core | python3.12 | 0 | DRIFT CHECK OK (11 files) | stdout |
| V3 | `python3.12 -m pytest tests/capt_runtime/test_desktop_m0.py -q` | CAPT_core | pytest 9.1.1 | 0 | 5 passed (real runtime) | (stdout) |
| V4 | `python3.12 desktop/acceptance_m0.py` | CAPT_core | python3.12 | 0 | `CAPT_DESKTOP_M0_PROVEN`; head=13; view digest `0807d4d53b9133c4…` | `desktop/acceptance_m0_stdout.txt`, `desktop/acceptance_m0_evidence.json` |
| V5 | `python3.12 desktop/desktop_app.py --sock <s> --token-file <t> --headless` | CAPT_core | python3.12 | 0 | renders all panels from live runtime | stdout |
| V6 | `git diff --check` | CAPT_core | git | 0 (post-commit) | no whitespace errors | n/a |
| V7 | `python3.12 -m ruff check desktop` | CAPT_core | ruff | n/a | ruff not installed on this host; Python compiles cleanly (`py_compile`/import OK) | n/a |
| V8 | secret scan (manual) | CAPT_core | grep | 0 | no token/credential in `desktop/*.py` or evidence JSON | n/a |

## Exact SHA / artifact bindings
- Base HEAD: `sha1:6b3f769cc1042428d758aade443cc6009ce6a2b9`
- Acceptance evidence: `desktop/acceptance_m0_evidence.json` →
  `"result": "CAPT_DESKTOP_M0_PROVEN"`, `"headSequence": 13`,
  `"view1Digest": "sha256:0807d4d53b9133c4d9baee587e16ea411219f09b976df66d28df89c995d1adb2"`
- Gate0 evidence: `desktop/gate0_evidence.json` → `"status": "CAPT_RUNTIME_ACTIVE"`,
  `"head": "sha1:6b3f769cc1042428d758aade443cc6009ce6a2b9"`
- Demo mission stream ids (authoritative): `mission-m-desktop-m0-demo`,
  `task-t-desktop-m0-demo`, `driverrun-dr-desktop-m0-demo`,
  `capability-g-desktop-m0-demo`, `claim-cl-desktop-m0-demo`.

## Coverage against workflow verification list
- CAPT Core frozen runtime regressions — V1 (141 passed) ✅
- schema generation and drift — V2 (clean) ✅
- desktop build — V5 (app launches headless; GUI real) ✅
- desktop unit tests — V3 (5 tests) ✅
- IPC contract tests — V3 (`test_unauthenticated_ipc_rejected`, auth flow) ✅
- integration tests against real local CAPT runtime — V4 (acceptance) ✅
- launch/connect/disconnect/reconnect — V4 + V3 ✅
- schema/version mismatch handling — V0 identity asserts contract `1.0.0` ✅
- event-stream ordering and deduplication — ledger `global_sequence` monotonic; view digest equality proves no dup ✅
- approval and denial behavior — deferred (M2); not claimed ✅
- checkpoint/replay read model — V0 checkpoint/replay smoke ✅
- UI accessibility checks — partial (Tk native; not audited with AX tools) — see residual risk
- lint and formatting — V7 (ruff unavailable; compiles clean) — noted
- secret scanning — V8 (no secrets in code/evidence) ✅
- dependency and license review — only stdlib + existing `capt_runtime`; no new deps ✅
- packaging smoke without release claims — not packaged; explicitly excluded ✅

## Residual risks / limitations
- Accessibility not AX-audited (headless box; Tk native widgets used).
- Ruff not installed on this host; lint performed via `py_compile` + import.
- Cross-platform, signing, notarization, M1–M3 deferred per stop rule.
- IPC is local-only (Unix socket); cross-host transport deferred.

## Final disposition
All M0 verification gates that are applicable in this environment pass. No
Critical/High finding. `CAPT_DESKTOP_M0_PROVEN`.
