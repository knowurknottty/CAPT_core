# 07 — Command Reference and Diagnostic Playbooks

This is the concise copy/paste reference. Arguments shown are implemented in `capt_cli.py` / `capt_ui/operator/cli.py`; obtain per-command help before scripting a new operation.

## Runtime and evidence

```zsh
capt start
capt start --seed
capt start --state-dir "$HOME/.capt-alt"
capt status
capt status --json
capt evidence
capt evidence --mission MISSION_ID
capt checkpoint
capt checkpoint --idempotency-key stable-key
capt resume
capt stop
capt doctor
```

## Governed providers

```zsh
# Configure only a reference, never plaintext.
capt-ui providers --key-ref openrouter env:OPENROUTER_API_KEY

# Inspect local availability/configuration.
capt-ui providers
capt-ui providers --test ollama
capt-ui providers --test openrouter
capt-ui capabilities
capt-ui models

# Interactive.
capt tui

# Non-interactive. Start runtime first.
capt start
capt run --provider ollama --model MODEL --prompt 'OBJECTIVE'
capt run --provider openrouter --model deepseek/deepseek-v4-flash-0731 --prompt 'OBJECTIVE'
```

## TUI diagnostic path

1. `capt tui` opens but says runtime unavailable: run `capt status`, then `capt start`; inspect `<state-root>/start.log` if start fails.
2. Ollama selector is empty: `capt-ui providers --test ollama`; start/repair Ollama daemon or choose an available local model. CAPT cannot install or start a missing provider automatically.
3. OpenRouter selection reports credentials unavailable: confirm the variable exists in the same zsh process using `test -n "$OPENROUTER_API_KEY" && echo loaded`; then repeat the `--key-ref` command. Do not print the value.
4. OpenRouter returns unauthorized: key/account/model access is external; inspect safe receipt detail and provider health. Do not retry an uncertain external run with a new command merely to force a second charge.
5. TUI output exists but verification panel is contradicted: inspect `capt evidence`; response remains an untrusted observation and task is not accepted.
6. TUI fails after a crash: relaunch `capt tui`; startup reconciliation occurs before duplicate callers are accepted. Inspect `capt evidence` and task/driver state.

## `capt-ui` references

```zsh
capt-ui status [--json]
capt-ui dashboard [--json]
capt-ui providers [--test PROVIDER] [--activate PROVIDER] [--key-ref PROVIDER env:VARIABLE] [--json]
capt-ui capabilities [--json]
capt-ui models [--set PROVIDER/MODEL] [--json]
capt-ui verbosity [--set LEVEL] [--json]
capt-ui memory [--json]
capt-ui onramp [--json]
```

The UI `models --set` command records an operator preference. For governed execution, the actual `capt run`/TUI selected provider/model travels through RuntimeService and is validated against runtime provider configuration.

## Memory/session commands

```zsh
capt memory list --namespace default
capt memory store 'text' --namespace default --tag tag --provenance cli
capt memory search 'query'
capt memory candidates
capt memory conflicts
capt memory pending
capt memory promote ID --state verified --evidence ev-1,ev-2
capt memory pin ID
capt memory archive ID
capt memory restore ID
capt memory explain ID

capt session begin project --objective 'objective'
capt session list
capt session status ID
capt session checkpoint ID --next-action 'next step'
capt session resume ID
capt session consolidate ID
capt session close ID --outcome completed
```

## Foundry commands

```zsh
capt foundry list-skills
capt foundry skill ID
capt foundry candidates
capt foundry validate ID
capt foundry review ID
capt foundry approve ID --reviewer NAME
capt foundry publish ID
capt foundry list-caps
capt foundry cap ID
capt foundry verify-cap ID
capt foundry prove-cap ID
capt foundry govern-cap ID --approver NAME
capt foundry list-bubbles
capt foundry bubble-validate ID
capt foundry bubble-approve ID --approver NAME
capt foundry bubble-install ID
capt foundry curate
capt foundry audit
```

## Expert-only harness examples

```zsh
capt harness start --ledger /path/runtime.db --sock /path/runtime.sock --token-file /path/runtime.token --seed
capt harness health --sock /path/runtime.sock --token-file /path/runtime.token
capt harness capabilities --sock /path/runtime.sock --token-file /path/runtime.token
capt harness checkpoint --sock /path/runtime.sock --token-file /path/runtime.token --idempotency-key KEY
capt harness resume --sock /path/runtime.sock --token-file /path/runtime.token --idempotency-key KEY
capt harness stop --sock /path/runtime.sock --token-file /path/runtime.token --idempotency-key KEY
capt harness command OPERATION --payload-json '{...}' --sock /path/runtime.sock --token-file /path/runtime.token
```

This is intentionally low-level. It is useful for test harnesses and protocol debugging; it is not required for TUI/provider operation.

## Safe operator log collection

```zsh
capt --json status
capt --json evidence > capt-evidence.json
```

Review JSON before sharing. While provider keys are designed not to appear, evidence may include paths, objectives, and untrusted provider output that you may not want to disclose.
