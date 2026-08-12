# CAPT UI Foundation

A thin operator presentation/control layer for CAPT. Every surface — CLI, TUI,
Desktop, future Web — consumes the same `capt_ui.operator` abstraction. No
duplicated runtime, provider, or business logic; authority stays in
RuntimeService.

## Authority invariant

```
RuntimeService
  -> EventStore
  -> Memory
  -> Governance
  -> Drivers
```

The UI is a projection and control surface only. It never writes the ledger,
never promotes driver output, and never fabricates authoritative state.

## Layout

```
capt_ui/
  operator/
    contract.py    # typed enums + state views (RuntimeHealth, Verbosity, ...)
    runtime.py     # Operator facade over RuntimeClient (status/dashboard/...)
    providers.py   # ProviderManager (Phase 2): CRUD, health, local/remote
    models.py      # ModelManager (Phase 3): default/mission/temp overrides
    verbosity.py   # CaveCAPT (Phase 4): minimal/normal/detailed/diagnostic
    onramp.py      # first-run onboarding wizard (Phase 7)
    cli.py         # `capt-ui` console script (shared CLI surface)
    bootstrap.py   # runtime socket/token resolution
  surfaces/
    tui/app.py     # Textual operator console (Phase 5)
    desktop/       # desktop view-model over RuntimeClient (Phase 6)
  acceptance/
    ui_continuity_demo.py # UI continuity workflow demo (Phase 8)
```

## Commands

```zsh
# shared operator CLI (works on base install; no textual required)
capt-ui status
capt-ui dashboard
capt-ui providers --test ollama
capt-ui providers --activate ollama
capt-ui models --set ollama/qwen2.5:7b
capt-ui verbosity --set detailed
capt-ui memory --store "a durable memory"
capt-ui onramp

# TUI (requires the 'ui' extra: pip install -e '.[ui]')
python -m capt_ui.surfaces.tui.app
```

## Prerequisites

A running CAPT runtime exposing an authenticated local socket + token
(`RuntimeService`). The operator layer resolves them via `CAPT_STATE_DIR` /
`CAPT_SOLO_HOME` or `CAPT_SOCK`/`CAPT_TOKEN`.

## Tests

```zsh
pytest tests/test_ui_operator_layer.py \
       tests/test_ui_tui.py \
       tests/test_ui_desktop_surface.py \
       tests/test_ui_onboarding.py \
       tests/test_ui_cli.py \
       tests/test_ui_continuity_demo.py
```

TUI/desktop/continuity tests that need a live runtime skip cleanly when none is
running.
