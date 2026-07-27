# MEMORY_CONVERGENCE_EVIDENCE.md

- **scope**: Public memory convergence (Decision 2) — explicit memory-type taxonomy, non-destructive revision, provenance chains, quarantine of malformed data, DREAM boundary.
- **source_commit**: `3493ef2` (parent of this milestone commit)
- **milestone**: M5

## Implemented
- `capt_solo/memory/types.py` (NEW): `MemoryType` enum with all 14 required
  distinctions (Event, Observation, Episode, Interpretation, Inference, Belief,
  Identity Narrative, Autobiographical, Semantic, Revision, Correction,
  Supersession, Provenance, Replay). `MemoryRecord` dataclass carries
  provenance_chain, uncertainty, confidence, source/evidence refs, revisions
  (non-destructive), supersedes/superseded_by, is_correction/is_inferred/
  is_synthetic, quarantined flag, replay_metadata. `validate_memory_record()`
  quarantines malformed data (empty content, invalid type, out-of-bounds
  uncertainty, inferred/synthetic without provenance) instead of silent storage.
- `capt_solo/memory/engram.py` (EXTENDED): `Engram` now carries `memory_type`
  (validated against taxonomy), `provenance_chain`, and `revisions`. `store_trace`
  accepts memory_type + provenance_chain. New `revise_engram()` performs
  NON-DESTRUCTIVE revision: appends a revision entry with prior-content hash,
  updates content, preserves history (prior content recoverable).
- `capt_solo/learning/dream.py` (EXTENDED): new `propose_knowledge_record()`
  returns a `MemoryRecord` explicitly labeled `is_inferred=True` with provenance;
  it does NOT write to canonical memory (caller decides). Enforces the boundary
  that DREAM-generated/recombined material stays labeled inferred/synthetic
  until verified and never silently overwrites canonical memory.

## Memory-type distinctions preserved
The taxonomy is explicit; no collapse into one generic record. Adapters (Engram)
preserve the canonical `memory_type` and `provenance_chain` through store/get.

## Quality requirements addressed
- deterministic IDs: engram_id / record_id via uuid + content hash.
- causal ordering: revisions record prior/new content hashes + timestamp.
- conflict retention: MemoryEngine.list_conflicts available; revisions preserve history.
- non-destructive revision: apply_revision / revise_engram never erase prior content.
- correction/supersession semantics: explicit kinds; supersedes/superseded_by links.
- uncertainty tracking: MemoryRecord.uncertainty (bounded 0..1, else quarantined).
- provenance chains: provenance_chain on every record; required for inferred.
- identity linkage: Identity Narrative is a distinct MemoryType.
- evidence linkage: evidence_refs on records and engrams.
- replay controls: replay_metadata field; REPLAY is a distinct MemoryType.
- consent boundaries: local consent ledger is a separate (abstraction) concern.
- quarantine of malformed data: validate_memory_record().
- schema migrations / verified rollback: MemoryEngine migration infra (prior).
- export/import integrity: MemoryEngine export_json (prior).
- bounded retention / no silent loss: retention policies (prior); revisions prevent loss.
- no hidden network dependence: HMC/ENGRAM/DREAM are local-only (verified).
- no hidden persistence beyond documented stores: all via MemoryEngine.

## HMC note (honest)
HMC (`memory/hmc.py`) is a deterministic, LOSSY holographic compressor. Compression
ratios are design targets, NOT verified benchmarks. Reconstruction is approximate
(nearest stored content), documented — not hidden. No change needed; status
remains `partial` (registry reconciled in M1).

## Test commands and exact results
```
python3 -m pytest tests/test_memory_types.py -q
# 10 passed
python3 -m pytest -q
# 582 passed (full suite)
python3 architecture/validate_registry.py
# SUMMARY: 15 checks, 0 fail, 0 warn
```

## Limitations
- Autobiographical/Semantic dedicated store classes are not separate modules; they
  are represented as MemoryType values within the MemoryRecord model (the canonical
  semantics are explicit, storage is unified via MemoryEngine). A dedicated
  AutobiographicalStore could be added later without changing the taxonomy.
- DREAM `propose_knowledge_record` returns a proposed record; persistence of
  proposed (inferred) records into knowledge is gated by corroborating evidence
  in `DreamConsolidator.run` (already SUPPORTED-only, never VERIFIED silently).
- Quarantine routing (where quarantined records go) is the caller's responsibility;
  validate_memory_record flags them but does not itself store them elsewhere.

## Files changed
- `capt_solo/memory/types.py` (new)
- `capt_solo/memory/engram.py` (extended: memory_type, provenance_chain, revisions, revise_engram)
- `capt_solo/learning/dream.py` (extended: propose_knowledge_record)
- `tests/test_memory_types.py` (new, 10 tests)
