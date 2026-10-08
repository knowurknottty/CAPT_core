# CAPT Kanban R1 — verification and release boundary (2026-10-08)

## Frozen source

- CAPT Core tested/install source: `783f06bd15f185b2eeeea10c85f6e993a09237e8`.
- CAPT-Bot compatibility source: `2ebf4db8aaa0fcf10c85bcdc702d44251ef756c6`.
- Core tests/build executed from an isolated clean detached worktree,
  never packaging unrelated untracked main-checkout files.

## Actual tests and acceptance evidence

- Core Python: **1,970 passed, 70 skipped, 13 deselected**,
  `python -m pytest -q tests`, log
  `~/capt-node-workspace/kanban-r1-core-full-python.log`.
- Native Swift: **148 passed, 9 skipped, no failures**,
  `swift test --quiet`, log
  `~/capt-node-workspace/capt-kanban-missions-final.log`.
- Historical Bot suite: **333 passed, 8 skipped** via a **test-only**
  source import overlay against current Core. Not a real production R5
  integration or certification; log
  `~/capt-node-workspace/capt-bot-r5-compat-suite-filebacked.log`.
  An earlier fileless Python invocation could not spawn one test
  subprocess; rerunning via a file-backed runner passed.
- TIA on installed native app: opened **Kanban** and saw board, status
  lanes, Inspect/Continue; opened **Missions** and saw Open Kanban /
  Prepare continuation; activated continuation and confirmed new Chat
  was prefilled with authoritative task, mission, DriverRun and recovery
  constraints **without inference dispatch**.
- TIA on installed Bots: Create Bot button enabled after RuntimeService
  upgrade; governed form opened, then closed without registration.

## Daemon reconciliation and installation

- Authenticated checkpoint `cp-cmd-e6bc0017c40929ee` accepted before
  runtime stop/restart at ledger head sequence 22968.
- Upgraded resident RuntimeService via `capt stop`/`capt start`;
  reports **HEALTHY**, CAPT package **0.5.0**, checkpoint contract
  **0.1.0**, integrity **ok**, `register_bot` advertised.
- September 25 historical CAPT Core issue-resolution mission and its
  single task now have explicit durable `suspended` transitions,
  after proof of no DriverRun/ToolExecution bound to the stale task.
  No task was falsely marked complete or automatically retried.
- Local goal watchdog backed up, repaired to read exact RuntimeService
  states, and re-enabled. Observed
  `missionState=suspended`, `taskState=suspended`,
  `needsAttention=true`, reason `task_suspended`.
- Signed installed CAPT.app **0.5.0**; binary matched clean-release
  staging app, executable SHA256
  `7d840c4490b5001dbc2b1f2c4edd0e71f91183873a377348300af181279f48a8`.

## Explicit open release gates

- True **CAPT-Bot R5** production composition, single runtime/authority
  proofs, lifecycle activation/delegation and restart acceptance.
- **Kanban R2** durable collaboration notes, authenticated agent/cohort/
  vessel contributions, claims and optimistic task assignment, governed
  mutation, realtime event cursors and negative multi-actor security tests.
- GitHub issue intake to **one-at-a-time governed implement/test/PR/verify**
  with existing-work checks, effect idempotency and human approval gates.
- Live provider-backed verification/rejection, real Docker/Cloudflare,
  full accessibility/security/CI release matrix; current skips are not
  reclassified as passing live proofs.

**Disposition:** resident daemon and native Kanban R1 verified.
Neither full R5 nor unrestricted multi-actor Kanban are certified.
