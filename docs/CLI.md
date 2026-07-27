# CAPT Solo v0.4 — CLI

The CLI (`capt_cli.py`) is the operator surface for all subsystems. It is
SQL-free: it calls domain methods, never raw SQL.

## Usage

```
python3 capt_cli.py [--json] <group> <action> [args]
```

## Groups & actions

### foundry
- `list-skills` — list all skills with lifecycle state.
- `skill <id>` — show a skill (includes `degradations` if any).
- `candidates` — list skill candidates.
- `validate <id>` — run the 12-stage harness.
- `review <id>` — submit for review.
- `approve <id> [--reviewer X]` — approve a skill.
- `publish <id> [--ctp TX]` — publish (records CTP receipt).
- `list-caps` — list capabilities.
- `cap <id>` — show capability (includes structured `degradations`).
- `verify-cap <id>` — verify capability proof.
- `prove-cap <id>` — mark capability proven.
- `govern-cap <id> [--approver X]` — governance-approve to verified.
- `list-bubbles` — list bubbles.
- `bubble-validate <id>` — run 12-step bubble validation.
- `bubble-approve <id> [--approver X]` — approve bubble.
- `bubble-install <id> [--ctp TX]` — install bubble (CTP receipt).
- `curate` — run skill curator.
- `audit` — show governance audit trail.

### memory / session / procedure / prospective / retrieval
Standard v0.1–v0.3 groups (store, search, session begin/checkpoint, procedure
runs, prospective intents, retrieval feedback). The `procedure runs <id>` and
`retrieval feedback` commands call domain methods (`ProcedureStore.get_runs`,
`FeedbackStore.list_feedback`) — no raw SQL.

### architecture
- `validate` — validate `architecture/registry.yaml` (fitness checks).
- `list` — list canonical subsystems.
- `show <id>` — show a subsystem by id.

### canon
- `show` — show constitutional invariants I-01..I-15.
- `check <text>` — (if implemented) check a statement against invariants.

### workspace (Universal Workspace layer)
Local-first, no network I/O. Operates on repository state so a fresh agent can
discover authority, state, tasks, and capabilities without a bootstrap prompt.
- `status` — branch/HEAD/clean/active_task/owner_gates/concurrency.
- `validate` — schema + consistency checks (files, dirs, schemas, tasks,
  checkpoint, task deps, registry namespaces). Exit nonzero on any `fail`.
- `bootstrap` — minimal ordered reading list for a newly attached agent.
- `checkpoint [--task T] [--next CMD] [--in-progress TXT]` — regenerate CHECKPOINT.md.
- `tasks` — list `tasks/*.json`.
- `next` — highest-priority READY task with satisfied deps + capabilities.
- `capabilities` — default local-first capability manifest.
- `archive-checkpoint` — move CHECKPOINT.md to `checkpoints/CKPT-<commit>.md`.

Example:
```bash
python3 capt_cli.py workspace validate      # CI gate for workspace consistency
python3 capt_cli.py workspace bootstrap      # what to read first
python3 capt_cli.py workspace next           # what to do next
```

## Implemented

- All foundry subcommands (skills, capabilities, bubbles, governance).
- Degradation surfaced in `cap` output.
- JSON output via `--json`.

## Experimental

- None.

## Future

- Interactive review workflows.
- Bubble export from CLI.

## Limitations

- CLI is local-only; no remote execution.
- `--ctp` is an optional external tx id; the CLI still records its own CTP
  receipt internally.

## Security Boundaries

- No raw SQL in the CLI (boundary-audited).
- Governance actions require a named approver/reviewer.
- Published skills/bubbles record CTP receipts.

## Verification

- `tests/test_v04_cli.py` (9 tests covering foundry subcommands).
- `tests/test_v04_boundary.py` (CLI uses domain methods, not raw SQL).
