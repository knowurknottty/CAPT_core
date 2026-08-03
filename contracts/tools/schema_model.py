"""Shared schema loading and canonicalization for the CAPT contract toolchain.

This module is the single interpreter of the JSON Schema subset CAPT uses
(ADR-0102). Both the Python emitter and the TypeScript emitter consume the
model produced here, so a schema construct cannot be interpreted differently
per language by construction.

Unsupported keywords raise UnsupportedSchemaError rather than being silently
ignored: a schema author must never believe a constraint is enforced when it
is not.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"

# Keywords the generator understands. Anything else in a subschema is an error.
SUPPORTED_KEYWORDS = frozenset(
    {
        "$schema",
        "$id",
        "$ref",
        "$defs",
        "title",
        "description",
        "type",
        "const",
        "enum",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "minItems",
        "maxItems",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
        "oneOf",
        # x- prefixed vendor extensions are allowed and handled explicitly.
    }
)

VENDOR_PREFIX = "x-"


class UnsupportedSchemaError(Exception):
    """A schema used a construct the generator does not implement."""


class SchemaModelError(Exception):
    """The schema set is internally inconsistent."""


def canonical_json(value: Any) -> str:
    """Deterministic JSON: sorted keys, no incidental whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_of(value: Any) -> str:
    return "sha256:" + sha256_hex(canonical_json(value))


def load_index() -> Dict[str, Any]:
    with (SCHEMA_DIR / "index.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_schemas() -> Dict[str, Dict[str, Any]]:
    """Load every schema file named in index.json, in index order."""
    index = load_index()
    schemas: Dict[str, Dict[str, Any]] = {}
    for name in index["files"]:
        path = SCHEMA_DIR / name
        if not path.exists():
            raise SchemaModelError("index.json references missing file: " + name)
        with path.open("r", encoding="utf-8") as handle:
            schemas[name] = json.load(handle)
    # Guard against a schema file that exists but is not indexed.
    on_disk = sorted(p.name for p in SCHEMA_DIR.glob("*.schema.json"))
    indexed = sorted(index["files"])
    if on_disk != indexed:
        raise SchemaModelError(
            "schema directory and index.json disagree: on_disk=%r indexed=%r"
            % (on_disk, indexed)
        )
    return schemas


def source_digest() -> str:
    """Digest over the canonicalized schema set plus the index.

    Content only: no timestamps, no paths, no hostnames. Two runs on different
    machines produce the same digest for the same schema content (ADR-0102).
    """
    schemas = load_schemas()
    index = load_index()
    material = {
        "index": {
            "contractSchemaVersion": index["contractSchemaVersion"],
            "runtimeVersion": index["runtimeVersion"],
            "files": index["files"],
        },
        "schemas": {name: schemas[name] for name in sorted(schemas)},
    }
    return digest_of(material)


def check_keywords(node: Any, where: str) -> None:
    """Recursively reject unsupported JSON Schema keywords."""
    if isinstance(node, dict):
        for key in node:
            if key.startswith(VENDOR_PREFIX):
                continue
            if key not in SUPPORTED_KEYWORDS:
                raise UnsupportedSchemaError(
                    "unsupported keyword %r at %s; the generator would silently "
                    "ignore it, so it is rejected" % (key, where)
                )
        for key, value in node.items():
            if key in ("properties", "$defs"):
                if not isinstance(value, dict):
                    raise UnsupportedSchemaError("%s.%s must be an object" % (where, key))
                for sub_key, sub_value in value.items():
                    check_keywords(sub_value, "%s.%s.%s" % (where, key, sub_key))
            elif key in ("oneOf",):
                for i, sub_value in enumerate(value):
                    check_keywords(sub_value, "%s.oneOf[%d]" % (where, i))
            elif key == "items":
                check_keywords(value, where + ".items")
            elif key in ("required", "enum", "type"):
                continue
            elif isinstance(value, dict):
                check_keywords(value, "%s.%s" % (where, key))


# --------------------------------------------------------------------------
# Type model
# --------------------------------------------------------------------------


class TypeRef(object):
    """A resolved reference to a named type in the model."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "TypeRef(%r)" % self.name


def ref_to_name(ref: str) -> str:
    """'capability.schema.json#/$defs/CapabilityGrant' -> 'CapabilityGrant'."""
    match = re.match(r"^[a-z]+\.schema\.json#/\$defs/([A-Za-z0-9_]+)$", ref)
    if not match:
        raise UnsupportedSchemaError(
            "only intra-repository '<file>.schema.json#/$defs/<Name>' refs are "
            "supported; got %r" % ref
        )
    return match.group(1)


class Field(object):
    __slots__ = ("name", "schema", "required", "description")

    def __init__(self, name: str, schema: Dict[str, Any], required: bool) -> None:
        self.name = name
        self.schema = schema
        self.required = required
        self.description = schema.get("description")


class NamedType(object):
    """One generated type: object, union, enum, or alias."""

    __slots__ = (
        "name",
        "domain",
        "kind",
        "schema",
        "fields",
        "variants",
        "enum_values",
        "discriminator",
        "description",
        "cross_field_equal",
    )

    def __init__(self, name: str, domain: str, schema: Dict[str, Any]) -> None:
        self.name = name
        self.domain = domain
        self.schema = schema
        self.description = schema.get("description") or schema.get("title")
        self.fields: List[Field] = []
        self.variants: List[str] = []
        self.enum_values: List[str] = []
        self.discriminator: Optional[str] = None
        self.cross_field_equal: List[List[str]] = schema.get("x-cross-field-equal", [])
        self.kind = self._classify()

    def _classify(self) -> str:
        schema = self.schema
        if "oneOf" in schema and "x-discriminator" in schema:
            self.discriminator = schema["x-discriminator"]
            return "union"
        if "oneOf" in schema:
            # A nullable-ref alias such as {oneOf: [{$ref}, {type: null}]}.
            return "alias"
        if "enum" in schema:
            self.enum_values = list(schema["enum"])
            return "enum"
        if schema.get("type") == "object" and "properties" in schema:
            required = set(schema.get("required", []))
            for prop_name in sorted(schema["properties"]):
                self.fields.append(
                    Field(prop_name, schema["properties"][prop_name], prop_name in required)
                )
            return "object"
        return "alias"


class SchemaModel(object):
    """The whole contract set, resolved and validated once."""

    def __init__(self) -> None:
        index = load_index()
        self.contract_schema_version: str = index["contractSchemaVersion"]
        self.runtime_version: str = index["runtimeVersion"]
        self.source_digest: str = source_digest()
        self.types: Dict[str, NamedType] = {}
        self.order: List[str] = []
        self.variant_owner: Dict[str, str] = {}

        schemas = load_schemas()
        for file_name in index["files"]:
            schema = schemas[file_name]
            domain = schema.get("x-domain", file_name.split(".")[0])
            check_keywords(schema, file_name)
            defs = schema.get("$defs", {})
            for type_name in sorted(defs):
                if type_name in self.types:
                    raise SchemaModelError(
                        "duplicate type name %r (in %s and %s)"
                        % (type_name, self.types[type_name].domain, domain)
                    )
                named = NamedType(type_name, domain, defs[type_name])
                self.types[type_name] = named
                self.order.append(type_name)

        self._expand_unions()
        self._validate_refs()

    def _expand_unions(self) -> None:
        """Hoist each inline oneOf variant into its own named object type."""
        for name in list(self.order):
            named = self.types[name]
            if named.kind != "union":
                continue
            for i, variant in enumerate(named.schema["oneOf"]):
                title = variant.get("title")
                if not title:
                    raise SchemaModelError(
                        "union %s variant %d has no title; a stable generated "
                        "name cannot be derived" % (name, i)
                    )
                if title in self.types:
                    raise SchemaModelError("union variant name collides: %r" % title)
                variant_type = NamedType(title, named.domain, variant)
                if variant_type.kind != "object":
                    raise SchemaModelError(
                        "union %s variant %r must be an object" % (name, title)
                    )
                disc = named.discriminator
                disc_field = variant.get("properties", {}).get(disc)
                if not disc_field or "const" not in disc_field:
                    raise SchemaModelError(
                        "union %s variant %r must pin discriminator %r with a "
                        "const value" % (name, title, disc)
                    )
                if disc not in variant.get("required", []):
                    raise SchemaModelError(
                        "union %s variant %r must mark discriminator %r required"
                        % (name, title, disc)
                    )
                self.types[title] = variant_type
                self.order.append(title)
                named.variants.append(title)
                self.variant_owner[title] = name

    def _validate_refs(self) -> None:
        def walk(node: Any, where: str) -> None:
            if isinstance(node, dict):
                if "$ref" in node:
                    target = ref_to_name(node["$ref"])
                    if target not in self.types:
                        raise SchemaModelError(
                            "unresolved $ref %r at %s" % (node["$ref"], where)
                        )
                for key, value in node.items():
                    walk(value, "%s.%s" % (where, key))
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    walk(value, "%s[%d]" % (where, i))

        for name in self.order:
            walk(self.types[name].schema, name)

    def discriminator_const(self, variant_name: str) -> Tuple[str, str]:
        owner = self.variant_owner[variant_name]
        disc = self.types[owner].discriminator
        if disc is None:  # pragma: no cover - guaranteed by _expand_unions
            raise SchemaModelError("union %s has no discriminator" % owner)
        const = self.types[variant_name].schema["properties"][disc]["const"]
        return disc, str(const)

    def emitted_order(self) -> List[str]:
        """Deterministic emission order: domain, then type name.

        Used by the TypeScript emitter, where declarations are hoisted.
        """
        return sorted(self.order, key=lambda n: (self.types[n].domain, n))

    def eager_dependencies(self, name: str) -> List[str]:
        """Names that must already be bound when this declaration is executed.

        Python evaluates `X = Union[A, B]` and `X = Y` at import time, so those
        forms have eager dependencies. Dataclass field annotations do not,
        because every generated module uses `from __future__ import
        annotations`, which defers them to strings.
        """
        named = self.types[name]
        if named.kind == "union":
            return list(named.variants)
        if named.kind == "alias":
            found: List[str] = []

            def walk(node: Any) -> None:
                if isinstance(node, dict):
                    if "$ref" in node:
                        found.append(ref_to_name(node["$ref"]))
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for value in node:
                        walk(value)

            walk(named.schema)
            return found
        return []

    def topological_order(self) -> List[str]:
        """Emission order that satisfies eager dependencies.

        Deterministic: candidates are always visited in (domain, name) order,
        so the output is stable across runs and machines.
        """
        pending = self.emitted_order()
        emitted: List[str] = []
        seen = set()
        visiting = set()

        def visit(name: str) -> None:
            if name in seen:
                return
            if name in visiting:
                raise SchemaModelError(
                    "eager dependency cycle involving %r; the generated Python "
                    "module would fail at import time" % name
                )
            visiting.add(name)
            for dep in sorted(self.eager_dependencies(name)):
                if dep in self.types:
                    visit(dep)
            visiting.discard(name)
            seen.add(name)
            emitted.append(name)

        for name in pending:
            visit(name)
        return emitted
