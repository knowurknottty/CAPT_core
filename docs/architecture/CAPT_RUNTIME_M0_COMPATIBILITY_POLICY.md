# CAPT Runtime M0 Compatibility Policy

Applies to all contracts under `contracts/schema/` (frozen at
`contractSchemaVersion: 1.0.0`; instance `SchemaVersion` const "1.0.0").

## Versioning model

Three levels of change, aligned with semantic-version intent for a schema set:

### patch
- Documentation correction (comments, descriptions, examples) with **identical
  wire shape**.
- Generator correction (binding codegen fix) that does not change the emitted
  wire contract.
- No `$defs` structural change; no property added/removed/retyped.
- **No version bump required** for the contract set, but the generator commit
  must be recorded and drift check must stay green.

### minor
- **Backward-compatible additive** schema evolution:
  - new optional property on an existing type (`"required"` unchanged);
  - new type added that no existing consumer is required to emit;
  - new enum value added as a non-default, non-required choice.
- Existing serialized instances remain valid against the new schema.
- Requires: **schema review + ADR note** (even if additive) and regeneration of
  both bindings with a green drift check.
- **contractSchemaVersion stays 1.0.0** for additive minor changes; the ADR
  records the addition. (A numeric minor bump is reserved for when the set is
  formally promoted — see major.)

### major
- **Incompatible** contract or semantic change:
  - removing/renaming a property or type;
  - changing a property type or making an optional property required;
  - changing validation semantics (e.g. relaxing a traversal guard);
  - any change that breaks existing serialized instances or conformance tests.
- Requires: **explicit ADR + major version bump** (`contractSchemaVersion`
  → 2.0.0, instance `SchemaVersion` const updated in `common.schema.json`),
  regeneration, drift check, and a migration/compat plan for in-flight aggregates.

## Frozen invariants (M0 scope)

1. **No breaking schema changes** without an ADR + major bump.
2. **No aggregate ownership changes** without an ADR.
3. **No widening of driver authority** (see `CAPT_RUNTIME_M0_AUTHORITY_MATRIX.md`).
4. **No new side-effect capability** under M0.
5. **No direct external harness types** in CAPT public contracts.
6. **No replacement** of generated bindings by hand-maintained models.
7. **No weakening** of replay / idempotency / verification tests.
8. **No claim** that M0 includes external OpenHarness integration.

## Allowed without a new ADR (but recorded)

- Bug fixes (behavior-preserving).
- Documentation corrections.
- Additive backward-compatible fields (schema review + ADR note + regeneration +
  drift check).

## Prohibited in M0

- M0-C work (separate branch + explicit authorization).
- RuntimeAggregate / RuntimeManifest / RuntimeIdentity implementation.
- Integration of another (external) driver.
- Any change to the frozen wire shape for stylistic reasons alone.

## Current frozen version

- `contractSchemaVersion`: **1.0.0**
- Instance `SchemaVersion` const: **"1.0.0"** (`contracts/schema/common.schema.json`)
- Generated bindings: Python `capt_contracts` + TypeScript `types.ts`, drift-clean.
