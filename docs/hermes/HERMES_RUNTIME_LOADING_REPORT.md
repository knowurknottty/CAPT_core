# Hermes Runtime Loading Report

Verified live, not carried forward from the prior session's claims.

## Executable and version

| Field | Value | How obtained |
|---|---|---|
| Executable | `/Users/knowurknot/.local/bin/hermes` | `shutil.which` via `resolve_hermes_executable()` |
| Version | Hermes Agent v0.19.1 (2026.7.30) | `hermes --version`, exit 0 |
| Upstream commit | `dae5df22` | `hermes --version` |
| Install directory | `/Users/knowurknot/.hermes/hermes-agent` | `hermes --version` |
| Install method | git | `hermes --version` |
| Python | 3.11.15 | `hermes --version` |
| OpenAI SDK | 2.24.0 | `hermes --version` |
| Update status | 753 commits behind upstream | `hermes --version` |
| Model preset | `@preset/inversiolabs-hy3` (openrouter) | `~/.hermes/config.yaml`, agent.log |
| Config path | `/Users/knowurknot/.hermes/config.yaml` | filesystem |
| Plugin discovery | 64 found, 49 enabled | `~/.hermes/logs/agent.log` |

The three values supplied in the mission brief (v0.19.1, `dae5df22`,
`@preset/inversiolabs-hy3`) were **confirmed independently**, not assumed.

## Invocation path used by the driver

```
hermes -z "<prompt derived solely from ContextSlice>" \
       -t terminal --safe-mode --pass-session-id
```

* `-z` — headless single-turn, no interactive REPL.
* `-t terminal` — restricts the toolset to the single tool the read-only task
  needs. Web, browser, file-write, and delegation toolsets are not loaded.
* `--safe-mode` — sets `ignore_rules` and `ignore_user_config`, so the user's
  `~/.hermes/config.yaml` rules and project rule files do not influence the
  governed run.
* Launched with `shell=False` and an explicit argv list — no shell interpolation.
* `cwd` pinned to the target repository.
* `start_new_session=True` so the whole process group can be killed on budget
  overrun.
* Environment restricted to an allow-list; any variable whose name contains
  `TOKEN`, `SECRET`, `PASSWORD`, `APIKEY`, `API_KEY`, `PRIVATE_KEY`, `CREDENTIAL`,
  `SESSION_KEY`, or `AUTH` is dropped. Observed env keys in the proven run:
  `CAPT_DRIVER_RUN_ID, HOME, LANG, LC_ALL, PATH, SHELL, TMPDIR, USER`.

## Real turn evidence

| Field | Value |
|---|---|
| PID | 51294 |
| Exit code | 0 |
| Elapsed | 11.80 s |
| stderr | empty |
| Output | non-empty analysis + one `OBSERVATION:` line |

A separate earlier probe (PID 49474, exit 0, 23.10 s) produced an equivalent
result, confirming reproducibility.

## The `capt-solo` Hermes plugin (pre-existing, NOT used)

`~/.hermes/plugins/capt-solo/` is a user-scope plugin listed as `enabled` by
`hermes plugins list`. It resolves a CAPT repository via `CAPT_SOLO_REPO`.

Observed behaviour:

* Against `CAPT_SOLO_REPO=/Users/knowurknot/CAPT_core` — **fails to load**.
* Against `CAPT_SOLO_REPO=/Users/knowurknot/capt-solo` — loads.
* `hermes tools | grep -i capt` returns **zero** tools in a default session.

Therefore the plugin registers no tools against the authoritative repository and
played no part in this integration. It is not a dependency of the Hermes
ExecutionDriver, which requires only the `hermes` executable on `PATH`.

## Provenance and licence

| Item | Value |
|---|---|
| Hermes source | `/Users/knowurknot/.hermes/hermes-agent` (git clone) |
| Upstream | Nous Research — Hermes Agent |
| Linkage | **none** — CAPT does not import, vendor, or link Hermes code |
| Coupling | OS process boundary + argv + stdout only |
| Licence impact | no Hermes source is copied into or distributed with CAPT |

`capt_runtime/drivers/hermes.py` imports only the Python standard library and
`capt_runtime` internals. There is no `import hermes` anywhere in this branch.
