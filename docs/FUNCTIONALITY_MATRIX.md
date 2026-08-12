# CAPT Functionality Matrix

Authoritative, evidence-based view of what the merged CAPT Core `main`
actually does, separating **shipped** from **proven-in-flight** from
**release-gate (not yet claimed)**.

Legend:
- **SHIPPED** — reachable through the installed CLI / surface and verified.
- **MVP** — functional operator surface, acceptable for v0.6.
- **PROVEN** — exercised with real evidence in this closure.
- **GATE** — declared release gate; present but NOT YET PROVEN.

## Operator surfaces

| Capability | CLI | TUI | Desktop (Tk) | SwiftUI | Status |
|---|---|---|---|---|---|
| Runtime start/status/stop | ✅ | ✅ | ✅ | – | **SHIPPED** |
| Checkpoint / resume | ✅ | ✅ | ✅ | – | **PROVEN** |
| Doctor (env diagnostics) | ✅ | – | – | – | **SHIPPED** |
| Durable memory store/search | ✅ | ✅ | ✅ | – | **PROVEN** |
| Evidence / verification view | ✅ | ✅ | ✅ | – | **SHIPPED** |
| Provider/model discovery | ✅ | ✅ | ✅ | – | **SHIPPED** |
| CaveCAPT verbosity | ✅ | ✅ | – | – | **SHIPPED** |
| Human approve/deny | – | ✅ | ✅ | – | **MVP** |

## Runtime / governance

| Capability | Status |
|---|---|
| EventStore ledger + integrity | **SHIPPED** |
| Authenticated IPC (socket/token) | **SHIPPED** |
| Mission/task aggregates | **SHIPPED** |
| Policy → grant → lease → driver | **PROVEN** (governed dispatch recorded in ledger) |
| External Hermes ExecutionDriver (Mode A) | **PROVEN** (real `hermes -z` process dispatched) |
| Checkpoint / replay / restart / resume | **PROVEN** (no-repeat verified) |
| ClaimGuard | **SHIPPED** |

## Provider execution (release gate)

| Capability | Status |
|---|---|
| Provider registration | **SHIPPED** |
| Health probe / model list | **SHIPPED** |
| Real governed model execution | **GATE** — NOT YET PROVEN |
| Cross-model continuity (A→B via restart) | **GATE** — NOT YET PROVEN |

## CAPT Lite / MCP (companion repo `capt-workspace-mcp`)

See the MCP repository — the MCP Gateway is merged there with 33 tools
(14 workspace + 17 CAPT-facing + Lite L0/L1).

## Honest boundaries

- Provider registration ≠ provider execution.
- A continuity **demo** (synthetic model IDs) ≠ real cross-model proof.
- The SwiftUI package is a **library**, not a shipped app.
