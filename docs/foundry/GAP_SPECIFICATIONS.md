# CAPT Foundry M0 — Gap Specifications

Base: `5fb323d6edd8511b687eaec9f6656fc4b4d0b320`. Governed by ADR-0130.

Each gap was verified by semantic inspection of the approved base, not by
class-name matching. Three originally proposed items were **withdrawn** after
semantic-equivalence checking; they are recorded at the end.

---

```yaml
gap:
  name: Research Entity Registry
  canonical_owner: CAPT Foundry (new; no existing owner)
  existing_related_components:
    - capt_runtime/aggregates/claim_driver.py (ClaimAggregate — claims, not entities)
    - capt_solo/memory/engine.py (memory records keyed by memory_id)
    - contracts/schema/*.json (mission, task, capability, driverrun, claim — no entity)
  exact_missing_behavior: >
    No CAPT subsystem gives a durable, deduplicated identity to a real-world
    research subject (person, organization, place, work, event) independent of
    any claim or memory row. Verified: zero Entity/Alias/Corpus/Source/Dataset
    definitions across all five contract schemas at 5fb323d.
  why_extension_is_required: >
    Without stable entity identity, every consumer re-derives "is this the same
    subject?" privately, which is exactly the duplicated work the Foundry exists
    to eliminate. Claims reference entities; they cannot substitute for them.
  proposed_location: capt_foundry/entities.py
  composition_root_impact: >
    None. Pure library over a caller-supplied sqlite3.Connection. No CAPTRuntime
    change. No import-time construction, no global, no service locator.
  migration_risk: >
    Low. New tables in a separate SQLite file; additive only; schema versioned by
    foundry_schema_version.
  acceptance_evidence: >
    tests/capt_foundry/test_entities.py — registration, canonical digest
    determinism, duplicate rejection, content-hash idempotency, merge with
    supersede, replay from a fresh connection.
```

```yaml
gap:
  name: Research Alias Registry
  canonical_owner: CAPT Foundry (new for research scope)
  existing_related_components:
    - capt_solo/memory/engine.py::add_alias/resolve_alias + memory_aliases table
  exact_missing_behavior: >
    The existing alias table maps an alias string to a MEMORY-RECORD id. It has
    no notion of a research entity, no evidence backing, no confidence, no actor
    attribution, and no ambiguity signalling. Research alias resolution must
    answer "which real-world subject is this name?" and must refuse to guess when
    a name is ambiguous.
  why_extension_is_required: >
    Semantically distinct from memory aliasing. Reusing the memory table would
    conflate record identity with subject identity and silently make private
    memory ids load-bearing for research conclusions.
  proposed_location: capt_foundry/entities.py (AliasRegistry, same module as entities)
  composition_root_impact: None. Same pure-library form.
  migration_risk: >
    Low. Does not read or write memory_aliases; no interaction with memory.db.
  acceptance_evidence: >
    tests/capt_foundry/test_entities.py — resolution, ambiguity refusal
    (AmbiguousAlias raised, never a guess), alias to unknown entity refused,
    evidence-backed alias, case/whitespace normalization without collapsing
    genuinely distinct names.
```

```yaml
gap:
  name: Corpus / Document Manifest
  canonical_owner: CAPT Foundry (new; no existing owner)
  existing_related_components:
    - capt_runtime/store.py (runtime events; not a document inventory)
    - contracts/schema/evidence.schema.json::ArtifactHashEvidence (single artifact digest)
  exact_missing_behavior: >
    No component inventories a set of documents with per-document digest, byte
    size, locator, and a manifest-level digest over the whole set. ArtifactHash
    evidence covers one artifact inside a claim; it is not a reusable corpus
    inventory and cannot answer "have we already ingested this corpus?".
  why_extension_is_required: >
    Prevents re-inventorying and re-hashing the same corpus per consumer, and
    makes duplicate detection and freshness checks possible without a scan.
  proposed_location: capt_foundry/corpus.py
  composition_root_impact: None.
  migration_risk: >
    Low. Records metadata only — never document bodies. No file reads outside a
    caller-declared root; path escape and symlink escape fail closed.
  acceptance_evidence: >
    tests/capt_foundry/test_corpus.py — deterministic manifest digest, duplicate
    document detection by content hash, path-escape refusal, symlink-escape
    refusal, freshness marking, manifest digest changes when membership changes.
```

```yaml
gap:
  name: Curated Artifact Publisher
  canonical_owner: CAPT Foundry (new); asset FORMAT owned by capt_solo/foundry/bubble.py
  existing_related_components:
    - capt_solo/foundry/bubble.py::KnowledgeBubbleRuntime.build_bubble (static)
  exact_missing_behavior: >
    The bubble format exists but nothing assembles Foundry research assets into
    one, records publication provenance, or refuses to publish an asset whose
    referenced entities/documents are unknown. build_bubble is a format builder,
    not a curation pipeline.
  why_extension_is_required: >
    The publisher is the value delivery point: it turns registry contents into a
    reusable, hash-verifiable asset. It REUSES build_bubble and defines no second
    format.
  proposed_location: capt_foundry/publisher.py
  composition_root_impact: >
    None. Calls the existing @staticmethod build_bubble directly — no
    KnowledgeBubbleRuntime instance, therefore no parallel construction of a
    canonical subsystem (respects the composition-root invariant).
  migration_risk: >
    Low. Consumes the existing format; asset payload carries format_version so
    readers can reject unknown majors.
  acceptance_evidence: >
    tests/capt_foundry/test_publisher.py — publish produces a valid bubble
    manifest, manifest_hash verifies, dangling entity/document reference refused,
    republication is deterministic (byte-identical for identical input),
    provenance preserved end to end.
```

```yaml
gap:
  name: Obsidian Projection
  canonical_owner: CAPT Foundry (new; no existing owner anywhere)
  existing_related_components: none (verified: zero SEAL/Foundry notes across 4 local vaults)
  exact_missing_behavior: >
    No component renders curated assets as human-readable Markdown for review.
  why_extension_is_required: >
    Human review is a hard requirement of every governing workflow, and the human
    cannot inspect SQLite rows. The projection is READ-ONLY and derived: the
    ledger and registries stay canonical, exactly as OneNote is a projection in
    the SEAL workflow.
  proposed_location: capt_foundry/projection.py
  composition_root_impact: None.
  migration_risk: >
    Low, but write-path risk is real, so: writes confined to a caller-declared
    vault root; path traversal and symlink escape refused; filenames sanitized;
    never deletes; regenerating is idempotent.
  acceptance_evidence: >
    tests/capt_foundry/test_projection.py — deterministic Markdown, path-escape
    refusal, symlink-escape refusal, filename sanitization of hostile titles,
    idempotent regeneration, no write outside root.
```

```yaml
gap:
  name: SEAL Research Asset Export
  canonical_owner: CAPT Foundry (produces); Project SEAL (consumes)
  existing_related_components:
    - ~/seal-pdfs mission_control (unmerged SEAL M0; consumer, not a dependency)
  exact_missing_behavior: >
    No SEAL-shaped export of Foundry assets exists. SEAL must be able to consume
    entities, aliases, and corpus manifests without importing Foundry internals.
  why_extension_is_required: >
    This is the "SEAL is the first client" contract. Export is a stable data
    boundary, so SEAL never depends on Foundry table layout.
  proposed_location: capt_foundry/seal_export.py
  composition_root_impact: None.
  migration_risk: >
    Low. Versioned envelope (format + format_version); no import path from SEAL
    into Foundry internals; Foundry does not import SEAL.
  acceptance_evidence: >
    tests/capt_foundry/test_seal_export.py — deterministic envelope, digest
    stability, no case/ruleset/candidate/prompt/submission fields present
    (asserted by explicit key scan), unverified claims never exported as
    verified, round-trip integrity.
```

---

## Withdrawn after semantic-equivalence verification

Per the Captain's ruling these are satisfied by existing runtime capabilities on
the approved base and **must not be duplicated**.

| Originally proposed | Satisfied at 5fb323d by | Evidence |
|---|---|---|
| Persisted Evidence Graph | `RuntimeService.propose_claim / record_evidence / record_verification / decide_claim`; `ClaimAggregate.evidenceIds`; append-only `events` table; `capt_runtime/replay.py` | Verification citing unrecorded evidence raises `AuthorityViolation` (`services.py`) |
| Proof Ledger | `capt_runtime/store.py` `events` table + ADR-0104 / ADR-0108 / ADR-0109 | `UNIQUE(stream_id, stream_version)`, `chain_next()`, checkpoint table |
| Temporal Ordering | `capt_solo/memory/models.py` (Production, tested); `events.global_sequence`; `occurredAt` on every envelope | ADR-0106: timestamps descriptive, ordering by sequence |

No Foundry module implements, wraps, or claims any of these three.
