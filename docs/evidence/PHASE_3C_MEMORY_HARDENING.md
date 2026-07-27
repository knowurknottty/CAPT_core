# Phase 3C — Internal Memory Hardening

**Branch:** integration/full-public-architecture
**Date:** 2026-07-26
**Issue:** #5
**Preceded by:** Phase 3B (commit ba14a41)

## Objective
Complete and harden the already-internal, un-gated Layer 3 memory substrate
before importing research-grade memory systems. Establish canonical memory
interfaces reusing ontology types (ADR-0002, I-12), extend persistence with
uncertainty/retention/consent/identity/evidence fields, add migration rollback
and corruption recovery, and prove behavior with real persistence tests.

## Canonical foundation (Layer 0.5)
- **New `capt_solo/ontology/`** — the shared ontology (16 canonical terms as
  typed dataclasses: Entity, Relationship, Identity, Evidence, Provenance,
  Confidence, Claim, Contradiction, TemporalOrdering, Observation, Inference,
  Procedure, Skill, MemoryRef). This satisfies ADR-0002 (ontology precedes
  knowledge/memory/trust/governance) and I-12 (shared upstream types).

## Canonical memory interfaces (Layer 3)
- **New `capt_solo/memory/interfaces.py`** — canonical contracts reusing ontology
  types: `RetentionPolicy`, `ConsentState`, `MigrationDirection`, `MemoryIdentity`,
  `TemporalMetadata`, `SourceEvidence`, `MemoryRecord` (single canonical record
  representation), `RetrievalResult`, `ReplayEvent`, `MigrationVersion`,
  `MemoryStore` protocol, plus `memory_to_canonical()` / `canonical_to_memory_kwargs()`
  adapters. **No parallel incompatible definitions** were introduced in individual
  memory modules (I-12) — the engine's `Memory` dataclass is the current
  implementation; the adapter is the single mapping point.

## Engine hardening (`capt_solo/memory/engine.py`)
- **Schema v4 → v5:** added `uncertainty`, `retention`, `consent`, `identity_link`,
  `evidence_refs` columns to `memories` via backward-compatible `ALTER` with safe
  defaults. Existing rows unaffected. `SCHEMA_VERSION = 5`.
- **`store`/`update`/`get`/`_row_to_memory`/`export_json`/`_upsert`** now carry the
  new canonical fields end-to-end. `Memory` dataclass extended with the same fields.
- **Uncertainty:** explicit `Optional[float]` (0.0–1.0), validated on store/update,
  preserved through export/import, exposed in canonical adapter.
- **Retention:** `RetentionPolicy` string (transient/session/durable/archival/
  tombstone), default `durable`.
- **Consent:** `ConsentState` string (granted/denied/unset/expired), default
  `unset`. `require_consent_for(*namespaces)` enforces **default-deny** for
  sensitive namespaces (I-05 privacy-preserving defaults).
- **Identity linkage:** `identity_link` column + canonical `MemoryIdentity`.
- **Evidence linkage:** `evidence_refs` list persisted as JSON.
- **Migration rollback:** `rollback_to(version)` restores the **pre-migration
  backup** taken during `_init_schema` (stored as `self._pre_migration_backup`).
  Refuses to mutate schema without a verified backup (safety gate).
- **Corruption recovery:** `recover_corrupt()` scans rows, quarantines malformed
  records (bad JSON metadata / out-of-range confidence) into a quarantine
  namespace instead of crashing — bounded failure domain (I-07). `_row_to_memory`
  is now resilient to malformed metadata on read paths.
- **Interrupted-write recovery:** relies on SQLite WAL + the existing verified
  pre-migration backup; `backup()` checkpoints WAL before copy.

## Security
- No secret material persisted: `secrets.screen` remains the screening path; the
  new fields carry only provenance/consent metadata, no payloads.
- Consent default-deny for sensitive namespaces (I-05).
- No hidden telemetry or network dependency introduced (I-01).
- AntiToken remains optional and stateless (unchanged; verified in fitness tests).

## Failure semantics tested
Empty stores, malformed entries, out-of-range uncertainty, duplicate handling,
missing optional accelerators (antitoken), corrupt-DB open (quarantine),
unsupported schema version (rollback), invalid timestamps (float coercion),
conflicting provenance (preserved), retrieval uncertainty (carried).

## Tests added
`tests/test_phase3c_memory_hardening.py` (12 tests):
- schema version is 5
- store carries canonical fields (uncertainty/retention/consent/identity/evidence)
- uncertainty preserved through update + range-validated
- export/import round-trip preserves all new fields
- migration forward (v4→v5) + rollback to v4 using pre-migration backup
- corruption recovery quarantines bad row, good row still retrievable
- consent default-deny for sensitive namespace
- canonical adapter round-trip (Memory ↔ MemoryRecord via ontology types)
- empty store search, duplicate-id, missing optional accelerator

Existing migration/release-scenario tests updated from schema v4 → v5 assertions
(the schema legitimately advanced; no behavior regression).

## Verification
- `pytest`: **389 passed** (was 377 before 3C; +12 new, +0 regressions after
  assertion updates).
- `verify_runtime.py`: **46/46 pass**.
- Engine imports cleanly; canonical adapter maps without loss.

## Result
The internal memory substrate now satisfies the canonical `MemoryRecord` contract
end-to-end, with explicit uncertainty, retention, consent, identity, and evidence
linkage; safe migration rollback; and corruption recovery. Ready for Phase 3D
(Episodic/ECHO convergence) which builds on this stable base.
