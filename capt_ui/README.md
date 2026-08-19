# CAPT UI / Operator Layer

`capt_ui` is a thin projection/control layer over CAPT RuntimeService. CLI, TUI, Tk, native macOS, and MCP-compatible clients share operator concepts; none becomes an alternate ledger or authority source.

## Surfaces

- shared Operator facade;
- Textual TUI;
- Tk reference/fallback operator surface;
- native Swift `CAPTNativeMac` application in the terminal convergence line;
- provider/model controls and coherent global/session selection;
- CaveCAPT presentation verbosity;
- evidence/approval/runtime/Cohort/provenance/security projections.

Typical commands:

```zsh
capt-ui status
capt-ui dashboard
capt-ui capabilities
capt-ui providers
capt-ui models
capt-ui verbosity
capt-ui memory
capt-ui onramp
```

## Terminal convergence status

PR #117 is the coherent convergence candidate. It incorporates the older PR #47 cockpit/provider work, durable Cohort and replay upgrades, native hardening, authored-skill approval binding, and PR #118 provider/model coherence repair.

Fresh candidate verification includes green Python, Swift normal/strict/TSan, native build, MCP PR #2, and shared-runtime cross-surface acceptance. See [`../docs/CURRENT_STATE.md`](../docs/CURRENT_STATE.md) for exact status.

## Authority invariant

```text
UI/operator intent
      -> authenticated RuntimeService
      -> governance / EventStore / memory / evidence / DriverHost
```

The UI never fabricates authoritative completion, verification, capability, or provider-dispatch state.
