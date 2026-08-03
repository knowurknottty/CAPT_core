# CAPT Desktop Runtime — Gap Analysis

Canonical desktop function taxonomy is taken from the authoritative workflow
Gate 2. Each function is classified against the recovered CAPT_core at HEAD
`sha1:6b3f769cc1042428d758aade443cc6009ce6a2b9`.

Classification legend: existing+connected, existing but disconnected, partial,
absent, inappropriate, deferred.

## A. Application shell
- application lifecycle — **absent** (built: `desktop_app.py` + `capt_runtime_service.py`)
- windows / scene restoration — **absent** (built: single-window Tk view)
- navigation — **absent** (built: Connect/Refresh/Disconnect)
- settings — **deferred** (M0 hard-codes local socket/token paths)
- menus/commands — **absent** (built: 3 control buttons)
- keyboard shortcuts — **absent** (deferred)
- accessibility — **partial** (Tk native; not yet audited — see Verification)
- update/version display — **existing+connected** (runtime identity shown)
- crash recovery — **partial** (server owns state; client reconnects)

## B. Runtime connection
- local runtime discovery — **absent** (built: explicit `--sock`/`--token-file`)
- start/stop/attach — **absent** (built: service process; client attaches)
- authenticated IPC — **absent → built** (Unix socket + per-session token)
- connection health — **built** (identity.integrity == "ok")
- degraded mode — **deferred**
- reconnect — **built + proven** (acceptance: identical view digest)
- version compatibility — **built** (contract schema version displayed)
- runtime identity display — **built**

## C. Mission workspace
- create mission — **existing+connected** (server `RuntimeService.create_mission`; M0 desktop is read-only)
- inspect MissionSpec — **built** (projection)
- display TaskGraph — **built**
- pause/resume/cancel — **deferred** (M1)
- budget display — **partial** (lease budget present in scope)
- capability requests — **deferred** (M1)
- human approvals — **deferred** (M2)
- terminal-state evidence — **built** (event timeline + verification)

## D. Execution and drivers
- driver registry — **existing+connected** (`DriverRegistry`)
- driver selection — **existing+connected** (server seeds reference driver)
- DriverRun lifecycle — **built** (projection shows `completed`)
- progress — **deferred** (M1 streaming)
- cancellation — **deferred** (M2)
- reconciliation — **existing+connected** (`reconciliation.py`; not surfaced in M0)
- driver health — **deferred**
- reference/Hermes swap visibility — **deferred** (M1)

## E. Context and memory
- ContextSlice inspection — **existing+connected** (server builds it for proof)
- provenance — **partial** (event ledger + chain digest)
- sensitivity/consent — **deferred**
- memory query display — **deferred** (M3)
- no direct UI mutation of memory — **built** (desktop is read-only)

## F. Evidence and claims
- observations — **existing+connected** (driver output ingested)
- evidence records — **partial** (verification checks surfaced)
- verification status — **built** (`verified`, `capt_authoritative`)
- ClaimGuard decisions — **built** (disposition query)
- accepted/qualified/rejected/unresolved — **partial** (proposed claim shown)
- artifact hashes — **built** (artifact digest in verification)
- source linking — **partial**
- execution receipts — **deferred**

## G. Events and replay
- event timeline — **built**
- correlation/causation — **partial** (correlationId present)
- checkpoints — **existing+connected** (server creates `cp-desktop-m0`)
- replay status — **existing+connected** (Gate0 replay smoke)
- state-digest comparison — **built** (view digest equality across reconnect)
- failure classification — **deferred**
- exportable evidence bundles — **deferred** (M3)

## H. Tools and capabilities
- tool inventory — **deferred**
- capability grants/leases — **built** (grant + lease projection)
- scope/expiration — **built**
- approval UX — **deferred** (M2)
- denial reasons — **deferred**
- side-effect classification — **built** (read-only lease ops)
- no prompt-based authority bypass — **built** (desktop issues no commands)

## I. Operator and developer surfaces
- logs — **partial** (service stdout; acceptance stdout captured)
- traces — **deferred**
- metrics — **deferred**
- runtime diagnostics — **built** (identity + integrity)
- schema/version display — **built**
- test/acceptance evidence — **built** (`acceptance_m0_evidence.json`)
- safe developer mode — **deferred**
- no secret exposure — **built** (token in 0600 file; never logged)

## J. Project surfaces
- Workspace MCP / Project SEAL / Knowledge Bubbles — **deferred** (out of M0 scope)

## Duplicated-state / authority risks
- Risk: desktop becoming a second authority. Mitigation: desktop issues **no**
  mutations; CAPT owns all aggregates. The desktop is a read/projection surface
  over an authenticated IPC read API. (See TRUST_BOUNDARIES.)
- Risk: framework lock-in. Mitigation: client/projection/IPC are
  framework-agnostic; the GUI view is a thin Tk layer swappable for SwiftUI
  without touching contracts (see ARCHITECTURE ADR).
- Risk: schema mismatch. Mitigation: generated contracts used; drift check clean.
