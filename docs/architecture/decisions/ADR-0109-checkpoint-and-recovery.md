# ADR-0109 — Checkpoint manifest and recovery semantics

**Status:** Accepted (M0-A)
**Date:** 2026-08-02
**Relates to:** spec §15, ledger Findings K/L, workflow M0-A items 10–12

## Context

Ledger Finding L: checkpoints were too shallow — mission state plus a worktree pointer would not capture leases, driver runs, policy versions, artifacts, or pending outbox entries. Ledger Finding K: a synchronous per-event hash chain risks premature complexity; begin with append-only events, per-event hashes, and signed or Merkle-rooted checkpoint manifests.

Baseline: the existing `session_checkpoints` table (`capt_solo/memory/engine.py:341`) and `sessions.checkpoint()` (`capt_solo/lifecycle/sessions.py:156`) produce a *memory-session restart packet* (objective, progress, CSG + antitoken render). It contains no aggregate versions, no lease state, no ledger position, no outbox state, no policy digest, and no integrity digest. It is a different artifact for a different subsystem.

## Decision

**`CheckpointManifest` is a complete, self-verifying description of runtime state at a ledger position, sufficient to reconstruct state without replaying from event 1.**

### Required content

| Field | Why it must be present |
|---|---|
| `schemaVersion` | reject an incompatible manifest (ADR-0101) |
| `runtimeVersion` | detect a manifest written by different runtime logic |
| `checkpointId`, `createdAt` | identity; `createdAt` is descriptive only (ADR-0106) |
| `ledgerPosition` | `{globalSequence, eventId}` — the exact resume point |
| `missionVersions`, `taskVersions`, `capabilityVersions`, `driverRunVersions`, `claimVersions` | per-stream `{streamId: version}` maps; the aggregate-version state |
| `activeLeases`, `activeReservations` | authority state at checkpoint time; without it, resume could re-authorize or lose a burned use (Finding L) |
| `pendingOutbox` | event ids not yet dispatched; without it, resume silently drops undelivered events |
| `artifactHashes` | referenced artifact integrity |
| `policyBundleDigest` | which policy authorized the state (Finding I) |
| `recoveryState` | discriminated union: `clean` \| `awaiting_reconciliation` \| `degraded` |
| `integrityDigest` | `sha256` over the canonicalized manifest with this field removed |

### Integrity model

Per Finding K, M0-A does **not** implement a synchronous per-event hash chain. Instead:

1. Each ledger event stores `payloadDigest = sha256(canonical_json(payload))`, verified on replay.
2. The manifest stores `ledgerDigest` — a **Merkle-style fold** over `(globalSequence, eventId, payloadDigest)` for every event up to `ledgerPosition`, computed as an ordered SHA-256 chain fold. This gives tamper evidence over the whole prefix without requiring a chain write on the hot path.
3. The manifest stores `integrityDigest` over itself.

Consequence: a modified, reordered, inserted, or deleted event in the checkpointed prefix changes `ledgerDigest` and is detected at load. This is tamper *evidence*, not tamper *prevention*, and is stated as such.

### Recovery semantics

`recover(store, checkpoint_id=None)`:

1. Load manifest; verify `integrityDigest`. Mismatch → `CheckpointCorruptError`. **Never** partially trust a corrupt manifest.
2. Verify `schemaVersion` compatibility. Mismatch → `CheckpointIncompatibleError`.
3. Recompute `ledgerDigest` from the store over `[1 .. ledgerPosition.globalSequence]`. Mismatch → `CheckpointCorruptError`.
4. Restore aggregate states at the recorded versions.
5. Replay only events with `globalSequence > ledgerPosition.globalSequence` (the tail).
6. Re-arm pending outbox entries so undelivered events are delivered after restart.
7. If `recoveryState = awaiting_reconciliation`, the runtime enters a mode where consequential dispatch is refused until reconciliation completes (ADR-0107, ADR-0108).

### Equivalence guarantee

**`checkpoint + tail replay` must produce state byte-identical to `full replay from event 1`.** This is the central correctness property and is asserted by a conformance test comparing canonical JSON of every aggregate. If it did not hold, the checkpoint would be an independent source of truth rather than an optimization — an unacceptable divergence risk.

### Fallback

If no valid checkpoint exists, recovery falls back to full replay. A corrupt checkpoint is **never** silently skipped; it raises. The caller may then explicitly choose full replay. Silent fallback would hide tampering.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Extend `session_checkpoints` | Different subsystem, different scope, and the existing table is reachable by five foundry subsystems through the shared connection. Rejected; term mapping recorded. |
| Full replay only, no checkpoints | Replay cost grows unbounded with ledger length; also fails the explicit M0-A requirement for checkpoint creation and restart. Rejected. |
| Checkpoint as the sole source of truth (discard events) | Destroys auditability and makes the equivalence property meaningless. Rejected. |
| Synchronous per-event hash chain | Finding K: premature complexity on the hot path; complicates migration and recovery. Deferred. |
| Cryptographic signing of manifests | Requires key management with no M0 threat model to justify it. Deferred; the digest field is signature-ready. |
| Skip a corrupt checkpoint and fall back silently | Converts detected tampering into invisible behaviour. Rejected outright. |

## Consequences

**Positive**
- Restart cost is bounded by tail length, not ledger length.
- Tampering with the checkpointed prefix is detected.
- The equivalence property is machine-checked, so the checkpoint cannot drift from the ledger.
- Undelivered outbox entries survive restart.

**Negative / costs**
- `ledgerDigest` computation is O(events since genesis) at checkpoint time. Acceptable at M0 volume; a future incremental fold is a straightforward optimization.
- The manifest must be extended whenever a new aggregate type is added — enforced by a completeness test against the aggregate registry.
- Tamper evidence, not prevention: an attacker with write access to the database can rewrite both the events and the manifest. Honest limitation, stated in the security section of the M0-A decision document.

## Reversal conditions

1. Ledger length makes the digest fold expensive → incremental/streaming fold, or a periodic Merkle root with a chain of roots.
2. A threat model requiring tamper *prevention* is adopted → per-event hash chaining plus manifest signing, accepting the Finding K migration cost.
3. Aggregate count grows large enough that full version maps bloat the manifest → per-aggregate-type sub-manifests.

## Evidence from the current repository

- `capt_solo/memory/engine.py:341-358` — `session_checkpoints(checkpoint_id, session_id, version, objective, progress, ...)`: no aggregate versions, no lease state, no ledger position, no outbox, no integrity digest.
- `capt_solo/lifecycle/sessions.py:156` `checkpoint()` and `:245` `resume()` — produce a `RestartPacket` from CSG + antitoken; a *context* artifact, not a *state* manifest.
- `capt_solo/ctp/journal.py:185-191` `integrity_check()` — re-parses the whole journal and returns a bool; the precedent for integrity verification, but with no digest and no tamper detection (a semantically valid forged record passes).
