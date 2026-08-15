# 01 — Operator Cockpit

## First-run truth check

```zsh
capt --help
capt-ui --help
```

A current provider/TUI build lists `run` and `tui` in `capt --help`, and `capt-ui providers --help` lists `--key-ref`. If it does not, you are invoking an older install. Do not attempt provider operations against an old command surface.

## Normal operating sequence

```zsh
# One terminal; key remains only in that shell process.
export OPENROUTER_API_KEY="$(tr -d '\r\n' < ~/noexcuses/fake.env)"
capt-ui providers --key-ref openrouter env:OPENROUTER_API_KEY
capt tui
```

`capt tui` starts the local RuntimeService when necessary, then opens the Textual UI. It does not print a provider key.

Non-interactive equivalent:

```zsh
capt start
capt run --provider ollama --model qwen3.6-fable-fusion:latest --prompt 'Respond exactly: CAPT OLLAMA ALIVE'
capt run --provider openrouter --model deepseek/deepseek-v4-flash-0731 --prompt 'Respond exactly: CAPT OPENROUTER ALIVE'
capt evidence
capt checkpoint
capt stop
```

`capt run` requires a running RuntimeService. It uses the current directory as the read-only target root; run it in a deliberate target directory/repository, not a broad shared directory such as `/tmp`.

## `capt` groups

| Group | Purpose | Important operations |
|---|---|---|
| `memory` | CAPT Solo memory review and maintenance | `list`, `store`, `inspect`, `search`, `candidates`, `conflicts`, `pending`, `promote`, `pin`, `archive`, `restore`, `explain` |
| `session` | Session lifecycle | `list`, `begin`, `status`, `checkpoint`, `resume`, `consolidate`, `close` |
| `procedure` | Procedure inspection | `list`, `inspect`, `runs` |
| `prospective` | Prospective-memory queue | `list`, `ready`, `resolve` |
| `retrieval` | Retrieval feedback/adaptation | `feedback`, `adaptation`, `reset` |
| `foundry` | Proof-governed skill/capability/bubble workflows | `list-skills`, `skill`, `candidates`, `validate`, `review`, `approve`, `publish`, `list-caps`, `cap`, `verify-cap`, `prove-cap`, `govern-cap`, `list-bubbles`, `bubble-validate`, `bubble-approve`, `bubble-install`, `curate`, `audit` |
| `runtime` | Canonical Core operation | `mission-begin` |
| `harness` | Expert/debug socket surface | `start`, `health`, `capabilities`, `checkpoint`, `resume`, `stop`, `command` |
| ramp | Normal local RuntimeService control | `start`, `status`, `stop`, `checkpoint`, `resume`, `doctor`, `evidence` |
| provider | Governed model use | `run`, `tui` |

All global and most subgroup commands accept `--json` for machine-readable output. Use `capt <group> --help` and `capt <group> <operation> --help` for canonical argument syntax.

## Ramp commands

```zsh
capt start [--state-dir PATH] [--seed]
capt status [--state-dir PATH]
capt stop [--state-dir PATH]
capt checkpoint [--state-dir PATH] [--idempotency-key KEY]
capt resume [--state-dir PATH] [--idempotency-key KEY]
capt evidence [--state-dir PATH] [--mission MISSION_ID]
capt doctor
```

- `start` creates/uses `runtime.db`, `runtime.sock`, `runtime.token`, and `runtime.pid` under state root. It launches `desktop.capt_runtime_service` detached and waits boundedly for health.
- `status` reports runtime integrity/version/ledger summary and command/query capabilities.
- `checkpoint` asks authoritative RuntimeService to create a checkpoint.
- `resume` asks RuntimeService to resume a checkpointed runtime; it is not permission to repeat uncertain external work.
- `evidence` projects mission specification, evidence, verification, and ClaimGuard disposition from the runtime.
- `stop` sends governed shutdown, not a blind process kill.
- `doctor` is local diagnostics; it does not send prompts to any provider.

## State-directory isolation

```zsh
export CAPT_STATE_DIR="$(mktemp -d)"
capt start
# use CAPT
capt stop
rm -rf "$CAPT_STATE_DIR"
unset CAPT_STATE_DIR
```

For ad-hoc tests use isolated state. For normal use, omit the variable and CAPT uses `~/.capt`. `CAPT_SOLO_HOME` is also respected by legacy/current UI configuration resolution.

## Mission begin

```zsh
capt runtime mission-begin --ledger /path/runtime.db --objective 'Bounded objective' --operator cli-operator
```

This is a direct Core composition path for creating a mission; normal model work should use `capt tui` or `capt run` so it follows the operator command/service lifecycle.

## Failure-reading cheat sheet

| Receipt/status | Meaning | Operator action |
|---|---|---|
| `accepted` | Command completed its current admission path; inspect result/outcome | Read result/evidence; accepted receipt is not always a verified completion claim |
| `idempotent` | Durable receipt replayed | Do not assume a second provider call occurred |
| `in_progress` | A prior durable admission remains unresolved | Wait/reconcile; do not reissue to force execution |
| `rejected`, `validation` | Payload/config contract rejected | Correct command/config; no provider call should occur |
| `rejected`, `internal_failure` | Runtime/driver failure | Read safe `detail`; inspect `capt status`, `capt evidence`, runtime start log |
| Task `suspended`/DriverRun `lost` | External dispatch outcome uncertain | Use governed reconciliation/cancellation, never blind replay |
| verification `contradicted` | Evidence/verification did not support claim | Treat output as observed but unverified; preserve state |

## Expert harness warning

`capt harness command OP --payload-json ... --sock ... --token-file ...` exists for integration/debugging. It requires manually constructed authenticated socket paths and command envelopes. It is deliberately not the recommended normal-human provider route. Use `capt run` or `capt tui` instead.
