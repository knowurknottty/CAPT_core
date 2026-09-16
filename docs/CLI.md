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
capt run --provider <id> --model <id> --prompt <text>
capt skills ...
capt tui
```

Runtime commands use normal local defaults (`~/.capt`, overridden by `CAPT_STATE_DIR`) and avoid requiring socket/token/ledger paths for ordinary operation. Standalone `capt memory` commands instead use Solo MemoryEngine storage under `~/.capt-solo` (overridden by `CAPT_SOLO_HOME`); they do not write runtime memory through RuntimeService.

## `capt-ui` operator surface

The installed package also declares `capt-ui`.

Typical merged commands include:

```zsh
capt-ui status
capt tui
capt-ui capabilities
capt-ui providers
capt-ui models
capt-ui verbosity
capt-ui memory
capt-ui onramp
```

Use `capt-ui --help` in the exact installed build for authoritative flags and subcommands.

`capt-ui dashboard` prints a summary and exits. Launch the interactive Textual console with `capt tui`, which starts or connects to the runtime before opening the TUI.

Textual is a base dependency in the current package; the `ui` extra also declares it.

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

## Merged operator controls

PR #117 merged the formerly stacked prompt/provider controls. Later native/TUI work adds governed authority selection, prompt-proposal review, and provider-result review. These UI/runtime payloads are not all flags on `capt run`; current `capt run --help` exposes provider, model, prompt, state directory, and idempotency key.

The semantic runtime API exposes `operator_chat_new`, `operator_execution_config_set`, `operator_prompt_submit`, and `operator_proposal_select`, with revision/digest checks. These are runtime operations, not additional `capt-ui` subcommands. Read queries include `approvals`, `missions`, `tasks`, and `checkpoints`.

UPG-024 adds the packaged `capt-debt` cognitive-debt cockpit entrypoint; it projects concrete debt and does not certify correctness.

## Authority boundary

Runtime execution and approval operations are admitted by RuntimeService/governance, and UI convenience commands do not enlarge capability. Standalone Solo memory operations, `capt-ui memory --store`, and local UI preferences are separate storage paths; their success is not EventStore admission, verification, or completion. Despite requiring a runtime connection, `capt-ui memory --store` currently writes through the Solo MemoryEngine.
