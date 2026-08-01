# CAPT Core Runtime — Diagnostics

## Scripts

| Script | Purpose |
|---|---|
| `scripts/capt-select-python.sh` | Single source of truth for interpreter selection |
| `scripts/capt-environment-report.sh` | CAPT identity record (read-only) |
| `scripts/capt-doctor.sh` | 18 diagnostic checks (PASS/WARN/FAIL/NOT_PROVEN) |
| `scripts/capt-fresh-boot.sh` | Boot a mission, emit schema-valid report |
| `scripts/capt-checkpoint.sh` | Write checkpoint + verify reload |
| `scripts/capt-resume-check.sh` | Fresh-process resume + continuity receipt |

## Interpreter selection (deterministic)

Precedence (first match wins, each validated as existing + executable):
1. `$CAPT_ACCEPT_PY` (explicit operator override)
2. `$WS/.venv/bin/python` (project-local venv)
3. `python3` from PATH
4. `python` from PATH
5. deterministic dependency failure (no silent fallback)

The selected interpreter is recorded in every report under `interpreter`:
- `executable`, `selection_source`, `version`, `prefix`
- `disagrees_with_capt_console_script` (yes/no)
- `capt_solo_module`, `capt_solo_version`, `editable_location`

## Doctor check categories

python, virtualenv, capt.executable, package.source, package.cwd_shadow,
checkout.identity, runtime.doctor, capt.home, mission.store, mission.schema,
checkpoint.digest, memory.store, session.store, composition.root,
plugin.installed, contextpack, memoryusegate, boot.recovery, ctp.journal,
khsb.events, claimguard, session.risk, hermes.tool_auth.

"Available" is never reported as "operational". `claimguard` is
`NOT_PROVEN` (importable ≠ wired). `hermes.tool_auth` is always
`NOT_PROVEN` (observational).

## Common failure readings

- `FAIL capt.executable [CAPT_NOT_FOUND]` → `capt` not on PATH; set CAPT_ACCEPT_PY
  and ensure its bin dir is on PATH.
- `FAIL checkout.identity [WRONG_CHECKOUT]` → imported capt_solo resolves outside
  the resolved source root; check CAPT_SOLO_REPO / editable location.
- `WARN package.cwd_shadow [CWD_MODULE_SHADOW]` → a local capt_solo/ shadows the
  CWD import; the CLI itself is unaffected (it uses isolated resolution).
- `FAIL python [WRONG_PYTHON]` → selected interpreter is < 3.10.
