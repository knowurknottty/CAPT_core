# CAPT Desktop Runtime — Recovery Report

Status vocabulary used below follows the authoritative workflow
(`workflows/CAPT_DESKTOP_RUNTIME_TRIPLE_RECURSION_BUILD_WORKFLOW.md`, commit
`sha1:c98a8be68ffd89d34f28731c3c4a933f89ed1ae0`): Confirmed locally at exact SHA,
Absent, Implemented but disconnected, Partial, Planned, Deferred, Unclear,
Historical evidence.

## 1. Repository identity

| Field | Value |
|---|---|
| Implementation repo | `/Users/knowurknot/CAPT_core` |
| Remote | `https://github.com/knowurknottty/CAPT_core.git` |
| Branch | `main` |
| HEAD SHA | `sha1:6b3f769cc1042428d758aade443cc6009ce6a2b9` |
| Tag `capt-runtime-m0` | present |
| Worktree status | clean before this work (new `desktop/` + 1 test file untracked) |
| Toolchain | python3.12.13 (also 3.9.6/3.10/3.14 available); pytest 9.1.1; swift/xcodebuild present; node v22.22.2 |
| Treasure Chest (instructions only) | `/Users/knowurknot/captstreasurechest`, remote `knowurknottty/captstreasurechest.git`, branch `workflow/capt-desktop-runtime-triple-recursion` fetched, workflow file confirmed at `c98a8be…` |

Rejected as implementation sources (per workflow): Homebrew bioCAPT,
`Biocapt-ecosystem-fullcaptlang`, `captrys`, unrelated prototypes. None used.

## 2. CAPT runtime source (authoritative)

| Component | Path | Status |
|---|---|---|
| `capt_runtime` package | `capt_runtime/` | Confirmed locally at exact SHA |
| Event ledger / store | `capt_runtime/store.py` | Confirmed locally at exact SHA |
| Checkpoint / replay | `capt_runtime/checkpoint.py`, `capt_runtime/replay.py` | Confirmed locally at exact SHA |
| ClaimGuard + verification | `capt_runtime/verification.py` | Confirmed locally at exact SHA |
| DriverRegistry / DriverHost | `capt_runtime/drivers/registry.py`, `capt_runtime/driver_host.py` | Confirmed locally at exact SHA |
| Reference driver | `capt_runtime/drivers/openharness.py` | Confirmed locally at exact SHA |
| Hermes driver | `capt_runtime/drivers/hermes.py` | Confirmed locally at exact SHA (executable present) |
| Runtime service (command surface) | `capt_runtime/services.py` | Confirmed locally at exact SHA |
| Generated contracts | `contracts/generated/python`, `contracts/generated/typescript` | Confirmed locally at exact SHA; drift clean |
| Contract drift tool | `contracts/tools/check_drift.py` | Confirmed locally at exact SHA |

## 3. Existing desktop code

| Component | Status | Evidence |
|---|---|---|
| macOS app (SwiftUI/AppKit) | Absent | `find` for `*.swift`, `*.xcodeproj`, `*.app` returned nothing in `CAPT_core` |
| TypeScript/web shell | Absent as an app | only `contracts/generated/typescript/package.json` (binding, not an app) |
| Desktop services / IPC | Absent | no IPC/server code outside this new `desktop/` work |
| CLI | Partial | `capt_runtime` is a library; no desktop CLI operator surface existed |
| Local daemon/runtime startup | Absent | no runtime service process existed prior to this work |
| Menu-bar / window applications | Absent | none found |
| Existing launch/build/package scripts | Absent | none found for desktop |

Conclusion: **no pre-existing desktop component** in CAPT_core. The desktop
vertical slice is built fresh under `desktop/` as a delivery/operator surface
over the authoritative runtime.

## 4. Runtime activation proof (Gate 0)

Run: `python3.12 desktop/gate0_activation.py` → `CAPT_RUNTIME_ACTIVE`.
Evidence: `desktop/gate0_evidence.json` (HEAD `6b3f769…`). All 10 required
smokes pass: imports resolve from the worktree, generated contracts available,
event-ledger smoke, checkpoint/replay smoke, ClaimGuard reachable (bounded
accepted + overclaim rejected), verification reachable, DriverRegistry/Host
reachable, reference-driver smoke (`oh-dr-g0`), Hermes driver available
(`Hermes Agent v0.19.1 … upstream dae5df22`), contract drift clean (11 files
match). `capt_runtime` test suite: **136 passed** at this point (141 after the
5 new desktop tests were added).

## 5. Subsystem map (reuse disposition)

| Subsystem | Status | Reuse disposition |
|---|---|---|
| `capt_runtime` aggregates/store | Confirmed locally at exact SHA | reuse directly (authority owner) |
| `RuntimeService` command surface | Confirmed locally at exact SHA | reuse directly (server wraps it) |
| `DriverHost` + reference driver | Confirmed locally at exact SHA | reuse directly (server seeds demo proof) |
| `EventStore` read API | Confirmed locally at exact SHA | reuse directly (client reads via IPC) |
| ClaimGuard / verification | Confirmed locally at exact SHA | reuse directly (server exposes as queries) |
| Generated Python/TS contracts | Confirmed locally at exact SHA | reuse for client typing/bindings |
| Desktop app / IPC / projections | Absent → built new | new, minimal, authority-preserving |

No functioning component was rewritten merely to normalize naming. The desktop
is additive and does not modify any `capt_runtime` module.
