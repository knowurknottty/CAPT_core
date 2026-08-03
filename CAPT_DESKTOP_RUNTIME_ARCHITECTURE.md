# CAPT Desktop Runtime — Architecture Specification

Authoritative SHA: `sha1:6b3f769cc1042428d758aade443cc6009ce6a2b9`.
This document specifies the M0 vertical slice only. Later milestones follow
the workflow roadmap.

## 1. Topology (recommended default, adopted)

```
CAPT Desktop application (untrusted operator surface)
    │  authenticated local IPC (Unix domain socket + session token)
    ▼
CAPT Runtime service/process (authoritative)
    │  RuntimeService + EventStore (single SQLite ledger)
    ▼
Authoritative aggregates, drivers, evidence, verification, ClaimGuard,
events, checkpoints, replay
        │
External execution drivers (reference / Hermes) → untrusted observations
```

The desktop projects CAPT state, issues typed read queries, and presents
approvals (M2). It does **not** directly mutate CAPT databases or aggregates.

## 2. Key decisions (Gate 3)

### 2.1 Native SwiftUI/AppKit vs web-wrapper vs existing shell
- **Selected**: Python desktop application with a Tk (Aqua) GUI view.
- **Alternatives considered**: SwiftUI (requires Xcode/macOS SDK; cannot be
  verified headless on this build box), Electron/web-wrapper (heavier,
  premature), existing shell (none existed).
- **Evidence**: no existing desktop code (Gap Analysis A/B); Tk is available
  and produces a real native macOS window; the client/projection/IPC logic is
  framework-agnostic and fully testable headless.
- **Trade-offs**: Tk is less "native-looking" than SwiftUI; acceptable for M0.
- **Reversal condition**: if a native SwiftUI shell is required for
  distribution/notarization, swap only `desktop_app.py`'s view layer; the
  client (`desktop_runtime_client.py`), IPC contract, and runtime service are
  unchanged.
- **Migration implication**: none for authority boundaries.

### 2.2 Desktop process vs runtime process ownership
- **Selected**: separate processes. The runtime service owns the ledger and
  is the single authority. The desktop is a separate, untrusted client
  process.
- **Evidence**: `capt_runtime` `EventStore` is single-writer SQLite; the
  desktop never opens the ledger file. All reads go through the service's IPC.
- **Trade-offs**: one extra process; clear authority boundary.
- **Reversal**: none planned.

### 2.3 IPC transport and authentication
- **Selected**: Unix domain socket (local only) with a 4-byte length-prefixed
  JSON framing. Authentication: a per-start 256-bit session token written to a
  `0600` file; the client must present it as the first frame or the connection
  is dropped.
- **Evidence**: `capt_runtime_service.py` `serve()` generates
  `secrets.token_hex(32)`, stores it `0600`, and `handle_conn` rejects any
  first frame whose token mismatches. Acceptance test
  `test_unauthenticated_ipc_rejected` confirms rejection.
- **Trade-offs**: local-only (no remote); sufficient for M0 single-host.
- **Reversal**: for cross-host, replace transport with an authenticated
  mutually-TLS channel; the query/response contract is transport-independent.

### 2.4 Query/read-model strategy
- **Selected**: server-side read queries (`identity`, `list_aggregates`,
  `get_state`, `get_stream_events`, `event_timeline`, `claimguard`,
  `verification`). The desktop builds projections from these responses.
- **Evidence**: `RuntimeQueryService.handle` enumerates ops; the desktop
  `project_mission_view` composes them. No aggregate-mutation API is exposed
  to the desktop in M0.
- **Trade-offs**: read-only M0; mutations (M1/M2) will add explicitly
  governed command ops.

### 2.5 State projection and invalidation
- **Selected**: pull-based projection; the desktop re-reads on Connect/Refresh.
  No server push in M0. View digest (sha256 of the composed projection) is used
  to prove reconnect reconstructs identical state.
- **Evidence**: acceptance asserts `view1Digest == view2Digest` and
  `headSequence` stable across disconnect/reconnect.

### 2.6 Secrets handling
- **Selected**: session token in a `0600` file, never logged, never sent over
  the ledger. No credentials are read by the desktop.
- **Evidence**: `os.chmod(tf, 0o600)`; token file path passed on the command
  line only; acceptance stdout contains no token.

### 2.7 Artifact access
- **Selected**: the desktop references artifact digests/summaries returned by
  the verification query; it does not read the artifact file directly from the
  runtime's staging area in M0.
- **Trade-offs**: M3 may add a governed artifact-fetch op.

### 2.8 Version compatibility
- **Selected**: the desktop displays `runtimeVersion` and
  `contractSchemaVersion` (both `1.0.0` at M0). The IPC query contract is
  versioned implicitly by the runtime; a mismatch would surface as a query
  error, not a silent decode.
- **Evidence**: `identity()` returns both versions; acceptance asserts
  `contractSchemaVersion == "1.0.0"`.

### 2.9 Initial packaging boundary
- **Selected**: M0 is a runnable Python app (`desktop_app.py`) launched against
  a runtime service process. No `.app` bundle, signing, or notarization in M0.
- **Non-goal**: distribution, signing, notarization (explicitly excluded).

### 2.10 Future cross-platform strategy
- **Selected**: no premature abstraction. The IPC query contract and client
  are platform-independent; only the view layer is platform-specific. A future
  Windows/Linux port reuses the client + service unchanged and supplies a
  platform view.

## 3. Process / deployment topology

```
launch desktop_app.py
   └─ connect to runtime.sock (token auth)
        └─ runtime service (capt_runtime_service.py)
             ├─ EventStore (runtime.db)  ← authoritative
             ├─ RuntimeService (commands)
             └─ RuntimeQueryService (read queries)
```
The runtime service is started independently (or by an operator) with
`--seed` to create the read-only demo mission. The desktop attaches.

## 4. Command / event flow (M0, read-only)

```
Desktop ──IPC(op:identity)────────────► Runtime ──EventStore.head_chain()──► ok
Desktop ──IPC(op:get_state,mission-*)─► Runtime ──load_state()────────────► state
Desktop ──IPC(op:event_timeline)─────► Runtime ──read_events()───────────► events
Desktop ──IPC(op:claimguard)──────────► Runtime ──guard_claim()───────────► verdict
Desktop ──IPC(op:verification)────────► Runtime ──build_verification_result()─► result
```
No `RuntimeService` mutation command is invoked by the desktop in M0.

## 5. Approval flow
Not in M0. M2 will add a governed `propose_*` command path with signed
operator decisions; the desktop will present the request and forward an
explicit approval/denial, never auto-promoting.

## 6. Evidence / verification / ClaimGuard flow
- Evidence: the reference-driver read-only proof produces an observation +
  artifact; `build_verification_result` (CAPT-authored, `trust:
  capt_authoritative`) verifies repository-unchanged / no-git-mutation /
  artifact-present.
- ClaimGuard: the demo claim statement is checked by `guard_claim`; the
  desktop queries the disposition (`claimguard` op) and displays
  accepted/rejected. The desktop cannot promote a claim.

## 7. Checkpoint / replay flow
- The server creates `cp-desktop-m0` after seeding. Gate0 proved
  checkpoint/replay equivalence on the same store. The desktop reads the
  resulting authoritative state; reconnect reconstructs the identical view.

## 8. Reconnect / recovery flow
- Desktop disconnects (process exit or button). Runtime keeps the ledger.
  Desktop relaunches, reconnects with the same token, re-reads. Acceptance
  proves the view digest is identical and the ledger head is unchanged → no
  duplicate execution, no mutation from rendering.
