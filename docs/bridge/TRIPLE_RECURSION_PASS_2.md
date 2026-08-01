# Triple Recursion — Pass 2: Harden Runtime Boundaries, IPC, Locking, Continuity, Ownership

## Threat model

The bootstrap bridge launches and verifies the canonical CAPT Agent Runner, then
routes governed turns to it over a local AF_UNIX socket. Before this pass the
turn channel was unauthenticated, the shutdown op was unauthenticated, the
duplicate-runner lock was a race-prone check-then-write PID file, and session
continuity lived in an unsigned plaintext `.sid` sidecar. Each of those is a
local privilege-escalation / spoofing surface: any local process could claim to
be the runner, issue turns, or trigger shutdown; a crashed runner could leave a
stale lock that blocks recovery or (worse) lets two runners own the same mission.

Assets in scope: the turn socket, the shutdown op, the runner lock/lease, the
continuity metadata, and the per-turn ownership receipt.

Adversary capabilities assumed: local unprivileged process on the same host,
able to connect to AF_UNIX sockets whose path it can discover, able to send
crafted or replayed requests, able to kill or SIGKILL the runner, able to reuse
a PID after the runner dies.

## IPC protocol

New module `capt_solo/bridge/protocol.py`:

- `TurnEnvelope` — authenticated request: `protocol_version`, `runtime_id`,
  `runtime_generation`, `request_id`, `nonce`, `auth`, `op` (`turn`/`shutdown`/
  `health`), `payload`. Parsed by `TurnEnvelope.from_mapping` with strict
  structural validation (missing field -> `TURN_MALFORMED`, non-object ->
  `TURN_MALFORMED`).
- `BridgeConnectionDescriptor` — issued by the launcher for the turn channel:
  runtime-scoped auth token (32-byte `secrets.token_hex`), socket path, issued/
  expires timestamps. The token is passed to the runner ONLY via the
  `CAPT_BRIDGE_TURN_AUTH` environment variable (never argv, never logs, never
  serialized into public bridge results).
- `TurnReceipt` — per-turn ownership proof (see below).
- `BridgeProtocolError` — carries a machine-readable `error` code
  (`TURN_MALFORMED`, `TURN_UNAUTHENTICATED`, `TURN_INVALID_AUTH`,
  `TURN_STALE_GENERATION`, `TURN_REPLAYED`, `TURN_OVERSIZED`) and message.

Server-side handling in `serve._handle_turn`:

- reads the request with a bounded loop (hard cap 256 KiB; oversized ->
  `TURN_OVERSIZED` after draining the body so the client never deadlocks);
- rejects missing auth (`auth == ""` -> `TURN_UNAUTHENTICATED`) and wrong auth
  (`hmac.compare_digest` -> `TURN_INVALID_AUTH`);
- rejects runtime identity / generation mismatch (`TURN_STALE_GENERATION`);
- rejects replayed `request_id` from a per-connection `seen` set
  (`TURN_REPLAYED`);
- authenticates `shutdown` with the same token;
- never leaks stack traces or tokens to the client.

## Locking / lease / fencing design

New module `capt_solo/bridge/lease.py` replaces the race-prone
check-then-write PID lock.

- `acquire_runner_lease` writes the lease atomically via
  `os.open(path, O_CREAT | O_EXCL | O_WRONLY, 0o600)` then renames a unique temp
  file into place (atomic on POSIX). `O_EXCL` makes concurrent acquisition by two
  processes fail closed with `DuplicateRunnerError`.
- Lease metadata (`RuntimeLease`): `mission_id`, `session_id`, `runtime_id`,
  `runtime_generation`, `fencing_token` (UUID per acquisition), `pid`, `pgid`,
  `hostname`, `created_at`, `last_heartbeat`, `schema_version`.
- Stale recovery: a lease is reclaimable only if EITHER the PID is not live on
  this host OR the heartbeat is older than `LEASE_TIMEOUT_S` (default 30s). A
  lease whose `hostname` differs is never reclaimed (PID reuse across hosts is
  not ours).
- Fencing: `RuntimeLease.fences(other)` returns True when this lease has a higher
  `runtime_generation` OR (same generation AND higher `fencing_token`
  lexicographically). A higher-generation lease fences a lower one, proving
  split-brain protection: a stale runner cannot write checkpoint state after a
  replacement has taken over.
- `release_runner_lease` verifies ownership (matching `runtime_id` +
  `fencing_token`) before unlinking; it does not delete a lock merely because
  its PID is not live.
- `read_held_lease` returns `None` on missing/corrupt lock (structured, not
  silent).

## Continuity metadata schema

New module `capt_solo/bridge/continuity.py` replaces the plaintext
`session-<mission>.sid` sidecar.

`ContinuityMetadata` (schema_version 1):

- `mission_id`, `session_id`, `checkpoint_id`, `runtime_id`,
- `runtime_generation`, `previous_generation`,
- `checkpoint_digest`, `fencing_token`, `metadata_digest`,
- `created_at`, `updated_at`.

Properties:

- atomic write: temp file + `fsync` + `os.replace` (rename); private dir (0o700)
  and file (0o600) modes;
- integrity: `metadata_digest = sha256(canonical_json(without digest))`;
  `load_continuity` recomputes and rejects `CONTINUITY_CORRUPTED` on mismatch;
- mission binding: internal `mission_id` must equal the requested mission
  (`CONTINUITY_MISSION_MISMATCH`);
- checkpoint binding: optional `expected_checkpoint_id` must match
  (`CONTINUITY_CHECKPOINT_MISMATCH`);
- generation tracking + rollback rejection (`CONTINUITY_ROLLBACK_DETECTED`);
- legacy `.sid` migration: a `session-<mission>.sid` file is read once, migrated
  into a `ContinuityMetadata`, and the legacy file removed;
- no silent read/write failure: `ContinuityError` carries a machine-readable
  `code`; missing vs corrupted are distinguished (`CONTINUITY_MISSING` vs
  `CONTINUITY_CORRUPTED`);
- authority stays in CAPT: the bridge metadata references and validates the
  canonical checkpoint digest; it does not replace the checkpoint body.

## Ownership receipt design

Every governed turn response (`serve._run_governed_turn`) returns a
`TurnReceipt` dict (not just a startup claim) proving the turn traversed CAPT
governance:

- `request_id`, `turn_id`, `mission_id`, `session_id`, `runtime_id`,
  `runtime_generation`, `provider_owner` (= `CAPT_AGENT_RUNNER`),
  `execution_mode` (= `GOVERNED`), `ctp_transaction_id`, `checkpoint_before`,
  `checkpoint_after`, `claim_supported`, `receipt_digest`
  (`sha256` over the authoritative fields).

The client (`turn.execute_governed_turn`) surfaces the receipt digest in the
bridge output so ownership is proven per turn, not only at startup.

## Adversarial tests

New file `tests/test_bridge_adversarial.py` — 28 tests covering all 28 required
scenarios (unauthenticated turn, invalid token, replay, stale generation,
unauthenticated shutdown, malformed, oversized, concurrent duplicate boot,
atomic acquisition, stale recovery, PID reuse, wrong fencing token, SIGKILL
recovery, corrupted metadata, missing metadata, legacy migration, mission
mismatch, checkpoint mismatch, rollback, failed atomic write, two processes same
session, stale runner fenced, per-turn receipt, provider failure without
fallback, deep-path socket overflow, unauthorized local client, authenticated
shutdown, interrupted-startup cleanup).

Key harness fix: `_exchange` runs the server handler in a concurrent thread so a
300 KiB request does not deadlock the synchronous in-process client (the client's
`sendall` blocks until the server reads, but the server cannot read until the
handler starts). Bounded 5s socket timeouts make any future deadlock fail fast.

## Test results

- `tests/test_bridge_adversarial.py`: 28 passed
- `tests/test_bridge_bootstrap.py`: 62 passed (updated lease tests)
- `tests/acceptance_bridge.py`: 3 scenarios passed (success/failure/ownership),
  including authenticated turn routing through the live runner.

## Unresolved risks

- The live-runner turn path depends on a CAPT provider being configured
  (`CAPT_MODEL_ENDPOINT`); without one the turn returns a structured
  `CAPT_AGENT_RUNNER` failure (no Hermes fallback) — correct, but the turn does
  not execute model text in CI without a model server.
- Lease heartbeat is written at acquisition only in this pass; a long-lived
  runner does not currently refresh `last_heartbeat` on an interval. Stale
  recovery therefore relies on PID liveness + the 30s window from acquisition.
  A heartbeat refresh thread is a Recursion-3 hardening candidate.
