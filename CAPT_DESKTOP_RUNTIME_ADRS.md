# CAPT Desktop Runtime — ADR Set (M0)

Authoritative SHA: `sha1:6b3f769cc1042428d758aade443cc6009ce6a2b9`.

## ADR-DT-001 — Desktop is a read/projection surface; CAPT retains all authority
- **Status**: accepted
- **Context**: The workflow forbids the desktop becoming a second source of
  truth or duplicating CAPT aggregates.
- **Decision**: The desktop issues no CAPT mutations in M0. All state access
  is via a runtime service IPC that exposes read queries only. CAPT
  (`RuntimeService` + `EventStore`) remains the single authority.
- **Consequences**: Simple authority story; M1/M2 add explicitly governed
  command paths. Reversible only by adding governed command ops (ADR-DT-005).
- **Evidence**: `capt_runtime_service.py` exposes only read `op`s;
  `test_read_only_does_not_advance_ledger` passes; acceptance asserts ledger
  head stable across reads.

## ADR-DT-002 — Separate runtime service process owns the ledger
- **Status**: accepted
- **Context**: `EventStore` is single-writer SQLite; the desktop must not open
  it.
- **Decision**: A dedicated runtime service process wraps `RuntimeService` +
  `EventStore` and serves the desktop over IPC. The desktop is a separate,
  untrusted client process.
- **Consequences**: Clear process boundary; one extra process. No shared
  mutable state between desktop and runtime except via the IPC contract.
- **Evidence**: `capt_runtime_service.py:serve()` owns `EventStore`; the
  desktop client never imports `EventStore` for writing.

## ADR-DT-003 — Local IPC: Unix domain socket + per-session token
- **Status**: accepted
- **Context**: Adversarial review requires authenticated IPC; no unauthenticated
  access.
- **Decision**: Unix domain socket (local-only) with 4-byte length-prefixed
  JSON framing; a 256-bit token in a `0600` file must be presented as the first
  frame.
- **Consequences**: Local-only (acceptable for M0 single-host). Cross-host
  needs a different authenticated transport; the query/response contract is
  transport-independent.
- **Evidence**: `serve()` generates `secrets.token_hex(32)`, `os.chmod(0o600)`;
  `test_unauthenticated_ipc_rejected` passes.

## ADR-DT-004 — Python/Tk view layer, framework-agnostic client
- **Status**: accepted
- **Context**: No existing desktop code; SwiftUI cannot be verified headless
  on the build box; premature cross-platform abstraction is excluded.
- **Decision**: The operator app is Python with a Tk (Aqua) GUI. The client
  (`desktop_runtime_client.py`), projections, and IPC contract are
  framework-agnostic and fully testable headless.
- **Consequences**: Tk is less "native" than SwiftUI; acceptable for M0. The
  view layer is swappable (e.g. for SwiftUI) without touching contracts.
- **Reversal condition**: if native SwiftUI is required for
  distribution/notarization, replace only `desktop_app.py`'s view; client +
  service unchanged.
- **Evidence**: `desktop_app.py` builds and runs headless
  (`run_headless`); GUI path uses Tk.

## ADR-DT-005 — Mutations deferred behind governed command ops (M1/M2)
- **Status**: accepted (forward-looking)
- **Context**: M0 is read-only; future milestones need create-mission,
  approvals, cancellation.
- **Decision**: Any desktop-originated mutation will be a new governed
  `RuntimeService` command invoked over IPC with explicit authority checks
  (per `authority.py`) and operator approval UX. No mutation path exists in M0.
- **Consequences**: Authority stays in CAPT; the desktop remains a thin
  command issuer, never a state owner.
- **Evidence**: M0 desktop code contains no `RuntimeService` mutation call.

## ADR-DT-006 — Demo mission seeded by CAPT, not the desktop
- **Status**: accepted
- **Context**: Gate 5 requires "create or select one read-only demonstration
  mission" without the desktop writing state.
- **Decision**: The runtime service seeds the demo mission server-side using
  the real `RuntimeService` + a real reference-driver read-only proof. The
  desktop only selects/displays it.
- **Consequences**: The desktop is provably read-only; the demo state is
  authoritative CAPT state.
- **Evidence**: `seed_demo_mission()` uses `RuntimeService`,
  `DriverHost` + `OpenHarnessDriver`; acceptance view shows
  `driverRun.state == "completed"` and `verification.status == "verified"`.
