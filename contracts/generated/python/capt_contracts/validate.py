# DO NOT EDIT. This file is GENERATED from contracts/schema/.
#
# generator:      contracts/tools/generate.py
# regenerate:     python3 contracts/tools/generate.py
# drift check:    python3 contracts/tools/check_drift.py
# schema version: 1.0.0
# source digest:  sha256:e84dfdf1eea315a6c9261b3e8ab127caae6ed4b5ac45ee888f5baf5c7173b871
#
# The JSON Schema source is normative (ADR-0101). Edits made here are
# erased on the next generation and will fail the CI drift check.

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .spec import SPEC

_TYPES: Dict[str, Any] = SPEC["types"]


class ValidationFailure(Exception):
    """Raised by require_valid when a payload does not satisfy its contract."""

    def __init__(self, type_name: str, errors: List[str]) -> None:
        Exception.__init__(
            self, "%s: %s" % (type_name, "; ".join(errors)) if errors else type_name
        )
        self.type_name = type_name
        self.errors = errors


def _err(out: List[str], path: str, message: str) -> None:
    out.append("%s: %s" % (path or "$", message))


def _repr(value: Any) -> str:
    """JSON representation, so Python and TypeScript emit identical messages.

    Python's %r would render strings with single quotes and None as 'None',
    diverging from the TypeScript validator. Message text is part of the
    cross-language contract and is asserted by the parity fixtures.
    """
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _matches(pattern: str, value: str) -> bool:
    import re

    # Python's `$` also matches immediately before a trailing newline, while
    # JavaScript's `$` (no `m` flag) means end-of-string. The shared spec holds
    # ONE pattern string, so Python normalizes at match time to give the two
    # languages identical semantics. Tested by the cross-language parity suite.
    normalized = pattern[:-1] + "\\Z" if pattern.endswith("$") and not pattern.endswith("\\$") else pattern
    return re.search(normalized, value) is not None


def _check_rule(rule: Dict[str, Any], value: Any, path: str, out: List[str]) -> None:
    kind = rule.get("t")
    if value is None:
        if not rule.get("nullable", False):
            _err(out, path, "must not be null")
        return

    if kind == "ref":
        _check_type(rule["ref"], value, path, out)
        return

    if kind == "const":
        if value != rule["const"]:
            _err(out, path, "must equal %s" % _repr(rule["const"]))
        return

    if kind == "enum":
        if value not in rule["enum"]:
            _err(out, path, "must be one of %s" % ",".join(map(str, rule["enum"])))
        return

    if kind == "string":
        if not isinstance(value, str):
            _err(out, path, "must be a string")
            return
        if "minLength" in rule and len(value) < rule["minLength"]:
            _err(out, path, "shorter than minLength %d" % rule["minLength"])
        if "maxLength" in rule and len(value) > rule["maxLength"]:
            _err(out, path, "longer than maxLength %d" % rule["maxLength"])
        if "pattern" in rule and not _matches(rule["pattern"], value):
            _err(out, path, "does not match pattern %s" % rule["pattern"])
        return

    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            _err(out, path, "must be an integer")
            return
        if "minimum" in rule and value < rule["minimum"]:
            _err(out, path, "less than minimum %d" % rule["minimum"])
        if "maximum" in rule and value > rule["maximum"]:
            _err(out, path, "greater than maximum %d" % rule["maximum"])
        return

    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _err(out, path, "must be a number")
        return

    if kind == "boolean":
        if not isinstance(value, bool):
            _err(out, path, "must be a boolean")
        return

    if kind == "array":
        if not isinstance(value, list):
            _err(out, path, "must be an array")
            return
        if "minItems" in rule and len(value) < rule["minItems"]:
            _err(out, path, "fewer than minItems %d" % rule["minItems"])
        if "maxItems" in rule and len(value) > rule["maxItems"]:
            _err(out, path, "more than maxItems %d" % rule["maxItems"])
        for i, item in enumerate(value):
            _check_rule(rule["items"], item, "%s[%d]" % (path, i), out)
        return

    if kind == "object":
        if not isinstance(value, dict):
            _err(out, path, "must be an object")
        return

    return


def _resolve_path(value: Any, dotted: str) -> Any:
    node = value
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _check_type(type_name: str, value: Any, path: str, out: List[str]) -> None:
    entry = _TYPES.get(type_name)
    if entry is None:
        _err(out, path, "unknown contract type %s" % type_name)
        return

    kind = entry["kind"]

    if kind == "enum":
        if value not in entry["values"]:
            _err(out, path, "must be one of %s" % ",".join(entry["values"]))
        return

    if kind == "alias":
        _check_rule(entry["rule"], value, path, out)
        return

    if kind == "union":
        if not isinstance(value, dict):
            _err(out, path, "must be an object")
            return
        disc = entry["discriminator"]
        actual = value.get(disc)
        for variant in entry["variants"]:
            if variant["const"] == actual:
                _check_type(variant["name"], value, path, out)
                return
        allowed = ",".join(v["const"] for v in entry["variants"])
        _err(out, path, "invalid discriminant %s=%s; expected one of %s" % (disc, _repr(actual), allowed))
        return

    if not isinstance(value, dict):
        _err(out, path, "must be an object")
        return

    for name in entry["required"]:
        if name not in value:
            _err(out, "%s.%s" % (path, name) if path else name, "is required")

    if not entry.get("additionalProperties", True):
        for name in sorted(value.keys()):
            if name not in entry["properties"]:
                _err(out, "%s.%s" % (path, name) if path else name, "is not permitted")

    for name in sorted(entry["properties"].keys()):
        if name in value:
            child = "%s.%s" % (path, name) if path else name
            _check_rule(entry["properties"][name], value[name], child, out)

    for pair in entry.get("crossFieldEqual", []):
        left = _resolve_path(value, pair[0])
        right = _resolve_path(value, pair[1])
        if left != right:
            _err(out, path, "%s must equal %s" % (pair[0], pair[1]))


def validate(type_name: str, value: Any) -> List[str]:
    """Return a sorted list of 'path: message' errors. Empty means valid."""
    out: List[str] = []
    _check_type(type_name, value, "", out)
    return sorted(out)


def is_valid(type_name: str, value: Any) -> bool:
    return not validate(type_name, value)


def require_valid(type_name: str, value: Any) -> Any:
    errors = validate(type_name, value)
    if errors:
        raise ValidationFailure(type_name, errors)
    return value


def known_types() -> List[str]:
    return sorted(_TYPES.keys())
