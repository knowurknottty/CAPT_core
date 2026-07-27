# Phase 3L — External Interface Hardening

**Branch:** integration/full-public-architecture
**Date:** 2026-07-26
**Issue:** #5
**Preceded by:** Phase 3K (commit c27506c)

## Objective
Harden the external interface: a single, stable, documented entry point over the
canonical subsystems; surface them safely via the CLI; no hidden behavior.

## Implementation
- `capt_solo/capt_facade.py` (NEW — does NOT replace the sanctioned integrator
  API `capt_solo/api.py`; I-11 respected): `CAPT` facade over all canonical
  subsystems (episodic, autobiographical, evidence, knowledge, engram, hmc,
  execution boundary, continuous learning, dream, research registry). All stores
  share ONE MemoryEngine (no hidden separate DBs). Local-first default (in-memory
  unless `db_path` given). Fails loudly on invalid use; optional capabilities
  degrade per I-09.
- `capt_cli.py`: added `canon` subcommand with actions `episodes`, `knowledge`,
  `evidence`, `autobiographical`, `engrams`, `research-health`, `self-check`.
  Dispatched via `_cmd_canon`, which uses the `CAPT` facade and surfaces errors
  as structured failures (never silent).

## Regression avoided
The pre-existing `capt_solo/api.py` (sanctioned integrator/plugin import path,
re-exporting CTPRuntime/KHSB/Lifecycle etc.) was initially overwritten by a
same-named facade module, breaking `capt_solo.plugin` imports (I-11 violation).
Detected via collection errors, the original `api.py` was restored from HEAD and
the facade moved to `capt_solo/capt_facade.py`. Plugin imports verified working
post-restore. No behavior regression.

## Tests added
`tests/test_phase3l_external_interface.py` (6):
- API facade co-locates all stores on one engine
- end-to-end flow (evidence -> verified knowledge, episode, autobiographical)
- execution boundary enforced via facade (consent default-deny)
- CLI `canon self-check` returns ok
- CLI `canon research-health` runs
- CLI `canon episodes` empty list handled

## Verification
- `pytest`: 463 passed (was 457).
- `verify_runtime.py`: 46/46 pass (unchanged).
- `capt_solo.plugin` imports verified after api.py restore.

## Result
External interface is hardened with a stable canonical facade + safe CLI surface,
and the sanctioned integrator API was preserved intact. Ready for Phase 3M
(Release verification).
