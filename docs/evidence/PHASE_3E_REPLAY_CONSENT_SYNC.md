# Phase 3E — Replay, Consent, and Local Synchronization Abstractions

**Branch:** integration/full-public-architecture
**Date:** 2026-07-26
**Issue:** #5
**Preceded by:** Phase 3D (commit c6a9f6c)

## Objective
Make Replay, Consent, and Synchronization first-class canonical capabilities
(no longer spec-only). Implement safe local foundations; gate network transports.

## Replay — `capt_solo/memory/replay.py`
- `ReplayEngine` with `ReplayMode` (DRY_RUN / RECONSTRUCT / EXECUTE) and
  `ReplayStatus` (PENDING/RUNNING/COMPLETED/FAILED/CANCELLED).
- Deterministic event replay, dry-run mode, target-state reconstruction, replay
  provenance, replay version, partial replay, failure reporting, cancellation.
- **Safety (I-07):** replay NEVER auto-executes unsafe external side-effect
  events. Even in EXECUTE mode, a `side_effect=True` event raises a hard
  RuntimeError (propagates, not swallowed as bounded failure). Such events
  require a dedicated executor with explicit authorization. Default behavior is
  state reconstruction / simulation.
- `ReplayEvent` carries provenance, replay_version, and `side_effect` flag.

## Consent — `capt_solo/memory/consent.py`
- `ConsentStore` local ledger: scope, subject identity, allowed/denied
  operations, expiration, revocation, provenance, policy version.
- **Default-deny** for sensitive operations (I-05): `check()` returns False
  unless an active grant matches. Explicit DENY takes precedence over GRANT
  regardless of record order.
- Local audit trail (`audit_trail`). No remote consent synchronization (per
  Phase 3E constraint). No biometric/private data collected.
- Export/import for local persistence.

## Synchronization — `capt_solo/memory/sync.py`
- Transport-neutral contract (`SyncTransport`) + canonical `SyncManifest` with
  `VersionVector` (conflict context), records, tombstones, provenance.
- Safe local transports implemented and tested:
  - `FilesystemTransport` (default-enabled)
  - `ExportImportTransport` (default-enabled)
  - `RemovableMediaTransport` (default-enabled, media-namespaced bundle)
- `LanTransport` REGISTERED but **disabled by default** (security gate [S]):
  opt-in, requires `authenticate=True` AND `encrypt=True` before any operation;
  otherwise raises RuntimeError. Cleanly omitted from baseline packaging.
- `merge_manifests()` performs union-by-id, tombstone-wins, version-vector join,
  and conflict reporting without crashing (bounded failure).

## Tests added
`tests/test_phase3e_replay_consent_sync.py` (17):
- replay reconstruct (no side effects), dry-run simulation, refuses auto
  side-effects (ValueError without authorize; RuntimeError even with authorize),
  execute with safe apply, partial failure reported, cancel.
- consent default-deny, grant+check, explicit deny wins, expiry+revoke, audit
  trail, export/import.
- sync filesystem round-trip, removable-media namespacing, LAN disabled by
  default (enabled+auth+encrypt works), merge union+tombstone, version-vector
  dominates.

## Verification
- `pytest`: 415 passed (was 398).
- `verify_runtime.py`: 46/46 pass (unchanged).

## Owner gates
- **[S] LAN transport**: registered, disabled by default, gated behind
  authenticate+encrypt. No escalation required — the capability is inert until
  explicitly enabled with the required security properties.
- No [B]/[L]/[C] triggers.

## Result
Replay, Consent, and Local Synchronization are now real, tested canonical
capabilities. Network transports remain gated. Ready for Phase 3F
(Autobiographical Memory).
