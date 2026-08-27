# CAPT Core — Current State

This is the concise public status source for the repository. It separates package version, merged source state, exact-head engineering evidence, release-security authorization, and independent work.

Snapshot date: **2026-08-27**. Literal `main` at audit start: `3aee7370bac880aed99ce3c9ecfaa6d9ff48101e`.

## Truth classes

### 1. Numbered package release

`pyproject.toml` still declares **`capt-solo 0.5.0`**. Preserved evidence under `release_evidence/v0.5/` applies to that historical release lineage only.

### 2. Merged `main`

Current `main` contains the August 21 convergence plus three material later merges:

- **PR #117** — terminal native/provider/UPG/MCP convergence, merge `4a654a74083cf341f8557983ce256949198a02e7`;
- **PR #126** — governed ToolBroker and durable ToolExecution with local, SSH, Docker, file, and code adapters, squash merge `bcfdff9d43b35b5b192cc998b68ce16cc73b9985`;
- **PR #128** — exact-byte convergence of the owner-approved public-release design and executable plans onto current Core, merge `54ac314294fb456cb2d9089615996b31dfeca753`; this is documentation authority, not implementation completion;
- **PR #129** — governed managed authored skills R1, merge `3aee7370bac880aed99ce3c9ecfaa6d9ff48101e`.

Merged runtime capabilities therefore include:

- CAPT-UPG-001→019, exact historical replay/checkpoint corrections, durable Cohorts + steering, governed artifact promotion, lease controls, forensic/provenance/epistemic/security projections;
- authenticated RuntimeService/EventStore authority with governed provider execution and native macOS/MCP control surfaces;
- governed ToolBroker execution with durable effect/reconciliation state and bounded local/SSH/Docker terminal backends;
- pinned external authored-skill context plus managed-local Agent Skills import/verify, deterministic contextual selection, approval-time binding, and execution-time anti-drift checking;
- native approval visibility for selected authored skills.

Closed-unmerged historical PRs are not separate current authority merely because useful semantics once lived there.

### 3. Engineering evidence vs release-security authorization

Release/security evidence is **SHA-bound**.

Historical facts remain historical:

- merged PR #117 head `570babeef113943860c1268722200a48639e406d`: M0-A PASS, Native macOS Swift PASS, Release Security **FAIL** on run `32440329043`;
- release-security closure baseline `2199c036aa22af33fb3eb0700f63f820a35aa55a`: hosted Release Security run `32617740908` **PASS**, **21 PASS / 0 FAIL / 0 NOT_VERIFIED / 26 NOT_APPLICABLE**, and M0-A run `32617740848` PASS;
- ToolBroker PR #126 exact head `b21ed6e7ff3996d48c756e342b278b69af0d666f`: hosted M0-A and Release Security both PASS; its squash merge `bcfdff9…` is tree-identical but is a different commit SHA, so the PR-head security receipt is not relabeled as a merge-SHA receipt.

At audit start, literal `main` `3aee737…` had an M0-A push run where Python 3.12, contract drift, and TypeScript parity passed while Python 3.10 failed because the Docker-daemon availability probe timed out during test collection. That failed job was retried during this documentation audit; do not infer the retry result until the hosted run completes.

A descendant of an authorized SHA is not automatically release-security authorized. Final public artifacts must be rebuilt and re-hashed from the exact source commit selected for release, with signing/notarization/distribution evidence handled separately.

### 4. Independent work

The current open Core PR queue is the CAPT-UPG-020→024 benchmark/probe lane:

- #89 reciprocal-review benchmark;
- #91 sparse symbol-index probe;
- #93 Tree-sitter structural-hash probe;
- #95 FastCDC/content-defined chunk probe;
- #97 cognitive-debt cockpit.

The former Inversion Labs/Forge PR line is not an open Core-main queue. It remains a separate edition/history lineage; for example #104 is closed unmerged and #119 merged into its separate Labs integration base, not Core `main`.

The owner-approved public-release design (#111) and plans (#116) were preserved on current `main` through PR #128. Secure Intake/Quarantine, Projects, human-first results, composer context palette, Search/Deep Research governance, and Cohort Council remain implementation work unless separately proven in source.

See [`PR_TOPOLOGY.md`](PR_TOPOLOGY.md) for the routing map.

## Tool execution status

ToolBroker is merged. It models durable ToolExecution lifecycle and reconciliation separately from adapter effects and supports the initial terminal backends `local | ssh | docker`, plus governed file/code adapters.

Consequential effects remain capability/lease governed. If CAPT cannot prove the external dispatch/result boundary, reconciliation is required rather than blind redispatch.

## Authored-skill status

CAPT now has two governed authored-skill trust classes:

- `pinned_external` — immutable release-pinned packs such as `CAPT_Skills`;
- `managed_local` — imported, digest-bound local Agent Skills packs under the CAPT state root.

Explicit pinned selection outranks contextual managed-local auto-selection. Skills are context/guidance only: they do not grant filesystem, network, tool, provider, approval, or policy authority. See [`AUTHORED_SKILLS.md`](AUTHORED_SKILLS.md).

## Native macOS status

`CAPTNativeMac` is a real buildable Swift application target with governed chat, approvals, runtime/provider controls, session persistence, authored-skill visibility, and cross-surface tests. A source-buildable app is not the same evidence class as a signed/notarized/distributed public release.

## Authority invariant

```text
Operator surfaces
  CLI / TUI / native macOS / MCP compatibility clients
                |
                v
        authenticated RuntimeService
                |
       governance + EventStore
       memory/context + evidence
       DriverHost + ToolBroker
                |
                v
    replaceable models / bounded tools
```

No UI, MCP client, model, skill pack, Cohort projection, security checker, provider manager, prompt enhancer, or tool adapter becomes a parallel source of CAPT authority.
