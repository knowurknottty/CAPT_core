# CAPT UI / Operator Layer

`capt_ui` is a thin projection/control layer over CAPT RuntimeService. CLI/TUI/desktop clients share operator concepts; none becomes an alternate ledger or authority source.

## Merged `main`

The package includes:

- shared operator facade;
- provider manager and adapter registry;
- model manager/favorites/defaults/overrides;
- CaveCAPT presentation verbosity;
- first-run onboarding;
- Textual TUI MVP;
- Tk desktop/operator surface;
- SwiftUI client-contract library;
- UI continuity scaffolding.

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

Use installed `--help` for exact flags.

## Active PR #47

The current TUI integration lane adds:

- `MAX/SPOCK/CAVE CAPT/MIN` response modes;
- 32K–256K requested context budgets;
- `OFF/AUTO/OMNI/META/FORGE/SIGMA` enhancement engines;
- inspect/review/approve prompt-enhancement flow;
- requested/effective context provenance and prompt digest;
- bounded ProviderDriver execution for Ollama native and OpenAI-compatible endpoints.

These features remain active integration until the stack merges and terminal acceptance is recorded.

## Hermes TUI workspace evidence

The dedicated `HERMES_LOCAL_002_COMPLETE` evidence branch records the faithful Hermes Agent TUI workspace/state map with 98/0/0 focused and 174/0/2 broader test results and no product/state-map blocker. It does not close the destructive external-provider/tool-kill rollback E2E gap.

## Authority invariant

```text
UI/operator intent
      -> RuntimeService
      -> governance / EventStore / memory / evidence / DriverHost
```

The UI never fabricates authoritative completion state.