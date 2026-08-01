# Final Bridge Release Audit

## Final architecture

The CAPT Bootstrap Bridge is a launcher + authority gate. It does NOT re-implement
CAPT: it launches the canonical `CAPTRuntime` (one composition root, exported from
`capt_solo.api`), verifies a READY handshake over an authenticated AF_UNIX socket,
then routes governed turns to the already-running runner over a second
authenticated AF_UNIX socket. Hermes may host the middleware seam but CAPT owns
every governed turn after a validated ownership transfer (`EXACTLY_ONE_PROVIDER_OWNER`).

## Final identity model

- `runtime_id` — assigned by the bridge at launch (32-byte hex), stable for the
  process lifetime, passed to the runner via `CAPT_BRIDGE_RUNTIME_ID`.
- `runtime_generation` — starts at 1, increments on each new lease acquisition for
  the same mission; used for fencing/stale detection.
- `fencing_token` — UUID per lease acquisition; higher generation (or same
  generation + higher token) fences a lower lease.
- `session_id` — CAPT's durable session identity, recovered from integrity-bound
  continuity metadata (never from an untrusted sidecar).
- `mission_id` — binds lease, continuity metadata, and checkpoint.
- `checkpoint_id` — CAPT's canonical checkpoint; continuity metadata references its
  digest.
- `request_id` / `nonce` — per-turn replay protection.
- `provider_owner` — one of `HERMES_BEFORE_BRIDGE`, `CAPT_AGENT_RUNNER_AFTER_READY`,
  `NONE_WHEN_BLOCKED`.

## Final threat model

Local unprivileged process on the same host, able to discover and connect to the
bridge's AF_UNIX sockets, send crafted/replayed requests, kill/SIGKILL the runner,
and reuse PIDs. Mitigations: authenticated turn + shutdown (hmac, runtime-scoped
token via env only), replay set, request-size bounds, atomic lease with fencing,
integrity-bound continuity metadata, per-turn ownership receipts, fail-closed on
any unauthenticated/invalid/stale/missing/corrupted state.

## Final protocol

`TurnEnvelope{protocol_version, runtime_id, runtime_generation, request_id, nonce,
auth, op, payload}` over AF_UNIX. Server validates: structural shape → auth token
(hmac.compare_digest) → runtime identity/generation → replay → op. Responses carry
a `TurnReceipt` with `provider_owner=CAPT_AGENT_RUNNER` and a `receipt_digest`.

## Final locking / fencing design

`RuntimeLease` acquired atomically via `O_CREAT|O_EXCL` + rename. Fields:
mission_id, session_id, runtime_id, runtime_generation, fencing_token, pid, pgid,
hostname, created_at, last_heartbeat, schema_version. Stale recovery requires dead
PID OR expired heartbeat on this host. `fences()` proves split-brain protection.
Release verifies ownership before unlink.

## Final continuity design

`ContinuityMetadata` (schema_version=1): mission_id, session_id, checkpoint_id,
runtime_id, runtime_generation, previous_generation, checkpoint_digest,
fencing_token, metadata_digest, timestamps. Atomic write (temp+fsync+rename),
private dir/file modes, integrity digest, mission + checkpoint binding, rollback
rejection, legacy `.sid` migration. Authority remains in CAPT; the bridge metadata
references and validates the canonical checkpoint.

## Final test results

- `test_runtime_composition.py` + `test_model_task.py` + `test_model_task_acceptance.py`: 28 passed
- `test_bridge_bootstrap.py`: 62 passed
- `test_bridge_adversarial.py`: 28 passed (all 28 required scenarios)
- `acceptance_bridge.py`: 3 scenarios passed (success/failure/ownership-denial)
- Full suite: 864 passed, 20 failed (all 20 in `test_v04_cli.py`, pre-existing,
  OUT OF SCOPE — see limitations)

## CI links / run identifiers

- Workflow: `.github/workflows/release-security.yml` (Python 3.10 + 3.12 matrix).
- Local equivalents executed: `compileall` (clean), `build` (wheel
  `capt_solo-0.5.0-py3-none-any.whl`, sha256=7d2ffe89dce6a2297982937034af1242a6390b263b726ee56f09fa0fd6a18477),
  installed-wheel smoke test (clean venv, all imports resolve), secret scan (clean),
  absolute-path scan (clean), `git diff --check` (clean).
- Exact final commit SHA: **3e3ffa9d1abbb6d5f6bdab0d56f67cbb2caf940a**

## Known limitations

1. 20 pre-existing `test_v04_cli.py` failures (v0.4 foundry CLI uses `mgr._eng`,
   absent on v0.5 `CAPTRuntime`). Out of scope for this reconciliation; blocks the
   CI enforce-test-suite gate. No `_eng` compatibility alias added (mission forbids
   concealing missing architecture).
2. Lease heartbeat refreshed only at acquisition; stale recovery uses PID liveness
   + 30s window.
3. Live turn requires a CAPT provider; without one the turn fails closed (no
   Hermes fallback) and produces no model text in CI.

## Rollback procedure

- The branch is additive: it re-exports the existing `CAPTRuntime` and adds new
  bridge modules. Rollback = `git revert` the three recursion commits
  (40e6fdf, 9bd8466, 3e3ffa9) or reset the branch to the base merge
  (78c8e12 / 648f581). No destructive history was created; no force-push used.

## Merge recommendation

**MERGE_BLOCKED.** The 14 listed defects are fully remediated and proven. The
branch cannot pass the CI enforce-test-suite gate because of 20 pre-existing,
out-of-scope `test_v04_cli.py` failures. Resolve those (separate foundry-CLI
compatibility PR) or have the owner scope them out of the merge gate before
merging to `release/capt-v05-layer-reconciliation`.
