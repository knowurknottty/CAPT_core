"""Tests for the CAPT Mathematics Engine.

Covers: safe parsing (no eval/exec via AST inspection), exact/approx semantics,
dimensional analysis, structural-affine linear solving, interval/uncertainty
propagation, malformed input, numerical edge cases, and derivation provenance.
"""
import ast
import math
import os
from fractions import Fraction

import pytest

from capt_solo.engines.mathematics import (
    MathematicsEngine, MathError, DimensionError, Number, Quantity, Dimension,
    Interval, Parser, evaluate, parse_unit, quick_eval, SolveKind, SolveResult,
)

# Sentinel for hostile-payload test
_SENTINEL = "/tmp/capt_math_eval_sentinel"


# ---------------------------------------------------------------------------
# Security: AST inspection proves no eval/exec/compile calls in the engine
# ---------------------------------------------------------------------------


def _forbidden_call_in(module_path: str) -> list:
    tree = ast.parse(open(module_path).read())
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in ("eval", "exec", "compile"):
                bad.append(func.id)
    return bad


def test_no_eval_exec_compile_in_ast():
    import capt_solo.engines.mathematics as M
    bad = _forbidden_call_in(M.__file__)
    assert bad == [], f"forbidden builtin calls present: {bad}"


def test_hostile_payloads_inert():
    eng = MathematicsEngine()
    if os.path.exists(_SENTINEL):
        os.remove(_SENTINEL)
    payloads = [
        "__import__('os').system('touch " + _SENTINEL + "')",
        "eval('1+1')",
        "open('/tmp/file')",
        "(lambda: 1)()",
        "object.__subclasses__()",
        "__import__('os')",
    ]
    for p in payloads:
        with pytest.raises(MathError):
            eng.evaluate(p)
    # Confirm no side effect occurred
    assert not os.path.exists(_SENTINEL), "hostile payload produced a side effect!"
    if os.path.exists(_SENTINEL):
        os.remove(_SENTINEL)


# ---------------------------------------------------------------------------
# Exact arithmetic
# ---------------------------------------------------------------------------


def test_exact_thirds():
    eng = MathematicsEngine()
    r = eng.evaluate("1/3 + 1/3 + 1/3")
    assert r.is_exact
    assert r.exact == 1


def test_exact_decimal_no_binary_error():
    # 0.1 + 0.2 must equal 0.3 exactly under exact decimal semantics
    eng = MathematicsEngine()
    r = eng.evaluate("0.1 + 0.2")
    assert r.is_exact, "decimal sum should be exact via Fraction"
    assert r.exact == Fraction(3, 10)


def test_precedence():
    eng = MathematicsEngine()
    assert abs(eng.evaluate("2 + 3 * 4").as_float() - 14.0) < 1e-9
    assert abs(eng.evaluate("(2 + 3) * 4").as_float() - 20.0) < 1e-9
    assert abs(eng.evaluate("2 ^ 3 ^ 2").as_float() - 512.0) < 1e-6  # right-assoc


def test_symbol_substitution():
    eng = MathematicsEngine()
    assert abs(eng.evaluate("x * 2 + 1", {"x": 5.0}).as_float() - 11.0) < 1e-9


def test_unbound_symbol_raises():
    eng = MathematicsEngine()
    with pytest.raises(MathError):
        eng.evaluate("y + 1")


# ---------------------------------------------------------------------------
# Malformed / hostile syntax
# ---------------------------------------------------------------------------


def test_malformed_input():
    eng = MathematicsEngine()
    for bad in ["", "(", "1 +", "* 2", "2 2", "foo(", "sin", "x ** 2"]:
        with pytest.raises(MathError):
            eng.evaluate(bad)


def test_unknown_function_rejected():
    eng = MathematicsEngine()
    with pytest.raises(MathError):
        eng.evaluate("evil(2)")


def test_division_by_zero():
    eng = MathematicsEngine()
    with pytest.raises(MathError):
        eng.evaluate("1 / 0")


def test_nested_depth_bound():
    eng = MathematicsEngine()
    deep = "(" * 80 + "1" + ")" * 80
    with pytest.raises(MathError):
        eng.evaluate(deep)


def test_input_length_bound():
    eng = MathematicsEngine()
    with pytest.raises(MathError):
        eng.evaluate("1+" * 30000)


def test_exponent_bound():
    eng = MathematicsEngine()
    with pytest.raises(MathError):
        eng.evaluate("2 ^ 5000")


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------


def test_dim_add_incompatible():
    m = Quantity(Number.from_int(1), parse_unit("m"))
    m2 = Quantity(Number.from_int(2), parse_unit("m"))
    assert (m + m2).as_float() == 3.0
    s = Quantity(Number.from_int(1), parse_unit("s"))
    with pytest.raises(DimensionError):
        _ = m + s


def test_dim_velocity():
    m = Quantity(Number.from_int(3), parse_unit("m"))
    s = Quantity(Number.from_int(2), parse_unit("s"))
    assert (m / s).dimension == parse_unit("m/s")


def test_dim_force():
    kg = Quantity(Number.from_int(5), parse_unit("kg"))
    acc = Quantity(Number.from_int(4), parse_unit("m/s^2"))
    assert (kg * acc).dimension == parse_unit("N")


def test_sqrt_dimension():
    area = Quantity(Number.from_int(4), parse_unit("m^2"))
    length = area.sqrt()
    assert length.dimension == parse_unit("m")
    assert length.as_float() == 2.0


def test_sin_requires_dimensionless():
    m = Quantity(Number.from_int(1), parse_unit("m"))
    with pytest.raises(DimensionError):
        m.sin()
    dimless = Quantity(Number.from_float(math.pi / 2))
    assert abs(dimless.sin().as_float() - 1.0) < 1e-9


def test_unknown_unit():
    with pytest.raises(DimensionError):
        parse_unit("furlong")


# ---------------------------------------------------------------------------
# Solving — structural affine analysis
# ---------------------------------------------------------------------------


def test_solve_unique():
    eng = MathematicsEngine()
    r = eng.solve_linear("x + 2 == 5", "x")
    assert r.kind == SolveKind.UNIQUE
    assert abs(r.value - 3.0) < 1e-9


def test_solve_infinite():
    eng = MathematicsEngine()
    r = eng.solve_linear("2*x + 3 == 2*x + 3", "x")
    assert r.kind == SolveKind.INFINITE


def test_solve_no_solution():
    eng = MathematicsEngine()
    r = eng.solve_linear("2*x + 3 == 2*x + 4", "x")
    assert r.kind == SolveKind.NO_SOLUTION


def test_solve_quadratic_unsupported():
    eng = MathematicsEngine()
    r = eng.solve_linear("x*x == 4", "x")
    assert r.kind == SolveKind.UNSUPPORTED


def test_solve_sampling_defeating_polynomial():
    eng = MathematicsEngine()
    # x*(x-1)*(x-2) == 0 is zero at 0,1,2 but NOT affine
    r = eng.solve_linear("x*(x-1)*(x-2) == 0", "x")
    assert r.kind == SolveKind.UNSUPPORTED


def test_solve_reciprocal_unsupported():
    eng = MathematicsEngine()
    r = eng.solve_linear("1/x == 2", "x")
    assert r.kind == SolveKind.UNSUPPORTED


def test_solve_sin_unsupported():
    eng = MathematicsEngine()
    r = eng.solve_linear("sin(x) == 0", "x")
    assert r.kind == SolveKind.UNSUPPORTED


def test_solve_power_one_unsupported():
    eng = MathematicsEngine()
    r = eng.solve_linear("x**2 == 1", "x")
    assert r.kind == SolveKind.UNSUPPORTED


# ---------------------------------------------------------------------------
# Intervals
# ---------------------------------------------------------------------------


def test_interval_endpoint_order():
    with pytest.raises(MathError):
        Interval(2.0, 1.0)


def test_interval_mul_all_combos():
    a = Interval(1.9, 2.1)
    b = Interval(2.8, 3.2)
    prod = a * b
    assert abs(prod.lo - 1.9 * 2.8) < 1e-9
    assert abs(prod.hi - 2.1 * 3.2) < 1e-9


def test_interval_div_zero():
    a = Interval(1.0, 2.0)
    b = Interval(-1.0, 1.0)
    with pytest.raises(MathError):
        _ = a / b


def test_interval_sin_extrema():
    # interval spanning a critical point must report full [-1,1]
    iv = Interval(0.0, math.pi)
    s = iv.sin()
    assert s.lo == -1.0 and s.hi == 1.0
    # monotonic interval away from critical points
    iv2 = Interval(0.1, 0.5)
    s2 = iv2.sin()
    assert abs(s2.lo - math.sin(0.1)) < 1e-9
    assert abs(s2.hi - math.sin(0.5)) < 1e-9


def test_interval_nan_rejected():
    with pytest.raises(MathError):
        Interval(float("nan"), 1.0)


# ---------------------------------------------------------------------------
# Number contract
# ---------------------------------------------------------------------------


def test_number_both_exact_approx_rejected():
    with pytest.raises(MathError):
        Number(exact=Fraction(1), approx=1.0)


def test_number_neither_rejected():
    with pytest.raises(MathError):
        Number()


def test_number_negative_uncertainty_rejected():
    with pytest.raises(MathError):
        Number(approx=1.0, uncertainty=-0.1)


def test_number_uncertainty_on_exact_rejected():
    with pytest.raises(MathError):
        Number(exact=Fraction(1), uncertainty=0.1)


def test_number_immutable():
    n = Number.from_int(3)
    with pytest.raises(Exception):
        n.exact = Fraction(4)


def test_uncertainty_propagation_mul():
    a = Number.from_float(10.0, uncertainty=0.1)
    b = Number.from_float(5.0, uncertainty=0.05)
    prod = a * b
    assert prod.uncertainty is not None
    assert abs(prod.uncertainty - 50 * math.sqrt(2) / 100) < 1e-6


def test_exact_division():
    a = Number.from_int(3)
    b = Number.from_int(4)
    q = a / b
    assert q.is_exact
    assert q.exact == Fraction(3, 4)


# ---------------------------------------------------------------------------
# Derivation provenance
# ---------------------------------------------------------------------------


def test_derivation_trace():
    eng = MathematicsEngine()
    tr = eng.derivation()
    tr.record("parse", "1 + 2", prior=None, result="3", exact=True)
    tr.record("evaluate", "3", assumptions=["arithmetic"])
    assert len(tr.steps) == 2
    assert tr.steps[0].rule == "parse"
    assert tr.steps[0].exact is True


def test_equation_equality():
    eng = MathematicsEngine()
    r = eng.evaluate("2 + 2 == 4")
    assert abs(r.as_float() - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Algebraic invariants (within valid domains)
# ---------------------------------------------------------------------------


def test_commutativity_add():
    eng = MathematicsEngine()
    for a, b in [(3, 5), (1.2, 4.8), (0, 7)]:
        lhs = eng.evaluate(f"{a} + {b}").as_float()
        rhs = eng.evaluate(f"{b} + {a}").as_float()
        assert abs(lhs - rhs) < 1e-9


def test_associativity_mul():
    eng = MathematicsEngine()
    a, b, c = 2, 3, 4
    lhs = eng.evaluate(f"({a} * {b}) * {c}").as_float()
    rhs = eng.evaluate(f"{a} * ({b} * {c})").as_float()
    assert abs(lhs - rhs) < 1e-9
