# LIFECYCLE — CAPT Core Lifecycle, State & Consolidation

Status: RECOVERED (knowledge archaeology pass, 2026-07-30)
Sources: `docs/KNOWLEDGE_BUBBLES.md`, `docs/GOVERNANCE.md`, `capt_solo/ctp`,
`capt_solo/lifecycle`, `architecture/checkpoint.schema.json`, ADR-0005/0012.

## Cognitive transaction lifecycle (CTP)
- Append-only JSONL journal under the CAPT runtime home.
- States: begin → validate → note → commit / abort.
- Immutable receipts (`Receipt` dataclass: tx_id, status, correlation_id,
  idempotency_key, created_at, finalized_at, meta).
- Implemented: `capt_solo/ctp/journal.py` (SHIPPED in v0.5).
- Constructor contract: `journal_dir` XOR `journal_path` (raised if both).

## Knowledge Bubble lifecycle
From `docs/KNOWLEDGE_BUBBLES.md`:
```
imported -> quarantined -> validated -> approved -> installed
        -> deprecated -> removed
```
- Imported bubbles are ALWAYS quarantined. Never auto-trusted, never executable,
  never silently overwrite local canonical memories/skills.
- Installation requires explicit approval + CTP-governed transaction.
- Manifest v2: bubble_id, version, compatibility range, trust_metadata,
  lifecycle_metadata, artifact_inventory, per-artifact hashes, manifest_hash,
  signature_metadata (placeholder), redaction_declaration.
- Status: CONCEPTUAL — no `knowledge_bubble` module in baseline. The CTP
  transactional substrate exists; the bubble wrapper is not implemented.

## Session / episodic lifecycle
- `capt_solo/lifecycle/sessions.py` (SessionStore): session-scoped episodic
  timeline. Partial (572 LOC + session_* tables).
- Checkpoint schema: `architecture/checkpoint.schema.json` (live checkpoint
  regeneration via `capt workspace checkpoint`).
- Status: SHIPPED (partial).

## Consolidation-as-Learning
- Registry lists `Consolidation-as-Learning` and `Continuous Learning` as Layer 10
  capabilities. `capt_solo/learning` exists (imports OK) but no dedicated test.
- Biological analogue: memory consolidation during "offline" processing.
- Status: PARTIAL — present as module, not fully wired to a consolidation loop.

## Semantic versioning & migration lifecycle
- CAPT_CANON: MAJOR.MINOR.PATCH; migrations forward-only, backup + reversible
  where feasible; `SCHEMA_VERSION` authoritative.
- `capt_solo/memory/engine.py` SCHEMA_VERSION=5, forward-migrates <5.
- Status: SHIPPED.

## Deprecation lifecycle
- CAPT_CANON I-11: deprecated subsystems retain compat layer ≥1 MINOR; removal
  requires owner approval + architecture update.
- Status: POLICY (enforced by ADR-0007 owner gate).

## Release lifecycle (Option A)
- Source commit (immutable) → Metadata commit (frozen candidate_sha) → validate
  → owner approval → tag/merge/publish (blocked until owner declares GA).
- Status: SHIPPED (v0.5 freeze protocol, docs/release/CANDIDATE_FREEZE_PROTOCOL.md).

## Missing lifecycle pieces
- Autobiographical memory lifecycle — registry "missing".
- Synchronization lifecycle (multi-instance) — registry "missing"; Knowledge
  Bubbles is the portability mechanism but not the sync protocol.
- DREAM / ENGRAM consolidation loops — registry "missing" (research package).
