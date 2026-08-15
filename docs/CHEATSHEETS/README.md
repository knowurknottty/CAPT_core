# CAPT Current-System Cheat Sheets

Source snapshot: `497dcd711f60759ddf898b56d17d11fbf89c8c92` on `fix/v07-ouroboros-lifecycle-terra`.

These pages document implemented behavior only. “Authority” means CAPT Core/EventStore/RuntimeService truth. A UI, model adapter, provider response, driver observation, or source document is never authority by itself.

## Read in this order

1. [01 Operator cockpit](01_OPERATOR_COCKPIT.md) — commands a human can run now.
2. [02 TUI and provider operations](02_TUI_AND_PROVIDERS.md) — the interactive cockpit, secrets, and failures.
3. [03 Governed execution lifecycle](03_GOVERNED_EXECUTION.md) — exact admission-to-evidence chain.
4. [04 Runtime state, recovery, and evidence](04_STATE_RECOVERY_EVIDENCE.md) — SQLite ledger, idempotency, checkpoints, verification, ClaimGuard.
5. [05 Memory, discovery, and foundry](05_MEMORY_DISCOVERY_FOUNDRY.md) — current non-provider subsystems.
6. [06 API and source atlas](06_API_SOURCE_ATLAS.md) — module-by-module implementation map.
7. [07 Command reference and diagnostic playbooks](07_COMMAND_REFERENCE.md) — copy/paste commands and fault triage.

## Fast safety rules

- Start from an installed/current environment: `capt --help` must list `run` and `tui`.
- Never put a provider key in a command argument, URL, provider record, artifact, evidence, log, or commit.
- Provider config persists `env:VARIABLE` or `keychain:ACCOUNT` references only.
- `capt tui` and `capt run` are the normal operator surfaces. `capt harness command --payload-json` is an expert/debug transport surface, not normal operation.
- A returned provider response is an **untrusted observation**. CAPT independently records artifact-hash evidence and verification/ClaimGuard state.
- A command receipt of `in_progress` is not success and does not authorize replay. Startup reconciliation owns recovery.
- A Task becoming `suspended`, `lost`, or `indeterminate` requires governed reconciliation/cancellation; do not blindly rerun external work.

## State locations

Default runtime state is `~/.capt/` unless `CAPT_STATE_DIR` or `CAPT_SOLO_HOME` is set. It contains `runtime.db`, `runtime.sock`, `runtime.token`, `runtime.pid`, `start.log`, `ui/`, and provider staging output. Use an isolated `CAPT_STATE_DIR` for testing.

## Scope boundaries

This is an operational map, not a promise that every cataloged source helper is a stable public API. Publicly supported practical surfaces are the `capt` CLI, `capt-ui` CLI, `capt tui`, the local authenticated RuntimeService socket protocol, and documented Python runtime composition/service APIs.
