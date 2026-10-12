# CAPT operator morning recovery — candidate v1

**One command (from a trusted physical Mac terminal):**

    /Users/knowurknot/CAPT_core/scripts/capt-refresh.zsh

This candidate currently lives only in the isolated RRDS worktree. Until promoted, test
the candidate using its own worktree path. Use \`python3 scripts/capt_recover.py --status\`
for read-only checks.

## Recovery state machine

1. Inspect the EXACT provisioned Node config and endpoint, then CONNECT to the socket.
   Socket-file existence alone is not readiness.
2. If the provisioned Node is unreachable, start that exact existing daemon. Never run
   \`init\`, delete a live socket, rewrite pairing, or replace node identity.
3. Read registered controller IDs and discover their EXISTING capability files.
   Verify file owner/mode. Renew only those existing capabilities by invoking
   the supported \`mcp-authorize\` command after one interactive confirmation.
4. Reprobe both native app RuntimeService profiles (\`~/.capt\` and
   \`~/.capt-inversion-labs\`) through authenticated Unix IPC. Token bytes never
   enter argv or diagnostic output.
5. Report separate states for Node service, controller renewals, native profile auth,
   client reattachment, and external OAuth. Never call a missing step successful.

## Fail-closed boundaries

- **A terminal confirmation is not Secure Enclave presence attestation.**
  Same-UID model processes may be able to drive a terminal or invoke the issuer
  directly. Before calling this A2-safe, require a separately authenticated
  operator ceremony implemented in the actual issuer (CAPT-UPG-041/043).
- No automatic HumanApproval issuance, model dispatch/replay, provider spend,
  token replacement, database open, or credential bootstrap.
- Never automatically restart a GUI containing unsent user work. The Swift
  desktop must reauthenticate its own runtime clients independently.
- Remote ChatGPT, Muse and other connector OAuth sessions are outside local
  CAPT Node's authority. If their identity providers require reauthorization,
  the operator must complete those provider-native flows.
- Do not copy capability contents into reports or prompts.
- Negative results are blockers with remedial steps, not grounds to widen scope.

## Production criteria remaining

- Hardware-bound human presence and issuer-enforced limited renewal scope.
- Source-pinned signed/installed launcher and launchd lifecycle specification.
- Multi-profile reconnect/read-back receipts for macOS native app, MCP clients,
  Inversion Commander, and Muse where supported.
- Integration tests covering missing daemon, expired grants, stale sockets,
  expired approvals, network policy drift, and failed rotations.
- Clear developer UX for any unrenewable OAuth/authorization and recovery
  rollback after partial failure.

This is a candidate, not a certified universal refresh solution.
