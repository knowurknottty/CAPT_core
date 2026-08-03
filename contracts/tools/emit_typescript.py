"""TypeScript emitter for the CAPT contract generator (ADR-0102).

Consumes the same SchemaModel as emit_python.py.
Target: ES2022, `tsc --strict` clean.
"""

from __future__ import annotations

from typing import Any, Dict, List

from schema_model import SchemaModel, ref_to_name

TS_SCALARS = {"string": "string", "integer": "number", "boolean": "boolean", "number": "number"}


def ts_type(schema: Dict[str, Any]) -> str:
    if "$ref" in schema:
        return ref_to_name(schema["$ref"])
    if "oneOf" in schema:
        parts = schema["oneOf"]
        non_null = [p for p in parts if p.get("type") != "null"]
        has_null = len(non_null) != len(parts)
        inner = ts_type(non_null[0]) if len(non_null) == 1 else "unknown"
        return inner + " | null" if has_null else inner
    raw = schema.get("type")
    if isinstance(raw, list):
        non_null = [t for t in raw if t != "null"]
        base = TS_SCALARS.get(non_null[0], "unknown") if non_null else "unknown"
        return base + " | null" if "null" in raw else base
    if raw == "array":
        inner = ts_type(schema.get("items", {}))
        wrapped = "(%s)" % inner if "|" in inner else inner
        return "readonly %s[]" % wrapped
    if raw == "object":
        return "Readonly<Record<string, unknown>>"
    if raw == "string" and "const" in schema:
        return '"%s"' % schema["const"]
    return TS_SCALARS.get(raw or "", "unknown")


def emit_types(model: SchemaModel) -> str:
    out: List[str] = []
    out.append('export const CONTRACT_SCHEMA_VERSION = "%s" as const;' % model.contract_schema_version)
    out.append('export const RUNTIME_VERSION = "%s" as const;' % model.runtime_version)

    for name in model.emitted_order():
        named = model.types[name]
        out.append("")
        if named.description:
            out.append("/** %s */" % named.description.replace("*/", "* /"))

        if named.kind == "enum":
            members = " | ".join('"%s"' % v for v in named.enum_values)
            out.append("export type %s = %s;" % (name, members))
            out.append("export const %sValues = [" % name)
            for value in named.enum_values:
                out.append('  "%s",' % value)
            out.append("] as const;")
        elif named.kind == "union":
            out.append("/** Discriminated on `%s`. */" % named.discriminator)
            out.append("export type %s =" % name)
            for i, variant in enumerate(named.variants):
                suffix = ";" if i == len(named.variants) - 1 else ""
                out.append("  | %s%s" % (variant, suffix))
        elif named.kind == "object":
            out.append("export interface %s {" % name)
            required = [f for f in named.fields if f.required]
            optional = [f for f in named.fields if not f.required]
            for f in required:
                out.append("  readonly %s: %s;" % (f.name, ts_type(f.schema)))
            for f in optional:
                out.append("  readonly %s?: %s;" % (f.name, ts_type(f.schema)))
            out.append("}")
        else:
            out.append("export type %s = %s;" % (name, ts_type(named.schema)))

    return "\n".join(out).rstrip() + "\n"


def emit_spec(model: SchemaModel, spec_json: str) -> str:
    out: List[str] = []
    out.append("// Canonical validation table derived from contracts/schema/.")
    out.append("// The Python binding embeds a byte-identical string; parity is tested.")
    out.append("const SPEC_JSON = %s;" % _ts_string(spec_json))
    out.append("")
    out.append("export const SPEC = JSON.parse(SPEC_JSON) as {")
    out.append("  contractSchemaVersion: string;")
    out.append("  runtimeVersion: string;")
    out.append("  sourceDigest: string;")
    out.append("  types: Record<string, unknown>;")
    out.append("};")
    out.append("")
    out.append("export { SPEC_JSON };")
    return "\n".join(out) + "\n"


def _ts_string(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return '"%s"' % escaped
