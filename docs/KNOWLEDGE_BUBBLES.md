# CAPT Solo v0.4 — Knowledge Bubbles

A Knowledge Bubble packages claims, procedures, skills, examples, tests, proof,
trust metadata, provenance, compatibility, CTP receipts, AntiToken summaries,
and CSG fragments for portable, governed transfer between CAPT Solo instances.

## Lifecycle

```
imported -> quarantined -> validated -> approved -> installed
         -> deprecated -> removed
```

Imported bubbles are ALWAYS quarantined. They are never trusted automatically,
never executable, never overwrite local canonical memories or skills silently.
Installation requires explicit approval + a CTP-governed transaction.

## Manifest (v2)

`build_bubble` produces a v2 manifest with: `format_version=2`, `bubble_id`,
`bubble_version`, `originating_capt_version`, `min_compatible_capt_version`,
`max_compatible_capt_version`, `platform_metadata`, `exported_namespaces`,
included skill/procedure/claim/evidence/proof IDs, `trust_metadata`,
`lifecycle_metadata`, `artifact_inventory`, `per_artifact_hashes`,
`manifest_hash`, `signature_metadata` (placeholder), `redaction_declaration`,
`declared_permissions`, `declared_external_dependencies`, `export_policy`,
`provenance`, and `payload`. The `manifest_hash` binds the whole structure.

## Validation (12-step, manifest before payload)

1. container_structure  2. manifest_schema  3. manifest_hash
4. payload_inventory  5. artifact_hashes  6. version_compatibility
7. secret_scanning  8. permission_analysis  9. dependency_analysis
10. proof_chain  11. conflict_detection  12. trust_lifecycle

The manifest is validated BEFORE any payload is trusted. A bubble fails
validation if any check fails; it remains quarantined.

## Implemented

- v2 manifest with full required fields + per-artifact hashes.
- 12-step validation with manifest-before-payload ordering.
- Quarantine-by-default import; explicit approve + CTP install.
- Selective export with redaction declaration.
- Duplicate detection against installed bubbles.

## Experimental

- Signed bubbles (signature_metadata is a placeholder; no signing yet).
- Cross-instance bubble sync.

## Future

- Real signature verification.
- Bubble dependency resolution at install.

## Limitations

- Bubbles are local-first; no automatic remote sync.
- Signature is placeholder only (no cryptographic verification yet).
- Installed skills are created as candidates, not auto-published.

## Security Boundaries

- Imported bubbles are never trusted or executed.
- Secret patterns in bubble content are rejected at validation.
- Unsafe permissions in bundled skills block validation.
- Private memory is excluded from export unless `include_private=True`.
- Local canonical skills are never overwritten by bubble install.

## Verification

- `tests/test_v04_foundry.py` (bubble build/validate/install/export, quarantine).
- `tests/test_v04_plugin.py` (plugin bubble tools).
- `verify_runtime.py` (bubble_manifest_v2, bubble_validate_12step).
