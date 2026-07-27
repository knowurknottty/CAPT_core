# BOUNDARY_AND_SECURITY_EVIDENCE.md

- **scope**: Public/private boundary enforcement (M6) + security review (M7).
- **source_commit**: `acf9159` (parent of this milestone commit)
- **milestone**: M6 + M7

## Public/private boundary (M6)
- **Public contents (verified in wheel `capt_solo-0.4.1-py3-none-any.whl`, 83 entries):**
  - Mathematics engine (`capt_solo/engines/mathematics.py`)
  - Physics engine (`capt_solo/engines/physics.py`)
  - Invention engine (`capt_solo/engines/invention.py`)
  - PULSE gateway (`capt_solo/pulse.py`, optional, disabled-by-default)
  - Memory convergence (`capt_solo/memory/types.py`, `hmc.py`, `engram.py`, `learning/dream.py`)
  - All prior CAPT_core subsystems.
- **Private exclusions (verified ABSENT from tree AND wheel):**
  - RYS implementation/datasets/checkpoints/orchestration — none present.
  - Puter KV implementation — none present.
  - Mesh-network implementation — none present.
  - Private credentials/endpoints/orchestration — none present.
  - Scan: `tests/test_release_boundary.py` walks `capt_solo/` for files/imports
    matching `rys|puter|mesh|ouroboros_private` (AST-based) and inspects the built
    wheel's namelist. Result: NONE.
- **Packaging fix:** `pyproject.toml` `packages` list was missing `capt_solo.engines`;
  added so the engines ship in the wheel. Rebuilt wheel confirms engines present.

## PULSE hardening (Decision 4)
- `capt_solo/pulse.py`: `PulseGateway` is DISABLED by default.
- Importing the module performs NO network I/O and imports NO network library
  (`urllib.request` is imported lazily, only inside an enabled `complete()` call).
- `complete()`/`chat()` raise `PulseDisabled` unless `configure(endpoint=..., enabled=True)`
  was explicitly called. No default/hidden endpoint.
- On failure, the gateway FAILS CLOSED (`PulseError`) — no silent fallback.
- No private credentials or infrastructure assumptions.

## Security review (M7)
- **No unsafe expression evaluation:** mathematics engine parses to an AST and
  walks it; AST inspection test proves no `eval`/`exec`/`compile` Call nodes.
- **Hostile payloads inert:** `__import__`, `open`, `lambda`, `object.__subclasses__`
  inputs raise MathError; sentinel-file test confirms no side effects.
- **Bounds:** parser depth (64), input length (20000), exponent magnitude (1000).
- **Schema/workspace bypass:** covered by prior `tests/test_workspace_security.py`
  (additionalProperties rejected, capability spoofing rejected).
- **Private-module leakage:** AST import scan + wheel namelist scan (M6).
- **Quarantine:** `validate_memory_record` quarantines malformed/inferred-without-
  provenance memory instead of silent storage.
- **DREAM boundary:** proposed knowledge is labeled `is_inferred` and never
  overwrites canonical memory.

## Test commands and exact results
```
python3 -m pytest tests/test_release_boundary.py -q
# 9 passed (incl. wheel private-scan)
python3 -m pytest -q
# 586 passed (full suite)
python3 -m build --wheel
# capt_solo-0.4.1-py3-none-any.whl (83 entries, 0 private matches)
python3 -c "import capt_solo.engines.mathematics..."  # clean import from wheel OK
```

## Limitations / known
- The wheel private-scan is a guard; it cannot prove a future private import won't
  be added — but CI/commit-time runs of `test_release_boundary.py` will catch it.
- PULSE network path is not exercised in tests (no real endpoint); only the
  disabled/fails-closed behavior is tested (per "no network on import" contract).
- Security review is bounded (static + negative tests), not a formal audit.

## Files changed
- `capt_solo/pulse.py` (new, safe optional gateway)
- `pyproject.toml` (added `capt_solo.engines` to packages)
- `tests/test_release_boundary.py` (extended: private-file/import scan, PULSE
  disabled/fails-closed, engine bounds, hostile payload, wheel private-scan)
