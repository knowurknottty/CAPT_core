---
status: Accepted (Foundry M0)
date: 2026-08-03
relates_to: ADR-0103, ADR-0104, ADR-0110, ADR-0131
---

# ADR-0130 — CAPT Foundry boundary and asset-curation ownership

## Context

Project SEAL, SynSync, bioCAPT research, and Digital Archaeology all repeat the
same non-differentiating work: resolving the same alias twice, rediscovering the
same source, losing a source hash or locator, forgetting why a path failed,
treating private notes as public proof, and re-inventorying the same corpus.

A boundary reconciliation was performed against Git object state at
`5fb323d6edd8511b687eaec9f6656fc4b4d0b320` before any implementation. It found
that most capabilities a naive "Foundry" would build **already exist** on this
base and must not be duplicated:

| Capability | Already provided at 5fb323d | Object evidence |
|---|---|---|
| Append-only ledger, per-stream ordering, replay | `capt_runtime/store.py`, ADR-0104 | `events` table, `UNIQUE(stream_id, stream_version)`, `chain_next()` |
| Claim → evidence → verification persistence | `capt_runtime/services.py` | `propose_claim`, `record_evidence`, `record_verification`, `decide_claim` |
| Evidence contract model | `contracts/schema/evidence.schema.json` | `EvidenceKind`, `EvidenceRecord` |
| Provenance | `capt_solo/memory/models.py`, `capt_solo/foundry/proof.py` | present, tested |
| Temporal ordering | `capt_solo/memory/models.py`; `events.global_sequence`; `occurredAt` | present, tested |
| Portable verifiable asset format | `capt_solo/foundry/bubble.py` | `BUBBLE_FORMAT`, `build_bubble()` |
| Governance | `capt_solo/foundry/governance.py`, `capt_runtime/authority.py` | present, tested |

Six capabilities were verified genuinely absent — by semantic inspection, not
name matching: research entity identity, research alias resolution, corpus /
document manifest, curated artifact publication, Obsidian projection, and a
SEAL-shaped research-asset export.

## Decision

**CAPT Foundry is a consumer and asset-curation layer. It owns research-domain
identity and curated asset publication, and nothing else.**

Canonical definition:

> A CAPT-native curation and reusable-asset pipeline composed from existing
> canonical CAPT evidence, provenance, ledger, temporal, Knowledge Bubble, and
> runtime primitives, with Project SEAL as an initial consumer.

### Why the Foundry exists

To make the 500th research case cheaper and better than the first, by giving
durable identity to the research-domain nouns no CAPT subsystem currently owns
(entities, aliases, corpora) and by publishing curated, provenance-preserving,
replayable assets that any consumer can reuse. Without it, every consumer
re-derives entity identity privately and re-does inventory work already paid for.

### Why it is NOT another runtime

`capt_runtime` owns authority, governed execution, state transitions, receipts,
approval gates, and consequence classification. The Foundry declares no actor
kinds, evaluates no policy, issues no capability grants, and performs no state
transitions on runtime aggregates. Its registries are pure libraries over a
caller-supplied SQLite connection; they can be constructed by a runtime-owned
service. **There is no second composition root and no import-time construction.**

### Why it does NOT own evidence

`EvidenceRecord` is contract-defined (`contracts/schema/evidence.schema.json`)
and persisted by `RuntimeService.record_evidence` into the runtime event ledger,
with `record_verification` refusing to cite evidence the runtime does not hold.
The Foundry stores **references** (`evidence_ids`) and never a parallel evidence
body, status, or verification verdict. A Foundry asset citing evidence is a
pointer into runtime truth, not a copy of it.

### Why it does NOT own provenance

Provenance is canonical at `capt_solo/memory/models.py` and
`capt_solo/foundry/proof.py`. The Foundry **preserves and propagates** provenance
into exported assets — source digest, locator, actor, timestamps — but defines no
new provenance algebra and no competing trust computation.

### Why it does NOT own the ledger

ADR-0104 fixes one transactional store with a single-transaction commit
discipline and hash-chained events. The Foundry writes no event ledger, defines
no outbox, and performs no dispatch. Foundry registries persist domain rows only;
when a Foundry action must be governed and durably recorded as a runtime event,
that is the caller's `RuntimeService` command, not a Foundry write.

### Why it does NOT own governance

Authority checks (`require_authority`), actor kinds, and approval gates live in
`capt_runtime/authority.py` and `capt_solo/foundry/governance.py`. The Foundry
records *who asserted what* as data and refuses unsafe defaults (an alias never
self-promotes to canonical; a projection never leaves the declared root), but it
grants nothing and adjudicates nothing.

### Why it exports research ASSETS, not CASES

A case is a SEAL-owned artifact: ruleset binding, candidate portfolio, prompt
preflight, reviewer outcomes, human-gated promotion. The Foundry has no ruleset,
no candidate, and no submission concept — exporting a case would make the Foundry
a SEAL task author, which it must never be. It exports **reusable research
assets** (entities, aliases, corpus manifests, curated bundles) that SEAL
consumes to build cases faster. Ownership stays with SEAL; reuse comes from the
Foundry. Export is one-directional and read-only with respect to consumers.

## Scope (Foundry M0)

Implemented: Research Entity Registry, Research Alias Registry, Corpus/Document
Manifest, Curated Artifact Publisher, Obsidian Projection, SEAL Research Asset
Export.

Explicitly NOT implemented, because verified already satisfied on this base:
persisted evidence graph, proof ledger, temporal ordering. Duplicating any of
these is a defect.

## Consequences

- Foundry code depends on the base runtime and `foundry/bubble.py`; the reverse
  dependency is forbidden.
- `contracts/schema/common.schema.json` `StreamId` admits only
  `mission|task|capability|driverrun|claim`. The Foundry therefore does **not**
  mint runtime streams. Changing that pattern would require a contract change and
  a new ADR.
- Foundry storage is a separate SQLite file from `runtime.db` and `memory.db`,
  consistent with ADR-0104's separation-of-authority reasoning.
- SEAL consumes exports; it does not reach into Foundry internals.

## Migration and compatibility

- New package, additive only. No existing module is modified. M0-A/M0-B runtime
  behaviour is untouched, so their proofs remain valid.
- Foundry tables are created on demand and versioned by
  `foundry_schema_version`; a future schema change requires a migration and a
  version bump, per the repository's existing convention.
- Export payloads carry `format` and `format_version`; readers must reject an
  unknown major version.

## Unresolved repository-state discrepancies (recorded, not repaired)

1. `architecture/registry.yaml`, `AGENTS.md`, `CAPT_CANON.md`, and
   `CANONICAL_OWNERSHIP_MATRIX.md` **do not exist at `5fb323d`**. They exist only
   on unmerged refs. Governance for this base is the `ADR-01xx` series.
2. `capt_solo/evidence/` (ProofGraph, InvalidationGraph, EvidenceRecord) is
   introduced by `5c9c807373ce1881f5afa8be01da86398f55e390` and is reachable only
   from unmerged refs — never merged to `main`.
3. Registry-declared namespace `capt_solo.memory.semantic` is stale; the
   implementation is `capt_solo/lifecycle/semantic.py`.

See ADR-0131. These are governance concerns and are explicitly **not** repaired
by the Foundry effort.

## Implementation-status truth

Only the six M0 capabilities are implemented. No Foundry module claims to provide
evidence-graph traversal, proof-ledger semantics, or temporal ordering; those
names do not appear as Foundry capabilities. No placeholder or
`return NotImplemented` module is created.

## Alternatives considered

1. **New repository** — rejected: five repos already hold pieces of this
   substrate; a sixth compounds fragmentation.
2. **Inside `seal`** — rejected: the Foundry is not a SEAL component; "Foundry"
   appears nowhere in either SEAL workflow, and SEAL already carries two
   competing unmerged M0 packages.
3. **Rebase onto `integration/capt-v05-final-audit`** (where evidence + registry
   exist) — rejected: unmerged, non-authoritative state.
4. **Recreate `capt_solo/evidence/` on main** — rejected: duplicate
   implementation of an existing subsystem.

## Reversal conditions

- If `capt_solo/evidence/` is ever merged to `main`, re-evaluate whether Foundry
  asset records should reference `ProofGraph` node ids directly.
- If a Foundry capability requires minting a runtime stream, stop and raise a
  contract ADR for `StreamId` before proceeding.
- If any Foundry component begins evaluating policy or granting authority, this
  ADR is violated and the component must be moved behind `RuntimeService`.
