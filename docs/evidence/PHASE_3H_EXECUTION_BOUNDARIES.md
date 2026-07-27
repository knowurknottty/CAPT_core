# Phase 3H — Skill Runtime, Plugin SDK, Execution Boundaries, Anti-Token Hardening

**Branch:** integration/full-public-architecture
**Date:** 2026-07-26
**Issue:** #5
**Preceded by:** Phase 3G (commit cf74312)

## Objective
Harden skill/plugin execution with explicit, auditable boundaries and
anti-token-extraction enforcement (no hidden state, no hidden network behavior,
no implicit trust, no silent fallback — security discipline from the directive).

## Existing canonical engines (preserved)
- `capt_solo/foundry/skill_foundry.py` — Skill Foundry (candidate -> build ->
  evidence -> validate -> review -> approve -> publish -> deprecate/revoke/revise).
  Preserved as-is (no silent redefinition, I-11).
- `capt_solo/plugin/__init__.py` — CaptSoloPlugin SDK + get_plugin()/tool_names().
  Preserved as-is.

## Added (canonical) — `capt_solo/execution/`
- `boundaries.py`: `ExecutionBoundary` wraps skill/plugin invocation and enforces:
  1. **Consent default-deny** — execution requires an explicit `execute` grant
     from the canonical ConsentStore (Phase 3E); denials recorded in audit trail.
  2. **Network egress default-deny** — a call may only perform network I/O if its
     declared `Capabilities.allows_network` is true AND the scope was granted the
     `network` operation (I-05 / I-09).
  3. **No silent credential access** — credentials are never passed unless an
     explicit capability grants it (default-deny).
  4. **Anti-Token-Extraction boundary** — execution outputs are scanned with the
     existing `capt_solo.memory.secrets.screen`; outputs containing token-
     equivalent / secret content are REFUSED at the boundary (returned as
     `[REDACTED ...]`), never propagated raw (I-05 privacy-preserving defaults).
  5. **Bounded failure** — execution errors are caught; the internal error type
     is reported but internals are not leaked (I-07).
- `Capabilities` dataclass (declared, default-deny) and `BoundaryResult` /
  `BoundaryViolation` enums. `capability_from_dict` for deserialization.
- `__init__.py`: convergence package re-exporting the boundary contract.

The boundary enforces the *contract* edges the architecture requires; OS-level
sandbox isolation is explicitly out of scope for CAPT_core (documented, not
silently omitted).

## Tests added
`tests/test_phase3h_execution_boundaries.py` (8):
- consent default-deny
- consent grant allows
- network default-deny (declared but not granted)
- network granted allows
- token-leak refused + redacted
- safe output passes
- execution error bounded (no internal leak)
- capability_from_dict

## Verification
- `pytest`: 438 passed (was 430).
- `verify_runtime.py`: 46/46 pass (unchanged).

## Result
Skill/plugin execution now has explicit, tested, auditable boundaries with
anti-token-extraction enforcement. Ready for Phase 3I (HMC / ENGRAM / DREAM
canonicalization).
