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

These features remain active integration until the stack merges. PR #47 head `4334657a919f74803e65d9b01aa5054d6d7b9a61` has clean source/editable full-suite verification, but installed-artifact, live-provider, terminal cumulative-stack, and cross-model restart acceptance remain separate gates.

## Hermes TUI workspace metadata

The previously documented `HERMES_LOCAL_002_COMPLETE` workspace/state-map result is currently **unverified operator-supplied metadata**. Terra could not retrieve `evidence/hermes-local-002-r6`, `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`, or `reports/local-evidence/HERMES_AGENT_TUI_WORKSPACE_TESTS_AND_STATE_MAP_8F97AE9_2026-08-17.md` from the current GitHub remote/API. The supplied 98/0/0 and 174/0/2 counts and no-blocker statement must not be used as evidence unless the record is restored and independently verified.

## Authority invariant

```text
UI/operator intent
      -> RuntimeService
      -> governance / EventStore / memory / evidence / DriverHost
```

The UI never fabricates authoritative completion state.