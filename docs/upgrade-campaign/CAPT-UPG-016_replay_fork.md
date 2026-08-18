# CAPT-UPG-016: Point-in-Time Replay + Linear Replay Fork

- **Campaign ID**: `CAPT-UPG-016`
- **Issue**: #82
- **Branch**: `upgrade/capt-upg-016-replay-fork`
- **Disposition**: `IMPLEMENTED_PENDING_EXACT_HEAD_VERIFICATION`

## Implementation

`capt_runtime/replay_fork.py` adds a read-only layer around CAPT's existing pure replay reducer:

- `replay_at_sequence(store, sequence)` reconstructs authoritative aggregate state only through the requested global sequence;
- selected-prefix chain identity is recomputed from `GENESIS_CHAIN` using each event's payload digest and event id;
- `prepare_linear_fork()` creates a content-addressed `LinearReplayForkManifest` binding:
  - source ledger head at preparation;
  - selected global sequence;
  - selected prefix chain digest;
  - selected reconstructed state digest;
  - per-stream versions;
  - optional verified checkpoint identity;
  - optional requested continuation metadata;
- the manifest explicitly states that it does not rewrite history, is not authoritative runtime state, may not dispatch, may not mutate the source ledger, and requires a separate governed adoption step;
- `verify_linear_fork()` replays and rechecks the selected source prefix/state without rejecting later legitimate source-ledger appends.

No original EventStore history is truncated, copied into an alternative authority, or mutated by preparation/verification.

## Tests authored

`tests/capt_runtime/test_replay_fork.py` covers:

1. point-in-time replay excludes future events and leaves the source ledger unchanged;
2. fork preparation binds source prefix/state and survives later legal source appends;
3. manifest tampering and unavailable future sequences fail closed;
4. a checkpoint newer than the requested historical sequence is rejected.

## Verification boundary

No exact-head execution is available from the connected environment. No pytest PASS is claimed.

Minimum execution evidence:

```bash
pytest tests/capt_runtime/test_replay_fork.py
```

Before owner-ready integration, also rerun replay/checkpoint/conformance and full relevant runtime regression suites.
