# CAPT_SKILL_SOURCE_MAP.md

Forensic source map for the `capt-core-runtime` Hermes skill. Every row below was
observed live on 2026-07-31 in this environment. Nothing is inferred.

## 1. Hermes runtime

| item | value | evidence |
|---|---|---|
| version | Hermes Agent v0.19.0 (2026.7.20), upstream e444d165 | `hermes --version` |
| install dir | `/Users/knowurknot/.hermes/hermes-agent` | `hermes --version` |
| install method | git | `hermes --version` |
| Hermes python | 3.11.15 | `hermes --version` |
| primary skills root | `~/.hermes/skills` | `agent/skill_utils.py:566 get_all_skills_dirs()` → `[get_skills_dir()] + get_external_skills_dirs()` |
| plugins root | `~/.hermes/plugins` | directory listing |
| active profile | `default` | session env |

### Skill schema (authoritative, read from loader source)

| rule | value | evidence |
|---|---|---|
| file | `SKILL.md` at skill dir root | `tools/skill_manager_tool.py` create/patch paths |
| frontmatter | YAML fenced by `---`, must be a mapping | `_validate_frontmatter`, `tools/skill_manager_tool.py:566-620` |
| required keys | `name`, `description` | same, lines 600-603 |
| description hard cap | 1024 chars | `MAX_DESCRIPTION_LENGTH`, `tools/skill_manager_tool.py:175` |
| description cap for NEW skills | 60 chars | `SKILL_PROMPT_DESC_LIMIT = 60`, `agent/skill_utils.py:833`; enforced only on the create path (line 607) |
| body | must be non-empty after frontmatter | line 616-618 |
| SKILL.md size cap (agent writes) | 100,000 chars | `MAX_SKILL_CONTENT_CHARS`, `tools/skill_manager_tool.py:513` |
| support dirs NOT scanned as skills | `references/`, `templates/`, `assets/`, `scripts/` | `SKILL_SUPPORT_DIRS`, `agent/skill_utils.py:50` |
| excluded dirs | `.git .github .hub .archive .venv venv node_modules site-packages __pycache__ .tox .nox .pytest_cache .mypy_cache .ruff_cache` | `EXCLUDED_SKILL_DIRS`, `agent/skill_utils.py:27-44` |
| namespacing | one optional category directory level: `~/.hermes/skills/<category>/<skill>/SKILL.md` | `tools/skill_manager_tool.py:641-642` |
| precedence | local `~/.hermes/skills` first, then `skills.external_dirs` in config order | `agent/skill_utils.py:566-574` |

Consequence: `schemas/` and `tests/` inside a skill package are NOT in
`SKILL_SUPPORT_DIRS`. They are also not `SKILL.md` files, so the scanner
(`rglob("SKILL.md")`) never sees them — safe to ship, but they are only
reachable by absolute path, not via `skill_view(file_path=...)`. Design
decision recorded in `CAPT_SKILL_DECISION.md` §4.

## 2. Canonical CAPT installation

| item | value | evidence |
|---|---|---|
| distribution | `capt-solo` 0.5.0 | `pip show capt-solo` |
| resolution | editable install | `Editable project location: /Users/knowurknot/capt-solo` |
| site-packages | `/Users/knowurknot/capt-solo/.venv/lib/python3.12/site-packages` | `pip show` |
| imported module | `/Users/knowurknot/capt-solo/capt_solo/__init__.py` | `python -c "import capt_solo"` |
| `capt_solo.__version__` | `0.5.0` | same |
| console script | `/Users/knowurknot/capt-solo/.venv/bin/capt` | `command -v capt` (inside venv) |
| venv python | 3.12.13 | `python --version` inside `.venv` |
| system python | 3.9.6 (`/usr/bin/python3`) — WRONG for CAPT | `python3 --version` |
| CAPT home env var | **`CAPT_SOLO_HOME`** (default `~/.capt-solo`) | `capt_solo/core/config.py:5,16-18,52` |
| `CAPT_HOME` | not used by capt-solo | absence in `grep -rn CAPT_HOME capt_solo/` |
| observed CAPT home | `~/.capt-solo` (`CAPT_SOLO_HOME` unset) with `backups/ components/ data/` | directory listing |
| mission checkpoint store | `<workspace>/.capt/checkpoints/*.json` + `events.jsonl` | `CheckpointStore.__init__`, `capt_solo/evidence` |
| `.capt/` git status | gitignored | `.gitignore:58` |

`capt` is NOT on PATH outside the venv (`command -v capt` empty in the login
shell). Environment activation is mandatory, not optional.

## 3. Canonical CAPT CLI surface (`capt --help`, verified)

Top-level groups:
`doctor release memory session procedure prospective retrieval architecture canon
foundry workspace verify evidence continuity mission selfmod agent`

Commands the skill uses (and only these):

| command | signature | purpose |
|---|---|---|
| `capt --version` | *(prints usage; version comes from `capt doctor`)* | see §6 limitation |
| `capt doctor` | no args | runtime inspection, no persistence, no network |
| `capt --json agent doctor --workspace P` | | runner wiring, `single_composition_root` boolean |
| `capt --json agent status --workspace P --mission M` | | boot-only recovery report |
| `capt --json agent checkpoint --workspace P --mission M` | | boot + mission checkpoint boundary |
| `capt --json agent resume --workspace P --mission M` | `--mission` REQUIRED | fresh-process reconstruction |
| `capt --json agent start --workspace P --mission M --input T` | | boot + one governed no-tool turn |
| `capt --json mission status` | | list checkpoint ids |
| `capt --json mission resume <mission_id>` | positional | resume plan |
| `capt mission checkpoint --mission-id M [--project-id --objective --phase --next --head]` | | write mission checkpoint |
| `capt --json session list` | | sessions |
| `capt session begin <namespace> [--objective]` | | new session |
| `capt session status <id>` | positional | session state |
| `capt --json memory list [--namespace N]` | | memory records |
| `capt --json memory search <query>` | positional | retrieval |
| `capt workspace status` / `bootstrap` / `validate` | | workspace identity + reading list |
| `capt --json evidence status` | | evidence store summary |

`--json` is a **top-level** flag (`capt --json <group> <cmd>`), not per-subcommand.

## 4. Canonical CAPT runtime API (`capt_solo.api`, 58 exports)

Composition root and owned subsystems — the skill invokes, never re-creates:

| symbol | role | construction site |
|---|---|---|
| `CAPTRuntime` | single composition root | `CAPTRuntime.load(config)` → `__init__` |
| `MemoryEngine` | memory | `runtime.engine` (`runtime.py` `__init__`) |
| `CTPRuntime` | transactions | `runtime.ctp` |
| `KHSB` | event bus | `runtime.bus` |
| `LifecycleManager` | sessions/checkpoints | `runtime.lifecycle` |
| `ProofEngine` | proofs | `runtime.proof` |
| `CapabilityRegistry` | capabilities | `runtime.registry` |
| `ClaimGuard` | claim verdicts | `runtime.claimguard` |
| `MemoryUseGate` | mandatory gate | `runtime.gate` |
| `RuntimeConfiguration` | fields: `home db_path journal_dir evidence_dir event_log_path mission_id` | `RuntimeConfiguration.from_env()` |

`CAPTRuntime` public methods: `load close execute execute_model_task
prepare_external_model_turn commit_external_model_turn abort_external_model_turn`.

Agent Runner (ADR-0001 Outcome C), `capt_solo/agent/`:
`boot.py` (fail-closed boot pipeline), `contracts.py` (frozen v1 dataclasses,
`AGENT_SCHEMA_VERSION = "capt.agent.v1"`), `runner.py` (`AgentRunner`,
`resume_report`), `output.py` (`OutputPolicy` rendering).

Execution modes are runtime constants, not prose:
`EXECUTION_MODE_GOVERNED|BOOTSTRAP_DEGRADED|BLOCKED` (`contracts.py:33-35`).
Output modes: `cave normal verbose silent audit` (`contracts.py:40-51`).

Mission resolution precedence is implemented in `boot.resolve_mission`
(`boot.py:76-108`): explicit → session-bound → exactly-one-active discovery →
BLOCKED. Never newest-wins.

`BOOTSTRAP_DEGRADED` requires the durable marker `BOOTSTRAP_DEGRADED_AUTHORIZED`
in checkpoint state (`boot.py:44`, `_degraded_authorized` at `boot.py:353-356`) —
it cannot be requested by a flag.

## 5. Hermes ↔ CAPT plugin

| item | value | evidence |
|---|---|---|
| source | `capt_solo/plugin/__init__.py` + `plugin.yaml` | worktree |
| installed | `~/.hermes/plugins/capt-solo/{__init__.py,plugin.yaml}` | listing |
| parity | **byte-identical**, sha256 `bb410e3a12f33498092dda1f48d50feb85753e6eb2fe43f9834f4d83c57a46cd` | `cmp` + `shasum -a 256` |
| enabled | yes | `~/.hermes/config.yaml` `plugins.enabled: [biocapt, capt-solo]` |
| entrypoint | `register(ctx)` (`__init__.py:1203`) | source |
| hooks registered | `on_session_start`, `on_session_end`, `on_session_finalize`, `pre_llm_call`, `post_llm_call`, `pre_tool_call`, `post_tool_call` (`__init__.py:1221-1227`) | source |
| tool-hook semantics | **observational only** (`__init__.py:864` comment) | source |
| legacy manifest | `plugin.json` still present (older contract) | listing |

`plugin.yaml` and the current `__init__.py` are **untracked/modified in the owner
worktree** — they exist at `466f0d2` only partially. This is recorded, not
changed. The skill does not modify the plugin (owner directive).

## 6. Observed live CAPT state in `/Users/knowurknot/capt-solo` (read-only)

`capt mission status` → 6 checkpoints:

| mission id | loads? | digest | boot result |
|---|---|---|---|
| `checkpoint-governed-agent-boot-proven` | **NO** — `TypeError: MissionCheckpoint.__init__() missing 2 required positional arguments: 'project_id' and 'objective'` | n/a | legacy schema |
| `cli-test` | yes | OK | active, phase 3 |
| `mission-governed-model-execution` | yes | **MISMATCH** (`event_digest` is 64 zeros) | `BLOCKED / CHECKPOINT_INTEGRITY` |
| `mission-outer-agent-memory-continuity` | yes | OK | **GOVERNED, gate PASS** |
| `phase0-outer-agent-memory-trace` | **NO** — same TypeError | n/a | legacy schema |
| `phase2-outcome-c-contracts` | **NO** — same TypeError | n/a | legacy schema |

`capt --json agent status --workspace /Users/knowurknot/capt-solo` **without**
`--mission` crashes with the same `TypeError` — discovery iterates every id and
hits a legacy record. Verified reproducible. Recorded as a runtime limitation in
`CAPT_SKILL_CONFLICT_AUDIT.md` §4; the Agent Runner is NOT modified here.

`capt --json agent doctor` → `{"ok": true, "single_composition_root": true,
"provider": "no provider configured (set CAPT_MODEL_ENDPOINT and CAPT_MODEL_ID)"}`.

`capt doctor` → `ok: True`, 11 checks pass, `side_effects: none`,
`network: not used`, `persistence: not created`.

`capt --version` prints the argparse usage line, not a version string. Version
must be read from `capt doctor` (`package.version` check) or
`capt_solo.__version__`.

## 7. Git identity

| item | value |
|---|---|
| owner worktree | `/Users/knowurknot/capt-solo` — **MIXED PRESERVED OWNER WORKTREE**, dirty, untouched |
| owner branch | `integration/capt-v05-final-audit` |
| base SHA (verified) | `466f0d2ea6c15f1a34e8d33ca77b5f5e7c091bc8` |
| origin parity | `git rev-list --left-right --count HEAD...origin/integration/capt-v05-final-audit` → `0 0` |
| Agent Runner on origin tip | yes (`capt_solo/agent/{__init__,boot,contracts,output,runner}.py`, `model_task.py`, `runtime.py`) |
| isolated worktree | `/Users/knowurknot/capt-core-skill-worktree` @ `466f0d2`, branch `feature/hermes-capt-core-runtime-skill`, clean |
| remotes | `origin` → `knowurknottty/CAPT_core`; `preservation` → `capt-core-v05-hardening-backup` |

## 8. Repository skill convention (existing)

Tracked bundled skills already live at `capt_solo/skills/<name>/SKILL.md`
(8 skills: `capt-arch-decision capt-bootstrap capt-debug capt-knowledge-capture
capt-memory-review capt-recovery capt-session-recap capt-transaction`).

Packaging: `pyproject.toml` `[tool.setuptools.package-data] capt_solo =
["plugin/plugin.json", "skills/*/SKILL.md"]`; `MANIFEST.in` `recursive-include
capt_solo/skills SKILL.md`.

`install.sh:56-63` copies **only `SKILL.md`**, flat, into `$HERMES_CONFIG_DIR/skills/<name>/`
— no category namespace, no references/scripts/schemas, no provenance. That
installer is insufficient for a multi-file skill; a new tracked installer is
required (see `CAPT_SKILL_DECISION.md` §3).
