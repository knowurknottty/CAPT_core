# boot-protocol.md

Exact boot procedure for CAPT Core (capt-solo). Every command below was verified
against capt-solo 0.5.0 / Hermes v0.19.0. Do not invent flags — run
`capt <group> --help` before using an option this file does not list.

## 1. Resolve source and environment

```bash
cd "$WORKSPACE"
test -x .venv/bin/capt && source .venv/bin/activate

pwd
git rev-parse --show-toplevel
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short --branch
python --version
command -v python
command -v capt
python -c "import capt_solo, sys; print(capt_solo.__file__); print(capt_solo.__version__)"
pip show capt-solo | sed -n '1,10p'
echo "CAPT_SOLO_HOME=${CAPT_SOLO_HOME:-<unset → ~/.capt-solo>}"
```

Precedence, first match wins:

1. **Installed distribution.** `pip show capt-solo` succeeds and the interpreter
   imports it. If `Editable project location:` is present, the source of truth is
   that checkout — record both.
2. **Explicit `CAPT_SOLO_REPO`.** Use only if set and it contains `capt_cli.py`
   and `capt_solo/`.
3. **Repository-relative discovery**, only when unambiguous: exactly one
   `capt_cli.py` + `capt_solo/` at the workspace root.

Reject when:
- `capt_solo.__file__` resolves outside the resolved source root → `WRONG_CHECKOUT`.
- more than one candidate checkout matches → ambiguous, stop and ask.
- `python --version` is not the venv interpreter → `WRONG_PYTHON`.

Facts that bite:
- CAPT home is **`CAPT_SOLO_HOME`** (default `~/.capt-solo`), *not* `CAPT_HOME`.
- `capt` is not on PATH outside the venv.
- `capt --version` prints argparse usage. Version comes from `capt doctor`
  (`package.version`) or `capt_solo.__version__`.

## 2. Runtime health

```bash
capt doctor
capt --json agent doctor --workspace "$WORKSPACE"
```

`capt doctor` must report `ok: True` with `side_effects: none`,
`network: not used`, `persistence: not created`.

`capt --json agent doctor` must report `single_composition_root: true`. If false,
a second composition root exists — stop, do not proceed.

`provider` in that output is informational. `"no provider configured (set
CAPT_MODEL_ENDPOINT and CAPT_MODEL_ID)"` is normal for boot-only work; it means
`capt agent start` will skip the model turn, not that boot failed.

## 3. Workspace identity

```bash
capt workspace bootstrap     # minimal ordered reading list
capt workspace status        # branch, head, clean, active task, next action
```

`capt workspace validate` exists and is the correct gate before claiming the
workspace is consistent. It is not part of boot.

## 4. Mission

```bash
capt --json mission status                    # list checkpoint ids
capt --json mission resume <mission-id>       # resume plan for one checkpoint
```

Then boot:

```bash
capt --json agent status --workspace "$WORKSPACE" --mission "$MISSION"
```

**`--mission` is mandatory.** Without it, `boot.resolve_mission` iterates every
id in the store and calls `store.load()` on each; any pre-`project_id`/`objective`
checkpoint raises `TypeError: MissionCheckpoint.__init__() missing 2 required
positional arguments: 'project_id' and 'objective'` and the whole command dies.
Classify that as `LEGACY_CHECKPOINT_SCHEMA` (see diagnostics §8), never as
"no mission".

Mission resolution precedence, implemented in CAPT (`agent/boot.py`):
1. explicit `--mission`
2. mission bound to the applicable session checkpoint
3. canonical discovery: exactly ONE non-completed mission
4. otherwise BLOCKED — never guess by recency

`MISSION_AMBIGUOUS` is a correct refusal, not a bug. Supply `--mission`.

## 5. What CAPT does during boot (you do not do any of this)

| step | CAPT does | failure code |
|---|---|---|
| workspace identity | resolve path, git sha, branch | `WORKSPACE_MISSING` |
| mission resolution | precedence above | `MISSION_AMBIGUOUS` / `MISSION_NOT_FOUND` / `MISSION_MISSING` |
| checkpoint validation | mission identity, `event_digest` recompute, project_id vs workspace name, required fields, divergence vs repo | `MISSION_IDENTITY` / `CHECKPOINT_INTEGRITY` / `FOREIGN_WORKSPACE` / `CHECKPOINT_INCOMPLETE` |
| session | reuse or `lifecycle.sessions.begin()` | — |
| directives | split `decisions_made` into active vs superseded on explicit markers (`supersede`, `superseded`, `corrected to`, `rejected`, `overstated`) | — |
| Intent | mint bounded `IntentRecord` from recovered state | — |
| selection | `gate.record_selection(...)` → selected/rejected/stale/missing/conflicting | — |
| ContextPack | `gate.prepare(...)` → `decision.pack.digest` | — |
| MemoryUseGate | `decision.allowed` | `gate_result: BLOCKED` + `block_codes` |
| classification | GOVERNED on PASS; BOOTSTRAP_DEGRADED only if the durable marker `BOOTSTRAP_DEGRADED_AUTHORIZED` is in checkpoint state; else BLOCKED | — |
| evidence | boot trace persisted to `<evidence_dir>/agent-boot/<run>.json` + `.sha256`, proof recorded, KHSB events published | — |

BOOTSTRAP_DEGRADED **cannot be requested by a flag**. It requires the durable
marker in checkpoint state. If you want degraded mode, that is an owner decision
recorded in the checkpoint, not a CLI argument.

## 6. Boot report

Fill every field from the CLI JSON. Any field you cannot source → `UNPROVEN`.

| field | source |
|---|---|
| workspace_root, branch, head, dirty | git commands in §1 |
| python, venv | `python --version`, `command -v python` |
| capt_package, capt_version, capt_source | `pip show capt-solo`, `capt doctor`, `capt_solo.__file__` |
| capt_home | `CAPT_SOLO_HOME` or `~/.capt-solo` |
| mission_id, session_id, checkpoint_id | `agent status` JSON |
| active_directive_ids | `agent status` JSON |
| superseded_directives | `agent status` JSON (absent from status output ⇒ read the boot-trace artifact) |
| selected/rejected/missing/conflicting memory | boot-trace artifact at `<evidence_dir>/agent-boot/` |
| contextpack_digest | `agent status` JSON |
| gate_result | `agent status` JSON |
| execution_mode | `agent status` JSON |
| next_justified_action | `agent status` JSON |
| latest_verified_milestone | checkpoint `current_phase` / repository evidence — never asserted |

Validate against `schemas/boot-report.schema.json`.

## 7. Optional: one governed model turn

```bash
capt --json agent start --workspace "$WORKSPACE" --mission "$MISSION" --input "<task>"
```

Requires a provider: `CAPT_MODEL_ENDPOINT` + `CAPT_MODEL_ID`. Without one, the
command boots and reports `turn: skipped: no provider configured` — that is not
a failure. The provider is invoked exactly once, inside
`CAPTRuntime.execute_model_task`, after the MemoryUseGate. On BLOCKED boot the
provider is never reached. V1 executes **no tools**: a model-emitted tool call is
reported and not executed.

Output modes: `cave` (default) `normal` `verbose` `silent` `audit`, via
`--output-mode`.
