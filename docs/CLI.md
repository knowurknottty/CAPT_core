# CAPT CLI

The `capt` command-line interface has two surfaces:

1. **Normal-human surface (v0.6, recommended)** — `capt start`, `capt status`,
   `capt stop`, `capt checkpoint`, `capt resume`, `capt evidence`,
   `capt doctor`, and `capt memory ...`. No paths or tokens required.
2. **Expert surface** — `capt harness ...` for full control (explicit
   socket/token/ledger paths) and `capt runtime mission-begin` for persisted
   mission transactions.

The CLI is SQL-free: it calls domain methods, never raw SQL.

## Normal-human surface (v0.6)

| Command | What it does |
|---|---|
| `capt start [--seed] [--state-dir D]` | start runtime with defaults (`~/.capt`) |
| `capt status [--state-dir D]` | runtime health + version + capabilities |
| `capt stop [--state-dir D]` | stop the runtime |
| `capt checkpoint [--idempotency-key K] [--state-dir D]` | save authoritative state |
| `capt resume [--idempotency-key K] [--state-dir D]` | resume after restart |
| `capt evidence [--mission M] [--state-dir D]` | human-readable proof/verification view |
| `capt doctor` | environment diagnostics |
| `capt memory store "<text>" [--namespace N] [--tag T]` | store durable memory |
| `capt memory search "<terms>"` / `capt memory list` | retrieve memories |
| `capt --version` | version |

State directory resolution: `$CAPT_STATE_DIR` overrides, otherwise `~/.capt`.
Use a short `CAPT_STATE_DIR` if your home path would exceed the Unix socket
path limit.

## Expert surface

### harness

- `start --ledger L --sock S --token-file T [--seed]` — start the service.
- `health --sock S --token-file T` — runtime health.
- `capabilities --sock S --token-file T` — advertised operations.
- `checkpoint/resume/stop --sock S --token-file T --idempotency-key K`.
- `command <op> --payload-json J --sock S --token-file T` — send a governed
  runtime command.

### runtime

- `mission-begin --ledger L --objective O [--operator X]` — run one persisted
  mission transaction and close deterministically.

### foundry

- `list-skills`, `skill <id>`, `candidates`, `validate <id>`, `review <id>`,
  `approve <id>`, `publish <id>`, `list-caps`, `cap <id>`, `verify-cap <id>`,
  `prove-cap <id>`, `govern-cap <id>`, `list-bubbles`, `bubble-validate <id>`,
  `bubble-approve <id>`, `bubble-install <id>`, `curate`, `audit`.

### memory / session / procedure / prospective / retrieval

Standard groups (store, search, session begin/checkpoint, procedure runs,
prospective intents, retrieval feedback). All call domain methods — no raw SQL.

## Security boundaries

- No raw SQL in the CLI.
- Governance actions require a named approver/reviewer.
- Published skills/bubbles record CTP receipts.
- The runtime surface is authenticated over a local Unix-domain socket; the
  token file is local session material, not a remote credential.

## Verification

- `tests/test_v04_cli.py` — foundry CLI subcommands.
- `tests/test_v04_boundary.py` — CLI uses domain methods, not raw SQL.
- `tests/test_v06_cli_onramp.py` — v0.6 normal-human surface
  (memory store, doctor, start/status/checkpoint/resume/evidence/stop).
