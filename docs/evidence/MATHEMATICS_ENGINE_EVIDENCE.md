# MATHEMATICS_ENGINE_EVIDENCE.md

- **scope**: Public deterministic mathematics engine (`capt_solo/engines/mathematics.py`).
- **source_commit**: `27ce5fc` (parent of this milestone commit)
- **milestone**: M2 (owner priority #1)

## Supported scope (defensible)
- Safe recursive-descent parser → explicit AST (NO `eval`/`exec`/`compile`; verified by AST inspection in tests).
- Exact arithmetic via `fractions.Fraction` (e.g. `1/3 + 1/3 + 1/3 == 1`; `0.1 + 0.2 == 0.3` exactly).
- Approximate arithmetic with 1-sigma uncertainty propagation (multiplicative/divisive).
- Unary `-`, binary `+ - * / ^` (right-associative), function whitelist: sin cos tan asin acos atan exp log ln sqrt abs floor ceil sign.
- Dimensional quantities with 7 SI base dimensions (M,L,T,I,Θ,N,J); unit parsing for base + derived (N,J,W,Pa,C,V,m/s,m/s²,Hz) and compound `kg*m/s^2`.
- Quantity operations: add/sub (same dim), mul/div (dim combine), `sqrt()` (dim halving, requires even exponents), dimensionless-guarded sin/cos/tan/ln/exp, abs (dim-preserving).
- Structural-affine linear equation solving returning UNIQUE / NO_SOLUTION / INFINITE / UNSUPPORTED (no sampling; recursive affine analyzer).
- Intervals [lo,hi] with endpoint-ordered arithmetic, division-by-zero-in-interval rejection, NaN rejection, and extrema-safe `sin`/`cos` (reports full [-1,1] when a critical point lies inside the interval).
- Derivation provenance records (rule, prior, result, premises, assumptions, provenance, exact flag).

## Intentionally unsupported (raise MathError)
- `eval`/`exec`/`compile` on input; Python payloads (`__import__`, `open`, lambdas, `object.__subclasses__`).
- Non-affine equations: `x^2`, `x*(x-1)*(x-2)`, `1/x`, `sin(x)`, `x**2`.
- Dimensional mismatch in add/sub; non-dimensionless argument to sin/cos/tan/ln/exp.
- Unknown units/functions/identifiers; malformed syntax; unbounded nesting/length/exponent.
- Celsius/Fahrenheit affine arithmetic (Kelvin-only, explicit limitation).

## Security model
- Untrusted input is parsed to an AST; evaluation walks the AST with explicit ops.
- AST inspection test (`test_no_eval_exec_compile_in_ast`) asserts no `eval`/`exec`/`compile` Call nodes exist in the module.
- Hostile-payload test asserts no side effects (sentinel file never created).
- Bounds: MAX_PARSE_DEPTH=64, MAX_INPUT_LEN=20000, MAX_EXPONENT=1000.

## Exact/approximate semantics
- `Number` is a frozen dataclass; exactly one of `exact`(Fraction) / `approx`(float) populated; `uncertainty` only with `approx` and non-negative.
- Decimal literals parsed via `Fraction` to avoid binary float error.
- Transition to approximation is explicit (irrational results, function calls).

## Unit behavior
- Compatible add/sub enforced; mul/div combine dimensions; `sqrt` halves exponents (even-only); unknown unit → DimensionError.

## Solver limits
- Single variable, single equation, affine only. Other symbols treated as parameters at 0. Outcomes: unique value, no solution, infinite, or unsupported (non-affine).

## Test commands and exact results
```
python3 -m pytest tests/test_mathematics.py -q
# 43 passed
python3 -m pytest -q
# 550 passed (full suite, includes math + boundary)
python3 architecture/validate_registry.py
# SUMMARY: 15 checks, 0 fail, 0 warn
python3 capt_cli.py workspace validate
# ok: True
```

## Limitations
- Not a symbolic algebra system or theorem prover; no simplification beyond evaluation.
- Intervals use endpoint arithmetic; non-monotonic functions handled only for sin/cos extrema (other non-monotonic functions over intervals are not auto-widened — documented).
- Uncertainty propagation is first-order (independent errors); correlated errors not modeled.
- No unit conversion between incompatible scales (e.g. no automatic m↔ft); only dimensional combination.
- Physics/invention layers build on this substrate (M3/M4), not duplicated here.

## Files changed
- `capt_solo/engines/__init__.py` (new package marker)
- `capt_solo/engines/mathematics.py` (new, ~680 lines)
- `tests/test_mathematics.py` (new, 43 tests)
- `CHECKPOINT.md`, `CURRENT_STATE.md` (state refresh)
