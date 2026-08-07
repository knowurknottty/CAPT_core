# CAPT Desktop Runtime M1 — Recovery & Gap Analysis

Authoritative repository: /Users/knowurknot/CAPT_core
Authoritative remote: https://github.com/knowurknottty/CAPT_core.git
Branch: feat/capt-desktop-runtime-m1
Base SHA (merged M0): 9d4fee12bc6147d7fe5da9e5025e8eb3291123a
Interpreter: /opt/homebrew/bin/python3.12 (Homebrew-managed; /usr/bin/python3 untouched)

## 1. Phase 0 — Baseline gate (closed)

| Check | Result |
|---|---|
| CAPT runtime activation (Gate0) | CAPT_RUNTIME_ACTIVE |
| Desktop M0 integration tests | 5 passed |
| Desktop M0 acceptance (acceptance_m0.py) | exit 0, CAPT_DESKTOP_M0_PROVEN |
| Contract drift | OK (11 generated files match schema) |
| Authenticated connect/disconnect/reconnect | verified |

Baseline is green. No CAPT_RUNTIME_NOT_ACTIVE, no CAPT_DESKTOP_M1_BLOCKED_BY_BASELINE.

## 2. Phase 1 — Existing M1 capability recovery

Inspected `capt_runtime/services.py`, `capt_runtime/aggregates/`, `capt_runtime/authority.py`,
`contracts/schema/*.json`.

| Capability | Status | Evidence |
|---|---|---|
| Mission creation | implemented & connected | `RuntimeService.create_mission` (services.py:60) |
| TaskGraph creation | implemented & connected | `RuntimeService.create_task` + `transition_task` |
| Human approval request | **ABSENT** (gap) | no `HumanApprovalRequest`/`HumanApprovalDecision` aggregate; no `request_human_approval` |
| Human approval decision | **ABSENT** (gap) | no `submit_human_approval_decision` |
| Cancellation (task/run) | implemented at aggregate, **no service method** | `TaskAggregate`/`DriverRunAggregate` support `cancelled` terminal state; no `cancel_task`/`cancel_driver_run` in `RuntimeService` |
| Authenticated IPC command path | implemented (M0 read-only) | `capt_runtime_service.py` Unix socket + token |
| Operator identity binding | **ABSENT** (gap) | M0 bound only a session token, not an operator identity |
| Command envelope (CommandMetadata) | implemented | `commands.command(...)` with commandId/actor/fingerprint/correlationId |
| Idempotency | implemented (store-level) | `EventStore.commit_command` idempotency key + replay |
| Duplicate suppression | implemented (store) | replay returns original result |

**Conclusion:** The only genuine contract gaps are (a) human approval and (b) operator
identity binding. Cancellation is already contract-supported at the aggregate level and
only needed service methods. Per the workflow's contract-discipline rule, the human-approval
gap is documented in ADR-DT-M1-001 and closed by an additive contract extension under 1.0.0
(no breaking change).

## 3. Components reused (no parallel reimplementation)

- `RuntimeService` (all mutations) — single authority.
- `EventStore` (idempotency, ledger, chain integrity).
- `commands.command` (CommandMetadata envelope).
- `HumanApprovalAggregate` (NEW, but a standard CAPT aggregate; no desktop authority).
- `desktop/desktop_runtime_client.py` projections (extended, not rewritten).
- `desktop/desktop_app.py` (extended with M1 tabs; M0 shell preserved).

## 4. Scope limits respected

No packaging, signing, notarization, M2, multi-agent orchestration, plugin marketplaces,
Mode B Hermes interception, RuntimeAggregate/Manifest/Identity, or general repository-write
automation were added. The desktop remains a presentation + governed-command surface; CAPT
owns all aggregates, events, evidence, verification, ClaimGuard, checkpoints, replay.
