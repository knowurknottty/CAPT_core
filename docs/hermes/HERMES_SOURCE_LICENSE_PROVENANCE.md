# Hermes Source / Licence / Provenance

## Coupling

| Aspect | Value |
|---|---|
| Coupling mechanism | OS process boundary: argv in, stdout out |
| Python import of Hermes | **none** — no `import hermes` anywhere on this branch |
| Vendored Hermes code | **none** |
| Hermes as a declared dependency | **no** — `pyproject.toml` adds no dependency |
| Runtime requirement | a `hermes` executable on `PATH` (or `CAPT_HERMES_EXECUTABLE`) |
| Behaviour when absent | `HermesDriverUnavailable`; Hermes tests skip; CAPT unaffected |

`capt_runtime/drivers/hermes.py` imports only: `asyncio`, `hashlib`, `json`,
`os`, `shutil`, `subprocess`, `time`, `pathlib`, `typing` — plus
`capt_runtime.contracts` and `capt_runtime.ingestion`.

## Provenance of the external runtime

| Field | Value | Source |
|---|---|---|
| Product | Hermes Agent | `hermes --version` |
| Vendor | Nous Research | product identification |
| Version | v0.19.1 (2026.7.30) | `hermes --version` |
| Upstream commit | `dae5df22` | `hermes --version` |
| Install path | `/Users/knowurknot/.hermes/hermes-agent` | `hermes --version` |
| Install method | git clone | `hermes --version` |
| Executable | `/Users/knowurknot/.local/bin/hermes` | `shutil.which` |
| Drift | 753 commits behind upstream | `hermes --version` |

## Licence position

Because CAPT does not copy, link, vendor, or distribute any Hermes source, no
Hermes licence term propagates into CAPT_core through this integration. The
relationship is invocation of an independent executable that the operator has
installed separately — the same relationship CAPT would have with `git` or
`python`.

If a future mode vendors Hermes source or links its Python package (for example
Mode B, which requires Hermes-side middleware), this analysis must be redone
before that mode is adopted.

## Supply-chain notes

* No package was installed into the repository environment for this integration.
* `ruff` was installed into a throwaway venv at `/tmp/lintvenv` purely to run the
  lint gate; it is not a project dependency and is not referenced by any project
  file.
* The child process receives a minimized environment and no credentials. Hermes'
  own model-provider credentials come from its own configuration, outside CAPT's
  process and outside CAPT's knowledge.
