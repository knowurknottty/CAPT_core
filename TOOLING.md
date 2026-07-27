# TOOLING.md — Workspace Tooling Reference

The CAPT workspace is operated through the existing CLI (`capt_cli.py`) plus a
dedicated `workspace` command group, and a set of standalone verifiers. All
commands are local-first and perform no network I/O.

## CLI: `capt_cli.py` (run as `python3 capt_cli.py` or `./capt_cli.py`)

### Workspace group (`capt workspace ...`)

| Command | Behavior |
|---------|----------|
| `capt workspace status` | Branch, HEAD, clean/dirty, active task, current phase, last verified tests, owner gates, next action. |
| `capt workspace validate` | Validate required files exist, JSON schemas, cross-references, task dependency graph, state/checkpoint consistency, registry references. |
| `capt workspace bootstrap` | Print the minimal ordered reading list for a newly attached agent (does not dump the whole repo). |
| `capt workspace checkpoint [--task ID --next "..." --files "a,b"]` | Generate/update `CHECKPOINT.md` from current repo state + supplied task details. Never fabricates test results. |
| `capt workspace tasks [--status STATUS]` | List task records from `tasks/` (and `TASK_QUEUE.md`). |
| `capt workspace next` | Return the highest-priority `ready` task whose dependencies and capability requirements are satisfied. |
| `capt workspace capabilities` | Print the declaring agent's capability manifest (from `architecture/agent-capabilities.schema.json`). |
| `capt workspace archive-checkpoint` | Move `CHECKPOINT.md` to `checkpoints/CHECKPOINT-<date>-<phase>-<commit>.md`. |

### Architecture group (`capt architecture ...`)

- `capt architecture validate` → runs `architecture/validate_registry.py`.
- `capt architecture list` / `capt architecture show <id>`.

### Canon / foundry / memory groups

Existing groups (`memory`, `session`, `procedure`, `prospective`, `retrieval`,
`canon`, `foundry`) are unchanged. The workspace group is additive.

## Standalone verifiers

- `python3 architecture/validate_registry.py` — registry structural + reference checks.
- `python3 verify_runtime.py` — structured runtime verification harness (46 checks).
- `bash doctor.sh` — environment diagnostics.
- `bash verify.sh` — one-command health check.
- `bash install.sh` / `bash uninstall.sh` — plugin + skills install/remove.

## JSON Schemas (in `architecture/`)

- `workspace.schema.json` — workspace contract (required files + key fields).
- `task.schema.json` — task record.
- `checkpoint.schema.json` — checkpoint record.
- `agent-capabilities.schema.json` — capability manifest.

Validate any record with `python3 -m jsonschema` (if installed) or via
`capt workspace validate`, which loads them internally.

## Tests

- `tests/test_workspace.py` — schema, missing-file, invalid-reference,
  stale-checkpoint, circular-dependency, capability-mismatch, bootstrap-ordering,
  CLI integration, clean-checkout.
- `tests/test_workspace_security.py` — hostile task/checkpoint content,
  permission self-grant, secret leakage in logs.

Run the whole suite: `python3 -m pytest -q`.
