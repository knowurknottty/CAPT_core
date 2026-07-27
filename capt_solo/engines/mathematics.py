"""CAPT Mathematics Engine — bounded, safe, defensible public mathematics.

Design constraints (owner Decision + verification requirements):
- NO `eval` / `exec` / `compile` on untrusted input. Expressions are parsed into an
  explicit AST by a recursive-descent parser, then evaluated by walking the AST.
  The implementation is verified by AST inspection (see tests) to contain no calls
  to those builtins.
- Deterministic where expected; explicit exact-vs-approximate semantics.
- Bounded computation (parser depth + input length + exponent magnitude caps);
  explicit unsupported-op errors.
- Dimensional quantities with SI base-dimension analysis.
- Provenance: derivation steps are recorded with rule + inputs.

Scope (honest): arithmetic, algebraic manipulation of expressions, symbolic
representation, equation representation, bounded linear solving, dimensional
quantities/units, numerical approximation, interval/uncertainty propagation,
validation, error reporting, derivation traces. This is NOT a universal theorem
prover; unsupported operations raise MathError.

No external math libraries required (stdlib only).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import Dict, List, Optional, Tuple

# Bounds (defensive, explicit)
MAX_PARSE_DEPTH = 64
MAX_INPUT_LEN = 20000
MAX_EXPONENT = 1000

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MathError(ValueError):
    """Raised for unsupported operations, malformed input, or invalid math."""


class DimensionError(MathError):
    """Raised when dimensional analysis rejects an operation."""


# ---------------------------------------------------------------------------
# Exact / approximate numbers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Number:
    """A numeric value with exact/approximate semantics.

    Invariants (enforced in __post_init__):
    - exactly one of `exact` (Fraction) and `approx` (float) is populated;
    - `uncertainty` is non-negative and only present with `approx`.
    - immutable (frozen dataclass).
    """
    exact: Optional[Fraction] = None
    approx: Optional[float] = None
    uncertainty: Optional[float] = None  # 1-sigma for approximate values

    def __post_init__(self) -> None:
        if self.exact is not None and self.approx is not None:
            raise MathError("Number cannot be both exact and approximate")
        if self.exact is None and self.approx is None:
            raise MathError("Number requires exactly one of exact/approx")
        if self.uncertainty is not None:
            if self.uncertainty < 0:
                raise MathError("uncertainty must be non-negative")
            if self.exact is not None:
                raise MathError("uncertainty is only valid with approximate values")

    @property
    def is_exact(self) -> bool:
        return self.approx is None and self.exact is not None

    def as_float(self) -> float:
        if self.approx is not None:
            return self.approx
        if self.exact is not None:
            return float(self.exact)
        raise MathError("number has neither exact nor approx value")

    @classmethod
    def from_int(cls, n: int) -> "Number":
        return cls(exact=Fraction(n))

    @classmethod
    def from_float(cls, x: float, uncertainty: Optional[float] = None) -> "Number":
        return cls(approx=x, uncertainty=uncertainty)

    @classmethod
    def from_fraction(cls, f: Fraction) -> "Number":
        return cls(exact=f)

    def __mul__(self, other: "Number") -> "Number":
        return _mul_num(self, other)

    def __add__(self, other: "Number") -> "Number":
        return _add_num(self, other)

    def __sub__(self, other: "Number") -> "Number":
        return _sub_num(self, other)

    def __truediv__(self, other: "Number") -> "Number":
        return _div_num(self, other)

    def __pow__(self, p: int) -> "Number":
        return _pow_num(self, p)

    def __neg__(self) -> "Number":
        if self.exact is not None:
            return Number(exact=-self.exact)
        return Number(approx=-self.as_float(), uncertainty=self.uncertainty)

    def __repr__(self) -> str:
        if self.is_exact:
            return f"Number(exact={self.exact})"
        return f"Number(approx={self.approx!r}, u={self.uncertainty!r})"


# ---------------------------------------------------------------------------
# Dimensions (SI base dimensions)
# ---------------------------------------------------------------------------
# Order: M, L, T, I, Θ, N, J  (mass, length, time, current, temp, amount, intensity)
_DIM_NAMES = ["M", "L", "T", "I", "Theta", "N", "J"]


@dataclass(frozen=True)
class Dimension:
    """A dimension vector over the 7 SI base dimensions."""
    vec: Tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0)

    def __post_init__(self) -> None:
        if len(self.vec) != 7:
            raise MathError("dimension vector must have 7 components")

    @property
    def is_dimensionless(self) -> bool:
        return all(d == 0 for d in self.vec)

    def __mul__(self, other: "Dimension") -> "Dimension":
        return Dimension(tuple(a + b for a, b in zip(self.vec, other.vec)))

    def __truediv__(self, other: "Dimension") -> "Dimension":
        return Dimension(tuple(a - b for a, b in zip(self.vec, other.vec)))

    def __pow__(self, p: int) -> "Dimension":
        if p != int(p):
            raise DimensionError("dimensional exponent must be an integer")
        return Dimension(tuple(a * int(p) for a in self.vec))

    def sqrt(self) -> "Dimension":
        """Square root of a dimension; requires even exponents."""
        if any(d % 2 != 0 for d in self.vec):
            raise DimensionError("cannot take square root of dimension with odd exponent")
        return Dimension(tuple(d // 2 for d in self.vec))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Dimension) and self.vec == other.vec

    def __repr__(self) -> str:
        parts = [f"{_DIM_NAMES[i]}^{self.vec[i]}" for i in range(7) if self.vec[i]]
        return "dim(" + "·".join(parts) if parts else "dim(1)"


# Base-unit dimensions
_DIM_OF_BASE = {
    "kg": Dimension((1, 0, 0, 0, 0, 0, 0)),
    "m": Dimension((0, 1, 0, 0, 0, 0, 0)),
    "s": Dimension((0, 0, 1, 0, 0, 0, 0)),
    "A": Dimension((0, 0, 0, 1, 0, 0, 0)),
    "K": Dimension((0, 0, 0, 0, 1, 0, 0)),
    "mol": Dimension((0, 0, 0, 0, 0, 1, 0)),
    "cd": Dimension((0, 0, 0, 0, 0, 0, 1)),
}

# Derived-unit dimensions
_DIM_OF_DERIVED = {
    "N": Dimension((1, 1, -2, 0, 0, 0, 0)),       # kg·m/s^2
    "J": Dimension((1, 2, -2, 0, 0, 0, 0)),       # kg·m^2/s^2
    "W": Dimension((1, 2, -3, 0, 0, 0, 0)),       # kg·m^2/s^3
    "Pa": Dimension((1, -1, -2, 0, 0, 0, 0)),     # N/m^2
    "C": Dimension((0, 0, 1, 1, 0, 0, 0)),        # A·s
    "V": Dimension((1, 2, -3, -1, 0, 0, 0)),      # J/(A·s)
    "m/s": Dimension((0, 1, -1, 0, 0, 0, 0)),
    "m/s^2": Dimension((0, 1, -2, 0, 0, 0, 0)),
    "Hz": Dimension((0, 0, -1, 0, 0, 0, 0)),
}

_UNIT_DIMS = {**_DIM_OF_BASE, **_DIM_OF_DERIVED}


def parse_unit(token: str) -> Dimension:
    """Parse a unit token into its dimension. Raises DimensionError if unknown."""
    token = token.strip()
    if token in ("", "1", "dimensionless", "rad"):
        return Dimension()
    if token in _UNIT_DIMS:
        return _UNIT_DIMS[token]
    if "/" in token or "*" in token:
        num, _, den = token.partition("/")
        d = Dimension()
        for part in num.replace("*", " ").split():
            d = d * parse_unit(part)
        for part in (den.replace("*", " ").split() if den else []):
            d = d / parse_unit(part)
        return d
    m = re.fullmatch(r"([A-Za-z/]+)\^?(-?\d+)", token)
    if m:
        base = parse_unit(m.group(1))
        return base ** int(m.group(2))
    raise DimensionError(f"unknown unit: {token!r}")


# ---------------------------------------------------------------------------
# Quantity (value + dimension)
# ---------------------------------------------------------------------------


@dataclass
class Quantity:
    """A physical quantity: numeric value with a dimension."""
    value: Number
    dimension: Dimension = field(default_factory=Dimension)

    def __post_init__(self) -> None:
        if not isinstance(self.value, Number):
            self.value = Number.from_int(self.value) if isinstance(self.value, int) \
                else Number.from_float(float(self.value))

    def assert_same_dim(self, other: "Quantity") -> None:
        if self.dimension != other.dimension:
            raise DimensionError(
                f"dimension mismatch: {self.dimension} vs {other.dimension}")

    def __add__(self, other: "Quantity") -> "Quantity":
        self.assert_same_dim(other)
        return Quantity(_add_num(self.value, other.value), self.dimension)

    def __sub__(self, other: "Quantity") -> "Quantity":
        self.assert_same_dim(other)
        return Quantity(_sub_num(self.value, other.value), self.dimension)

    def __mul__(self, other: "Quantity") -> "Quantity":
        return Quantity(_mul_num(self.value, other.value), self.dimension * other.dimension)

    def __truediv__(self, other: "Quantity") -> "Quantity":
        return Quantity(_div_num(self.value, other.value), self.dimension / other.dimension)

    def __pow__(self, p: int) -> "Quantity":
        return Quantity(_pow_num(self.value, p), self.dimension ** p)

    def sqrt(self) -> "Quantity":
        """Square root; transforms dimensions (requires even exponents)."""
        return Quantity(_sqrt_num(self.value), self.dimension.sqrt())

    def _require_dimensionless(self, func: str) -> None:
        if not self.dimension.is_dimensionless:
            raise DimensionError(f"{func} requires a dimensionless argument")

    def sin(self) -> "Quantity":
        self._require_dimensionless("sin")
        return Quantity(Number.from_float(math.sin(self.value.as_float())))

    def cos(self) -> "Quantity":
        self._require_dimensionless("cos")
        return Quantity(Number.from_float(math.cos(self.value.as_float())))

    def tan(self) -> "Quantity":
        self._require_dimensionless("tan")
        return Quantity(Number.from_float(math.tan(self.value.as_float())))

    def ln(self) -> "Quantity":
        self._require_dimensionless("ln")
        return Quantity(Number.from_float(math.log(self.value.as_float())))

    def exp(self) -> "Quantity":
        self._require_dimensionless("exp")
        return Quantity(Number.from_float(math.exp(self.value.as_float())))

    def abs(self) -> "Quantity":
        v = self.value
        if v.exact is not None:
            return Quantity(Number(exact=abs(v.exact)), self.dimension)
        return Quantity(Number(approx=abs(v.as_float()), uncertainty=v.uncertainty), self.dimension)

    def as_float(self) -> float:
        return self.value.as_float()


# ---------------------------------------------------------------------------
# Number arithmetic helpers (exact-aware)
# ---------------------------------------------------------------------------


def _add_num(a: Number, b: Number) -> Number:
    if a.exact is not None and b.exact is not None:
        return Number(exact=a.exact + b.exact)
    return Number(approx=a.as_float() + b.as_float(),
                  uncertainty=_combine_u(a.uncertainty, b.uncertainty, "+"))


def _sub_num(a: Number, b: Number) -> Number:
    if a.exact is not None and b.exact is not None:
        return Number(exact=a.exact - b.exact)
    return Number(approx=a.as_float() - b.as_float(),
                  uncertainty=_combine_u(a.uncertainty, b.uncertainty, "-"))


def _mul_num(a: Number, b: Number) -> Number:
    if a.exact is not None and b.exact is not None:
        return Number(exact=a.exact * b.exact)
    av, bv = a.as_float(), b.as_float()
    u = None
    if a.uncertainty is not None or b.uncertainty is not None:
        ua = a.uncertainty or 0.0
        ub = b.uncertainty or 0.0
        if av != 0 and bv != 0:
            u = abs(av * bv) * math.sqrt((ua / av) ** 2 + (ub / bv) ** 2)
    return Number(approx=av * bv, uncertainty=u)


def _div_num(a: Number, b: Number) -> Number:
    if b.as_float() == 0.0:
        raise MathError("division by zero")
    if a.exact is not None and b.exact is not None:
        try:
            return Number(exact=a.exact / b.exact)
        except ZeroDivisionError:
            raise MathError("division by zero")
    av, bv = a.as_float(), b.as_float()
    u = None
    if a.uncertainty is not None or b.uncertainty is not None:
        ua = a.uncertainty or 0.0
        ub = b.uncertainty or 0.0
        if av != 0 and bv != 0:
            u = abs(av / bv) * math.sqrt((ua / av) ** 2 + (ub / bv) ** 2)
    return Number(approx=av / bv, uncertainty=u)


def _pow_num(a: Number, p: int) -> Number:
    if abs(p) > MAX_EXPONENT:
        raise MathError(f"exponent magnitude exceeds bound ({MAX_EXPONENT})")
    if a.exact is not None:
        try:
            return Number(exact=a.exact ** p)
        except (ValueError, ZeroDivisionError):
            pass
    av = a.as_float()
    u = None
    if a.uncertainty is not None and av != 0:
        u = abs(p) * abs(av) ** (p - 1) * a.uncertainty
    return Number(approx=av ** p, uncertainty=u)


def _sqrt_num(a: Number) -> Number:
    if a.exact is not None:
        # exact sqrt only when perfect square rational
        f = a.exact
        if f >= 0 and f.denominator > 0:
            num = int(f.numerator) ** 0.5
            den = int(f.denominator) ** 0.5
            if num == int(num) and den == int(den) and den != 0:
                return Number(exact=Fraction(int(num), int(den)))
        return Number(approx=math.sqrt(a.as_float()))
    return Number(approx=math.sqrt(a.as_float()), uncertainty=a.uncertainty)


def _combine_u(ua, ub, op):
    ua = ua or 0.0
    ub = ub or 0.0
    if op == "+" or op == "-":
        return math.sqrt(ua * ua + ub * ub)
    return None


# ---------------------------------------------------------------------------
# Expression AST + safe parser (NO eval)
# ---------------------------------------------------------------------------


class Expr:
    """Base class for expression AST nodes."""


@dataclass
class Num(Expr):
    value: Number


@dataclass
class Sym(Expr):
    name: str


@dataclass
class Unary(Expr):
    op: str  # '-'
    operand: Expr


@dataclass
class Bin(Expr):
    op: str  # '+', '-', '*', '/', '^'
    left: Expr
    right: Expr


@dataclass
class Call(Expr):
    func: str
    args: List[Expr]


@dataclass
class Eq(Expr):
    left: Expr
    right: Expr


_FUNC_WHITELIST = {
    "sin", "cos", "tan", "asin", "acos", "atan",
    "exp", "log", "ln", "sqrt", "abs", "floor", "ceil", "sign",
}


class Parser:
    """Recursive-descent parser. Produces an AST; never executes anything."""
    _TOKEN_RE = re.compile(r"\s*([0-9]+(?:\.[0-9]+)?|[A-Za-z_][A-Za-z0-9_]*|==|<=|>=|!=|\*\*|[+\-*/^()=<>])")

    def __init__(self, max_depth: int = MAX_PARSE_DEPTH) -> None:
        self.max_depth = max_depth

    def parse(self, text: str) -> Expr:
        if len(text) > MAX_INPUT_LEN:
            raise MathError(f"input too long (max {MAX_INPUT_LEN} chars)")
        self.toks = self._tokenize(text)
        self.pos = 0
        e = self._parse_expr(0)
        if self.pos < len(self.toks):
            raise MathError(f"unexpected token at {self.pos}: {self.toks[self.pos]!r}")
        return e

    def _tokenize(self, text: str):
        toks = []
        i = 0
        while i < len(text):
            m = self._TOKEN_RE.match(text, i)
            if not m:
                if text[i].isspace():
                    i += 1
                    continue
                raise MathError(f"invalid character at {i}: {text[i]!r}")
            toks.append(m.group(1))
            i = m.end()
        return toks

    def _peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def _next(self):
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def _parse_expr(self, depth: int) -> Expr:
        if depth > self.max_depth:
            raise MathError("expression too deeply nested (bounded)")
        node = self._parse_add(depth + 1)
        while self._peek() in ("==", "!=", "<=", ">=", "<", ">"):
            op = self._next()
            rhs = self._parse_add(depth + 1)
            if op == "==":
                node = Eq(node, rhs)
            else:
                node = Bin(op, node, rhs)
        return node

    def _parse_add(self, depth: int) -> Expr:
        node = self._parse_mul(depth)
        while self._peek() in ("+", "-"):
            op = self._next()
            rhs = self._parse_mul(depth)
            node = Bin(op, node, rhs)
        return node

    def _parse_mul(self, depth: int) -> Expr:
        node = self._parse_unary(depth)
        while self._peek() in ("*", "/"):
            op = self._next()
            rhs = self._parse_unary(depth)
            node = Bin(op, node, rhs)
        return node

    def _parse_unary(self, depth: int) -> Expr:
        if self._peek() == "-":
            self._next()
            return Unary("-", self._parse_unary(depth))
        if self._peek() == "+":
            self._next()
            return self._parse_unary(depth)
        return self._parse_pow(depth)

    def _parse_pow(self, depth: int) -> Expr:
        node = self._parse_atom(depth)
        if self._peek() in ("^", "**"):
            self._next()
            rhs = self._parse_unary(depth)
            node = Bin("^", node, rhs)
        return node

    def _parse_atom(self, depth: int) -> Expr:
        t = self._peek()
        if t is None:
            raise MathError("unexpected end of expression")
        if t == "(":
            self._next()
            node = self._parse_expr(depth)
            if self._peek() != ")":
                raise MathError("missing closing parenthesis")
            self._next()
            return node
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", t):
            self._next()
            if "." in t:
                # Exact decimal: convert via Fraction to avoid binary float error.
                return Num(Number(exact=Fraction(t)))
            return Num(Number(exact=Fraction(t)))
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t):
            self._next()
            if self._peek() == "(":
                self._next()
                args = []
                if self._peek() != ")":
                    args.append(self._parse_expr(depth))
                    while self._peek() == ",":
                        self._next()
                        args.append(self._parse_expr(depth))
                if self._peek() != ")":
                    raise MathError("missing closing parenthesis in call")
                self._next()
                if t not in _FUNC_WHITELIST:
                    raise MathError(f"unknown function: {t!r} (not in whitelist)")
                return Call(t, args)
            return Sym(t)
        raise MathError(f"unexpected token: {t!r}")


# ---------------------------------------------------------------------------
# Evaluation (explicit AST walk; no eval)
# ---------------------------------------------------------------------------


def evaluate(expr: Expr, env: Optional[Dict[str, float]] = None) -> Number:
    """Evaluate an AST to a Number. env maps symbol names to float values."""
    env = env or {}
    if isinstance(expr, Num):
        return expr.value
    if isinstance(expr, Sym):
        if expr.name in env:
            return Number(approx=env[expr.name])
        raise MathError(f"unbound symbol: {expr.name!r}")
    if isinstance(expr, Unary):
        v = evaluate(expr.operand, env)
        return Number(approx=-v.as_float()) if v.exact is None else Number(exact=-v.exact)
    if isinstance(expr, Bin):
        l = evaluate(expr.left, env)
        r = evaluate(expr.right, env)
        if expr.op == "+":
            return _add_num(l, r)
        if expr.op == "-":
            return _sub_num(l, r)
        if expr.op == "*":
            return _mul_num(l, r)
        if expr.op == "/":
            return _div_num(l, r)
        if expr.op == "^":
            if r.exact is not None and r.exact.denominator == 1:
                p = int(r.exact)
                if abs(p) > MAX_EXPONENT:
                    raise MathError(f"exponent magnitude exceeds bound ({MAX_EXPONENT})")
                return _pow_num(l, p)
            return Number(approx=l.as_float() ** r.as_float())
        if expr.op in ("<", ">", "<=", ">="):
            lv, rv = l.as_float(), r.as_float()
            return Number(approx=float(_cmp(expr.op, lv, rv)))
        raise MathError(f"unsupported operator: {expr.op!r}")
    if isinstance(expr, Call):
        args = [evaluate(a, env).as_float() for a in expr.args]
        return Number(approx=_call_func(expr.func, args))
    if isinstance(expr, Eq):
        l = evaluate(expr.left, env).as_float()
        r = evaluate(expr.right, env).as_float()
        return Number(approx=float(abs(l - r) < 1e-12))
    raise MathError(f"cannot evaluate node: {type(expr).__name__}")


def _cmp(op, l, r) -> bool:
    return {"<": l < r, ">": l > r, "<=": l <= r, ">=": l >= r}[op]


def _call_func(func: str, args: List[float]) -> float:
    if func in ("sin", "cos", "tan", "asin", "acos", "atan", "exp", "sqrt", "abs",
                "floor", "ceil", "log", "ln", "sign"):
        if func == "ln":
            return math.log(args[0])
        if func == "log":
            return math.log(args[0]) if len(args) == 1 else math.log(args[0]) / math.log(args[1])
        if func == "sign":
            return math.copysign(1.0, args[0]) if args[0] != 0 else 0.0
        if func == "sqrt":
            return math.sqrt(args[0])
        return getattr(math, func)(*args)
    raise MathError(f"unknown function: {func!r}")


# ---------------------------------------------------------------------------
# Equation solving — structural affine analysis (no sampling)
# ---------------------------------------------------------------------------


class SolveKind(Enum):
    UNIQUE = "unique"
    NO_SOLUTION = "no_solution"
    INFINITE = "infinite"
    UNSUPPORTED = "unsupported"


@dataclass
class SolveResult:
    kind: SolveKind
    value: Optional[float] = None
    variable: Optional[str] = None

    def __repr__(self) -> str:
        if self.value is not None:
            return f"SolveResult({self.kind.value}, {self.variable}={self.value})"
        return f"SolveResult({self.kind.value}, {self.variable})"


def _contains_var(e: Expr, var: str) -> bool:
    if isinstance(e, Num):
        return False
    if isinstance(e, Sym):
        return e.name == var
    if isinstance(e, Unary):
        return _contains_var(e.operand, var)
    if isinstance(e, Bin):
        return _contains_var(e.left, var) or _contains_var(e.right, var)
    if isinstance(e, Call):
        return any(_contains_var(a, var) for a in e.args)
    if isinstance(e, Eq):
        return _contains_var(e.left, var) or _contains_var(e.right, var)
    return False


def _collect_symbols(e: Expr, acc: set) -> None:
    if isinstance(e, Num):
        return
    if isinstance(e, Sym):
        acc.add(e.name)
    elif isinstance(e, Unary):
        _collect_symbols(e.operand, acc)
    elif isinstance(e, Bin):
        _collect_symbols(e.left, acc)
        _collect_symbols(e.right, acc)
    elif isinstance(e, Call):
        for a in e.args:
            _collect_symbols(a, acc)
    elif isinstance(e, Eq):
        _collect_symbols(e.left, acc)
        _collect_symbols(e.right, acc)


def _affine(e: Expr, var: str) -> Tuple[Optional[Expr], Optional[Expr]]:
    """Return (a, b) such that e == a*var + b, or (None, None) if not affine in var."""
    if isinstance(e, Num):
        return (Num(Number.from_int(0)), e)
    if isinstance(e, Sym):
        if e.name == var:
            return (Num(Number.from_int(1)), Num(Number.from_int(0)))
        return (Num(Number.from_int(0)), e)  # other symbols treated as constants
    if isinstance(e, Unary):
        a, b = _affine(e.operand, var)
        if a is None or b is None:
            return (None, None)
        return (Unary("-", a), Unary("-", b))
    if isinstance(e, Bin):
        if e.op in ("+", "-"):
            al, bl = _affine(e.left, var)
            ar, br = _affine(e.right, var)
            if al is None or ar is None:
                return (None, None)
            if e.op == "+":
                return (Bin("+", al, ar), Bin("+", bl, br))
            return (Bin("-", al, ar), Bin("-", bl, br))
        if e.op == "*":
            al, bl = _affine(e.left, var)
            ar, br = _affine(e.right, var)
            if al is None or ar is None:
                return (None, None)
            if not _contains_var(e.left, var):
                return (Bin("*", al, e.right), Bin("*", bl, e.right))
            if not _contains_var(e.right, var):
                return (Bin("*", e.left, ar), Bin("*", e.left, br))
            return (None, None)  # both sides variable-dependent -> nonlinear
        if e.op == "/":
            al, bl = _affine(e.left, var)
            ar, br = _affine(e.right, var)
            if al is None or ar is None:
                return (None, None)
            if not _contains_var(e.right, var):
                return (Bin("/", al, e.right), Bin("/", bl, e.right))
            return (None, None)  # variable-dependent denominator -> nonlinear
        if e.op == "^":
            al, bl = _affine(e.left, var)
            ar, br = _affine(e.right, var)
            if al is None or ar is None:
                return (None, None)
            if _contains_var(e.right, var):
                return (None, None)
            try:
                p = evaluate(e.right, {}).as_float()
            except Exception:
                return (None, None)
            if p == 0:
                return (Num(Number.from_int(0)), Num(Number.from_int(1)))
            if p == 1:
                return (al, bl)
            if not _contains_var(e.left, var):
                return (Num(Number.from_int(0)), e)  # constant^const
            return (None, None)  # var^const (const != 0,1) -> nonlinear
        return (None, None)
    if isinstance(e, Call):
        if any(_contains_var(a, var) for a in e.args):
            return (None, None)
        return (Num(Number.from_int(0)), e)
    if isinstance(e, Eq):
        return (None, None)
    return (None, None)


def solve_linear(text: str, variable: str) -> SolveResult:
    """Solve a single linear equation in `variable` using structural affine analysis.

    Returns a SolveResult with kind UNIQUE (value set), NO_SOLUTION, INFINITE, or
    UNSUPPORTED (non-affine forms such as x^2, sin(x), 1/x, x*(x-1)*(x-2)).
    Other symbols are treated as parameters evaluated at 0.
    """
    expr = Parser().parse(text)
    if not isinstance(expr, Eq):
        raise MathError("solve_linear requires an equation using '=='")
    sub = Bin("-", expr.left, expr.right)
    a_expr, b_expr = _affine(sub, variable)
    if a_expr is None:
        return SolveResult(SolveKind.UNSUPPORTED, variable=variable)
    syms = set()
    _collect_symbols(sub, syms)
    env = {s: 0.0 for s in syms}
    env[variable] = 0.0
    a_val = evaluate(a_expr, env).as_float()
    b_val = evaluate(b_expr, env).as_float()
    if abs(a_val) < 1e-12:
        if abs(b_val) < 1e-12:
            return SolveResult(SolveKind.INFINITE, variable=variable)
        return SolveResult(SolveKind.NO_SOLUTION, variable=variable)
    return SolveResult(SolveKind.UNIQUE, value=-b_val / a_val, variable=variable)


# ---------------------------------------------------------------------------
# Interval / uncertainty propagation (basic, safe)
# ---------------------------------------------------------------------------


@dataclass
class Interval:
    """A closed interval [lo, hi]. Bounded arithmetic; used for uncertainty."""
    lo: float
    hi: float

    def __post_init__(self) -> None:
        if math.isnan(self.lo) or math.isnan(self.hi):
            raise MathError("interval endpoint is NaN")
        if self.lo > self.hi:
            raise MathError("interval lo > hi")

    def __add__(self, o: "Interval") -> "Interval":
        return Interval(self.lo + o.lo, self.hi + o.hi)

    def __sub__(self, o: "Interval") -> "Interval":
        return Interval(self.lo - o.hi, self.hi - o.lo)

    def __mul__(self, o: "Interval") -> "Interval":
        vals = [self.lo * o.lo, self.lo * o.hi, self.hi * o.lo, self.hi * o.hi]
        return Interval(min(vals), max(vals))

    def __truediv__(self, o: "Interval") -> "Interval":
        if o.lo <= 0 <= o.hi:
            raise MathError("division by interval containing zero")
        vals = [self.lo / o.lo, self.lo / o.hi, self.hi / o.lo, self.hi / o.hi]
        return Interval(min(vals), max(vals))

    def __pow__(self, p: int) -> "Interval":
        vals = [self.lo ** p, self.hi ** p]
        return Interval(min(vals), max(vals))

    def sin(self) -> "Interval":
        """sin over an interval. If the interval contains a critical point
        (pi/2 + k*pi) the true range includes [-1, 1]; otherwise sin is monotonic
        on the interval and endpoint evaluation is exact."""
        lo, hi = self.lo, self.hi
        k_start = int(math.floor((lo - math.pi / 2) / math.pi)) - 1
        for kk in range(k_start, k_start + 4):
            c = math.pi / 2 + kk * math.pi
            if lo <= c <= hi:
                return Interval(-1.0, 1.0)
        return Interval(math.sin(lo), math.sin(hi))

    def cos(self) -> "Interval":
        lo, hi = self.lo, self.hi
        k_start = int(math.floor(lo / math.pi)) - 1
        for kk in range(k_start, k_start + 4):
            c = kk * math.pi
            if lo <= c <= hi:
                return Interval(-1.0, 1.0)
        return Interval(math.cos(lo), math.cos(hi))


def interval_of(value: float, uncertainty: float) -> Interval:
    if uncertainty < 0:
        raise MathError("uncertainty must be non-negative")
    return Interval(value - uncertainty, value + uncertainty)


# ---------------------------------------------------------------------------
# Derivation trace (provenance)
# ---------------------------------------------------------------------------


@dataclass
class DerivationStep:
    rule: str
    expression: str
    inputs: List[str] = field(default_factory=list)
    prior: Optional[str] = None
    result: Optional[str] = None
    premises: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    provenance: Optional[str] = None
    exact: Optional[bool] = None


class DerivationTrace:
    """Records steps of a computation for provenance/auditability."""
    def __init__(self) -> None:
        self.steps: List[DerivationStep] = []

    def record(self, rule: str, expression: str, inputs: Optional[List[str]] = None,
               prior: Optional[str] = None, result: Optional[str] = None,
               premises: Optional[List[str]] = None, assumptions: Optional[List[str]] = None,
               provenance: Optional[str] = None, exact: Optional[bool] = None) -> None:
        self.steps.append(DerivationStep(
            rule, expression, inputs or [], prior, result,
            premises or [], assumptions or [], provenance, exact))

    def __repr__(self) -> str:
        return "\n".join(f"{i+1}. [{s.rule}] {s.expression}" for i, s in enumerate(self.steps))


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------


class MathematicsEngine:
    """Bounded, safe public mathematics engine."""

    def parse(self, text: str) -> Expr:
        return Parser().parse(text)

    def evaluate(self, text: str, env: Optional[Dict[str, float]] = None) -> Number:
        return evaluate(self.parse(text), env)

    def evaluate_quantity(self, value: Number, dimension: Dimension) -> Quantity:
        return Quantity(value, dimension)

    def parse_unit(self, token: str) -> Dimension:
        return parse_unit(token)

    def solve_linear(self, text: str, variable: str) -> SolveResult:
        return solve_linear(text, variable)

    def interval(self, value: float, uncertainty: float) -> Interval:
        return interval_of(value, uncertainty)

    def derivation(self) -> DerivationTrace:
        return DerivationTrace()


def quick_eval(text: str, env: Optional[Dict[str, float]] = None) -> Number:
    """Parse and evaluate an expression string safely (no eval)."""
    return MathematicsEngine().evaluate(text, env)
