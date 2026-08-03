"""Language-neutral validation table builder (ADR-0102).

Both generated validators interpret this table. One table + two identical
interpreters is what makes cross-language behavioural parity provable at
error-message granularity, rather than two independent schema readings.
"""

from __future__ import annotations

from typing import Any, Dict, List

from schema_model import SchemaModel, ref_to_name


def _field_rule(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Compile one property schema into an interpreter instruction."""
    if "$ref" in schema:
        return {"t": "ref", "ref": ref_to_name(schema["$ref"])}

    if "oneOf" in schema:
        parts = schema["oneOf"]
        non_null = [p for p in parts if p.get("type") != "null"]
        nullable = len(non_null) != len(parts)
        if len(non_null) == 1:
            inner = _field_rule(non_null[0])
            inner["nullable"] = nullable
            return inner
        return {"t": "any", "nullable": nullable}

    raw = schema.get("type")
    nullable = False
    if isinstance(raw, list):
        nullable = "null" in raw
        remaining = [t for t in raw if t != "null"]
        raw = remaining[0] if remaining else None

    rule: Dict[str, Any] = {"nullable": nullable}

    if "const" in schema:
        rule["t"] = "const"
        rule["const"] = schema["const"]
        return rule

    if "enum" in schema:
        rule["t"] = "enum"
        rule["enum"] = list(schema["enum"])
        return rule

    if raw == "array":
        rule["t"] = "array"
        rule["items"] = _field_rule(schema.get("items", {}))
        if "minItems" in schema:
            rule["minItems"] = schema["minItems"]
        if "maxItems" in schema:
            rule["maxItems"] = schema["maxItems"]
        return rule

    if raw == "string":
        rule["t"] = "string"
        for key in ("pattern", "minLength", "maxLength"):
            if key in schema:
                rule[key] = schema[key]
        return rule

    if raw == "integer":
        rule["t"] = "integer"
        for key in ("minimum", "maximum"):
            if key in schema:
                rule[key] = schema[key]
        return rule

    if raw == "number":
        rule["t"] = "number"
        return rule

    if raw == "boolean":
        rule["t"] = "boolean"
        return rule

    if raw == "object":
        rule["t"] = "object"
        return rule

    rule["t"] = "any"
    return rule


def build_spec(model: SchemaModel) -> Dict[str, Any]:
    """Produce the deterministic validation table for the whole contract set."""
    types: Dict[str, Any] = {}

    for name in sorted(model.order):
        named = model.types[name]

        if named.kind == "enum":
            types[name] = {"kind": "enum", "values": list(named.enum_values)}
            continue

        if named.kind == "union":
            variants = []
            for variant in sorted(named.variants):
                disc, const = model.discriminator_const(variant)
                variants.append({"name": variant, "const": const})
            types[name] = {
                "kind": "union",
                "discriminator": named.discriminator,
                "variants": variants,
            }
            continue

        if named.kind == "object":
            props: Dict[str, Any] = {}
            required: List[str] = []
            for f in sorted(named.fields, key=lambda x: x.name):
                props[f.name] = _field_rule(f.schema)
                if f.required:
                    required.append(f.name)
            entry: Dict[str, Any] = {
                "kind": "object",
                "properties": props,
                "required": sorted(required),
                "additionalProperties": bool(
                    named.schema.get("additionalProperties", True)
                ),
            }
            if named.cross_field_equal:
                entry["crossFieldEqual"] = [list(pair) for pair in named.cross_field_equal]
            if name in model.variant_owner:
                disc, const = model.discriminator_const(name)
                entry["variantOf"] = model.variant_owner[name]
                entry["discriminator"] = disc
                entry["discriminatorConst"] = const
            types[name] = entry
            continue

        types[name] = {"kind": "alias", "rule": _field_rule(named.schema)}

    return {
        "contractSchemaVersion": model.contract_schema_version,
        "runtimeVersion": model.runtime_version,
        "sourceDigest": model.source_digest,
        "types": types,
    }
