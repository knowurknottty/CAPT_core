# PHYSICS_ENGINE_EVIDENCE.md

- **scope**: Public physics engine (`capt_solo/engines/physics.py`), built on the mathematics substrate.
- **source_commit**: `535745d` (parent of this milestone commit)
- **milestone**: M3

## Supported scope (defensible, bounded)
Reuses `Quantity`/`Dimension`/`Number`/`DerivationTrace` from mathematics — no duplication of units/dimensions/uncertainty/provenance.

- Physical constants (SI): c, G, h, k_B, g, N_A, R, epsilon_0, mu_0 — as `Quantity` with dimensions.
- **Classical mechanics** (ESTABLISHED_LAW): Newton's 2nd (F=m·a), work (W=F·d), kinetic energy (½mv²), momentum (p=m·v). All dimensionally validated.
- **Thermodynamics** (MODEL/ESTABLISHED): ideal gas law (pV=nRT, classified MODEL with explicit assumptions), first law (ΔU=Q−W, ESTABLISHED_LAW).
- **Circuits** (MODEL/ESTABLISHED): Ohm's law (V=I·R, MODEL — linear resistor), electrical power (P=V·I, ESTABLISHED_LAW).
- **Waves** (ESTABLISHED_LAW): v=f·λ (linear non-dispersive medium).

## Explicit classification (honesty)
Every relation carries a `RelationClass`: ESTABLISHED_LAW / MODEL / APPROXIMATION / EMPIRICAL / HYPOTHESIS / SPECULATIVE. The engine exposes `classify(relation)` which raises `PhysicsError` for unknown relations (cannot assert classification for speculative/unimplemented physics). No SPECULATIVE relation is returned by any method.

## Dimensional validation
All inputs are dimension-checked; mismatches raise `DimensionError`. Units registered: base SI + derived (N, J, W, Pa, C, V, m/s, m/s², Hz, ohm, F). Parenthesized unit strings are avoided; paren-free exponent form used (e.g. `m^3*kg^-1*s^-2`).

## Solver traces
Each result carries a `DerivationTrace` recording rule, assumptions, prior/result expressions, and exact/approximate status.

## Intentionally unsupported (raise PhysicsError / not implemented)
- Advanced/speculative physics (relativistic, quantum field, warp, etc.) — not present.
- Relations with fewer/more than the required inputs (e.g. Ohm's law needs exactly 2 of 3).
- Unknown relation classification lookup.

## Test commands and exact results
```
python3 -m pytest tests/test_physics.py -q
# 14 passed
python3 -m pytest -q
# 564 passed (full suite, includes math 43 + physics 14 + boundary 5 + prior)
python3 architecture/validate_registry.py
# SUMMARY: 15 checks, 0 fail, 0 warn
```

## Limitations
- Bounded to classical mechanics, basic thermodynamics, elementary DC circuits, and waves.
- Ideal gas is a MODEL (point particles, negligible interactions); not valid near condensation/critical point.
- Ohm's law is a MODEL (linear resistor); non-ohmic devices not modeled.
- No numerical PDE solvers, no field theory, no relativistic corrections.
- Constants are approximate SI values (documented); not arbitrary-precision.
- Invention engine (M4) will consume these results directly rather than re-deriving.

## Files changed
- `capt_solo/engines/physics.py` (new, ~330 lines)
- `tests/test_physics.py` (new, 14 tests)
- `capt_solo/engines/mathematics.py` (added `ohm` + `F` derived-unit dimensions)
