# CAPT CLI and Operator Commands

CAPT exposes a normal runtime CLI, an operator/UI CLI, and an expert harness surface.

## Normal `capt` surface

```text
capt start
capt status
capt stop
capt checkpoint
capt resume
capt evidence
capt doctor
capt memory ...
```

These commands use normal local defaults (`~/.capt` unless overridden) and avoid requiring socket/token/ledger paths for ordinary operation.

## `capt-ui` operator surface

The installed package also declares `capt-ui`.

Typical merged commands include:

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

Use `capt-ui --help` in the exact installed build for authoritative flags and subcommands.

The Textual dashboard requires the `ui` extra.

## Expert `capt harness` surface

Use the harness when you need explicit runtime paths or raw governed command operations:

```zsh
capt harness start ...
capt harness health ...
capt harness capabilities ...
capt harness command ...
capt harness checkpoint ...
capt harness resume ...
capt harness stop ...
```

Installed help is authoritative for exact arguments.

## Active integration note

PR #47 extends the TUI-run command payload with prompt enhancement, response mode, requested context budget, and human-verification requirements. Those payload fields should not be described as shipped CLI guarantees until the stacked integration merges.

## Authority boundary

Neither CLI parses into raw ledger mutation as a public contract. Consequential operations are admitted by RuntimeService/governance, and UI convenience commands do not enlarge capability.