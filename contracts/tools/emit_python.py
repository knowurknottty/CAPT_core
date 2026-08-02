"""Python emitter for the CAPT contract generator (ADR-0102).

Consumes the shared SchemaModel produced by schema_model.py. The TypeScript
emitter consumes the same model, so a schema construct cannot be interpreted
differently per language.

Target syntax level: Python 3.8. No `X | Y` runtime unions, no `match`.
Field names stay camelCase, identical to the schema, so JSON round-trips need
no name-mapping layer that could drift between languages.
"""

from __future__ import annotations

from typing import Any, Dict, List

from schema_model import SchemaModel, ref_to_name

PY_SCALARS = {"string": "str", "integer": "int", "boolean": "bool", "number": "float"}


def py_type(schema: Dict[str, Any]) -> str:
    """Map one property schema to a Python annotation."""
    if "$ref" in schema:
        return ref_to_name(schema["$ref"])
    if "oneOf" in schema:
        parts = schema["oneOf"]
        non_null = [p for p in parts if p.get("type") != "null"]
        has_null = len(non_null) != len(parts)
        inner = py_type(non_null[0]) if len(non_null) == 1 else "Any"
        return "Optional[%s]" % inner if has_null else inner
    raw = schema.get("type")
    if isinstance(raw, list):
        non_null = [t for t in raw if t != "null"]
        base = PY_SCALARS.get(non_null[0], "Any") if non_null else "Any"
        return "Optional[%s]" % base if "null" in raw else base
    if raw == "array":
        return "List[%s]" % py_type(schema.get("items", {}))
    if raw == "object":
        return "Dict[str, Any]"
    if raw == "string" and "const" in schema:
        return 'Literal["%s"]' % schema["const"]
    return PY_SCALARS.get(raw or "", "Any")


def emit_types(model: SchemaModel) -> str:
    out: List[str] = []
    out.append("from __future__ import annotations")
    out.append("")
    out.append("from dataclasses import dataclass, field")
    out.append("from enum import Enum")
    out.append("from typing import Any, Dict, List, Optional, Union")
    out.append("")
    out.append("try:  # Python 3.8+")
    out.append("    from typing import Literal")
    out.append("except ImportError:  # pragma: no cover")
    out.append("    from typing_extensions import Literal  # type: ignore")
    out.append("")
    out.append('CONTRACT_SCHEMA_VERSION = "%s"' % model.contract_schema_version)
    out.append('RUNTIME_VERSION = "%s"' % model.runtime_version)
    out.append("")

    for name in model.topological_order():
        named = model.types[name]
        out.append("")
        if named.kind == "enum":
            out.append("class %s(str, Enum):" % name)
            if named.description:
                out.append('    """%s"""' % named.description.replace('"', "'"))
                out.append("")
            for value in named.enum_values:
                out.append('    %s = "%s"' % (_enum_member(value), value))
            out.append("")
        elif named.kind == "union":
            variants = " ,".join(named.variants)
            out.append("# discriminated on %r" % named.discriminator)
            out.append("%s = Union[%s]" % (name, variants.replace(" ,", ", ")))
            out.append("")
        elif named.kind == "object":
            out.append("@dataclass(frozen=True)")
            out.append("class %s(object):" % name)
            if named.description:
                out.append('    """%s"""' % named.description.replace('"', "'"))
                out.append("")
            required = [f for f in named.fields if f.required]
            optional = [f for f in named.fields if not f.required]
            if not required and not optional:
                out.append("    pass")
            for f in required:
                out.append("    %s: %s" % (f.name, py_type(f.schema)))
            for f in optional:
                annotation = py_type(f.schema)
                if not annotation.startswith("Optional[") and not annotation.startswith("List["):
                    annotation = "Optional[%s]" % annotation
                default = (
                    "field(default_factory=list)"
                    if annotation.startswith("List[")
                    else "None"
                )
                out.append("    %s: %s = %s" % (f.name, annotation, default))
            out.append("")
        else:
            out.append("%s = %s" % (name, py_type(named.schema)))
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def _enum_member(value: str) -> str:
    member = "".join(ch if ch.isalnum() else "_" for ch in value).upper()
    if member and member[0].isdigit():
        member = "V" + member
    return member


def emit_spec(model: SchemaModel, spec_json: str) -> str:
    out: List[str] = []
    out.append("from __future__ import annotations")
    out.append("")
    out.append("import json")
    out.append("from typing import Any, Dict")
    out.append("")
    out.append(
        "# Canonical validation table derived from contracts/schema/. The"
    )
    out.append(
        "# TypeScript binding embeds a byte-identical string; parity is tested."
    )
    out.append("SPEC_JSON = %s" % _py_string(spec_json))
    out.append("")
    out.append("SPEC: Dict[str, Any] = json.loads(SPEC_JSON)")
    out.append("")
    out.append('CONTRACT_SCHEMA_VERSION = "%s"' % model.contract_schema_version)
    return "\n".join(out) + "\n"


def _py_string(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return '"%s"' % escaped
