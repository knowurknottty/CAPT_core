# Phase 3K — Research Module Adapters

**Branch:** integration/full-public-architecture
**Date:** 2026-07-26
**Issue:** #5
**Preceded by:** Phase 3J (commit ac78f9e)

## Objective
Connect research-grade modules to the canonical architecture through stable
adapters that degrade gracefully when optional (I-09). External research modules
are NOT copied into CAPT_core (licensing gate [L]); they register via the adapter
registry when present, or are represented by a local fallback.

## Implementation — `capt_solo/research/`
- `adapter.py`: canonical research adapter contract.
  - `ResearchAdapter` (base): name, version, capabilities(), health(), run().
  - `LocalFallbackAdapter`: default no-op used when an optional research module is
    absent — returns DEGRADED result without raising (I-09 satisfied).
  - `ResearchAdapterRegistry`: register/get/health/run. `run()` returns a
    `LocalFallbackAdapter` result when the module is unregistered (graceful
    degradation), and catches adapter exceptions into a bounded `ResearchResult`
    (I-07) instead of crashing the runtime.
  - `ResearchResult` dataclass (adapter, ok, output, error, provenance).
  - `DEFAULT_REGISTRY` module-level convergence point.
- `__init__.py`: re-exports the contract.

## Tests added
`tests/test_phase3k_research_adapters.py` (6):
- register + get
- run active adapter
- missing module -> graceful local fallback (I-09)
- adapter failure bounded (no runtime crash)
- health status (active vs degraded)
- default registry exists

## Verification
- `pytest`: 457 passed (was 451).
- `verify_runtime.py`: 46/46 pass (unchanged).

## Result
Research modules have a canonical, tested adapter boundary that degrades
gracefully. Ready for Phase 3L (External interface hardening).
