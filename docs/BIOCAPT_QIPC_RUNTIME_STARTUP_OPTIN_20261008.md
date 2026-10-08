# R5 — explicit CAPT RuntimeService startup option for native bioCAPT QIPC

Date: 2026-10-08

## New production host seam

CAPT Core `desktop/capt_runtime_service.py` now optionally registers the separately installed, exact-source-reviewed `capt_ouroboros.qipc_tool_broker` adapter at the canonical RuntimeComposition startup boundary.

Startup arguments (all default off/unset):
- `--enable-biocapt-qipc`
- `--biocapt-qipc-source-root <absolute bioCAPT installation root>`
- `--biocapt-qipc-interpreter <existing Python interpreter>`

Without the explicit enable flag, the registry remains **unchanged**. Giving paths without the enable flag is refused. Enabling without both paths is refused. The package is imported through the normal, trusted Python import path; the host does not add arbitrary writable directories to `sys.path`. The imported R4 adapter checks the reviewed QIPC source digest and composition identity, and refuses any source drift.

Startup code installs only a ToolRegistry descriptor. It cannot create a PolicyDecision, HumanApproval, mission, grant, or lease, and never executes QIPC by registering. It also does not enable new provider inference or Hermes use. If a requested adapter is unavailable, startup **fails closed** rather than silently starting a service missing the expected tool.

## Verified

Tests exercise the real CAPT `create_runtime` composition and actual source-pinned adapter without touching `~/.capt/runtime.db`. Tests cover default-off unchanged tool registry, refusal of unsolicited paths, missing required paths, and explicit source-validated opt-in without durable events. CAPT ToolBroker, CAPT local tool wiring, and runtime composition regression tests pass.

The previous R4 tests independently verify the one-use authorized QIPC dispatch, no direct adapter bypass, exact replay after database restart, inability to reuse a grant, and reconciliation of interrupted work as indeterminate.

## Still required for live deployment — NOT activated

1. Package the vetted `capt-core-ouroboros` release into the **actual RuntimeService Python environment**; verify package and source hashes. Do not use arbitrary path injection.
2. In CAPT's canonical operator-controlled launch configuration, add explicit, reviewed startup arguments binding the one true installed bioCAPT QIPC source and the interpreter.
3. Check in-flight missions/tool executions and checkpoint before any host restart. Do not restart by default or interrupt concurrent operators.
4. Deploy this reviewed host change and restart through the approved recovery path. Verify the resulting **live** ToolRegistry includes `biocapt.qipc`, with zero execution side effects on registration.
5. Obtain real CAPT PolicyDecision and HumanApproval as required for a source-bound, mission/task-bound, maxUses=1 local capability lease; never promote test fixtures into the live ledger.
6. Execute a **single** separately authorized QIPC request. Retrieve durable ToolExecution, capability consumption, raw QIPC receipt, ledger integrity and cross-process restart replay before exposing to user missions.
7. Obtain independent QIPC confidence-calibration evidence and stronger OS-level resource isolation before allowing broad local bioCAPT code execution or self-healing.

The currently running CAPT RuntimeService remains unchanged: its audited EventStore reports integrity `ok` but has no safe live tool-install operation advertised. This PR adds an opt-in future-startup path; no hot patch or hidden live activation occurs.

Existing CAPT Core working tree is on a separate development branch and was **not modified**; this change was built in a clean Git worktree based on `origin/main`.
