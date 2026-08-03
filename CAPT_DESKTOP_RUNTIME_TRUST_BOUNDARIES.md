# CAPT Desktop Runtime — Trust Boundaries

Authoritative SHA: `sha1:6b3f769cc1042428d758aade443cc6009ce6a2b9`.

## Boundary 1 — Desktop is untrusted; CAPT is authoritative

| Concern | Owner | Rule |
|---|---|---|
| missions, tasks, policies | CAPT `RuntimeService` | desktop issues no create/transition in M0 |
| capabilities, leases | CAPT `CapabilityAggregate` | desktop reads only |
| drivers, evidence, verification | CAPT `DriverHost`/`verification` | desktop reads results |
| ClaimGuard decisions | CAPT `guard_claim` | desktop queries disposition; never promotes |
| events, checkpoints, replay | CAPT `EventStore` | desktop reads; never writes |
| memory / context contracts | CAPT (M3) | not in M0 |

The desktop never opens the ledger SQLite file. All access is via the
runtime service IPC, which exposes **read queries only** in M0.

## Boundary 2 — IPC authentication

- Transport: Unix domain socket (local).
- Auth: per-start 256-bit token in a `0600` file. The client must send the
  token as the first framed message; any mismatch → connection closed with
  `{"ok": false, "error": "unauthenticated"}`.
- No token is logged. The token file is created with `os.chmod(0o600)`.
- Adversarial coverage: `test_unauthenticated_ipc_rejected` asserts a wrong
  token is refused.

## Boundary 3 — No duplicate authority / second source of truth

- The desktop holds no CAPT aggregate state. Its projections are derived
  read models, recomputed on each connect/refresh from authoritative data.
- Reconnect reconstructs the same view (proven by equal view digests); the
  desktop cannot "remember" authoritative state across restarts except by
  re-reading the runtime.

## Boundary 4 — Driver output is untrusted until verified

- The demo mission's DriverRun is produced by the reference driver through
  `DriverHost` (the same frozen, proven path as PR #29). The driver output is
  ingested as an untrusted observation; CAPT's `build_verification_result`
  independently verifies it (`trust: capt_authoritative`). The desktop only
  displays the CAPT-authored verification result, never the raw driver text as
  authoritative state.

## Boundary 5 — Read-only lease enforcement

- The demo lease uses read-only operations only (`repository.read`,
  `filesystem.read`, `artifact.create`, `analysis.execute`). `verify_lease`
  (called inside `DriverHost.dispatch`) rejects any write/git operation before
  any external call. The desktop cannot widen the lease.

## Boundary 6 — Secrets / logs

- No credentials are read by the desktop. The session token is local and
  `0600`. Acceptance evidence files contain no token (verified: the token is
  written to a temp file, not echoed).
- The runtime service logs only `CAPT_RUNTIME_SERVICE_READY` and fatal errors
  to stdout; no secret material is printed.

## Boundary 7 — Path / symlink scope

- The lease scope `rootPath` is an absolute, normalized path
  (`/tmp/capt-desktop-m0-demo-worktree`); `verify_lease` checks
  `allowedPaths` and rejects paths outside scope. The desktop cannot redirect
  the runtime to an arbitrary path in M0 (it issues no commands).

## What the desktop MAY do
- Connect (with token), read projections, render panels, disconnect, reconnect,
  refresh.

## What the desktop MUST NOT do (enforced)
- Open the ledger file; call `RuntimeService` mutation commands; promote a
  claim; forge an event; widen a capability scope; bypass IPC auth.
