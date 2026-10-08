# CAPT Core — Current State

This is the concise public status source for the repository. It separates package version, merged source state, exact-head engineering evidence, release-security authorization, and independent work.

Snapshot date: **2026-10-08**. Reconciled source HEAD: `80d3b82` (media R2C attestation). Governed execution evidence for this snapshot was harvested on the operator Mac under CAPT Node (see §3).

## Truth classes

### 1. Numbered package release

`pyproject.toml` still declares **`capt-solo 0.5.0`**. Preserved evidence under `release_evidence/v0.5/` applies to that historical release lineage only.

### 2. Merged `main`

The pinned source contains the August convergence and subsequent merged work:

- **PR #117** — terminal native/provider/UPG/MCP convergence, merge `4a654a74083cf341f8557983ce256949198a02e7`;
- **PR #126** — governed ToolBroker and durable ToolExecution with local, SSH, Docker, file, and code adapters, squash merge `bcfdff9d43b35b5b192cc998b68ce16cc73b9985`;
- **PR #128** — exact-byte convergence of the owner-approved public-release design and executable plans onto current Core, merge `54ac314294fb456cb2d9089615996b31dfeca753`; this is documentation authority, not implementation completion;
- **PR #129** — governed managed authored skills R1, merge `3aee7370bac880aed99ce3c9ecfaa6d9ff48101e`.

- **PR #146** — CAPT-UPG-020→024 benchmark/probe and cognitive-debt convergence, merge `cefc885`; empirical effectiveness and provider-cache claims remain separate proof obligations.
- **PR #148** — native macOS control center, Prompt Intelligence proposals/approval binding, and model/tool authority work, merge `5709380`; semantic operator-control API subsequently merged at `42a6cd2`, with revision/digest-bound configuration and prompt selection subordinate to RuntimeService/EventStore.
- **PR #153** — Model Council alpha, merge `542f820`: tier geometry, logical Vessel expansion, launch interlocks, dissent-preserving analysis, durable admission/replay/checkpoints, and read-only Chamber projection; live provider execution, native Council GUI, and release proof remain separate.
- **PR #155** — hardening tiers 1–5, merge `5812a0c`: read projections, mission/DriverRun authority gates, identity-refusal auditing, honest absent-context provenance, and explicit unshipped labels for `context_pipeline` / `context_merkle`.
- **PR #156** — SOMA M0 contract closure, merge `4f1c0a1`: trajectory/reducer contracts, compression receipts, and local benchmark/reconstruction primitives; this does not establish live runtime integration or competition readiness.
- **`d33a5e4`** — native model-answer rendering separated from the execution receipt, with retained disclosure/persistence of execution details.
- **`1e85bac`** — expands AUTO routing signals to include list/match and other actionable requests; the four-word minimum and operator-selected engine/mode still apply. This is routing, not proof of a Search/Deep Research product surface.
- **PR #169** — durable Model Council + per-boundary provider dispatch accounting, merge `f5aef2f` (feature `abfd658`): durable council receipts, provider request/cost accounting at the dispatch boundary, and reconciliation classification (`request_started`/`response_started` → `retry_forbidden`; never blind-replay lost or ambiguous runs).
- **Media R2A→R2C** — governed media execution: `1da2fa5` R2A governed execution + durable video jobs; `d2ee83d` Gemini PDF/video inline + allowlisted image-URL outputs; `bfcfd4b` Gemini Files upload with separate model-reference approval; `80d3b82` R2C installed/offline two-approval acceptance attestation.

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

Historical August 27 audit: `3aee737…` had a mixed M0-A push run (`32958741310`): Python 3.12, contract drift, and TypeScript parity passed; Python 3.10 failed during the Docker availability probe. A retry was recorded by that audit; no retry outcome or current-HEAD CI result is established here. This is historical evidence, not status for `1e85bac…`.

Governed local evidence at `80d3b82` (CAPT Node operations on the operator Mac, 2026-10-08): full `tests/capt_runtime` suite **1435 passed / 13 skipped / 12 deselected**; UPG probe suites **33/33** unit tests plus `scripts/upgrade_probe_suite.py` **exit 0** (810 KB `CAPTUpgradeProbeEvidence`; all cache/semantic-equivalence claim boundaries remain `false`). This is exact-head engineering evidence, not a release-security receipt.

A descendant of an authorized SHA is not automatically release-security authorized. Final public artifacts must be rebuilt and re-hashed from the exact source commit selected for release, with signing/notarization/distribution evidence handled separately.

### 4. Merged upgrade and product-plan boundaries

CAPT-UPG-020→024 source was reconciled into Core through **PR #146 (`cefc885`)**. The earlier #89/#91/#93/#95/#97 lane is historical implementation lineage, not a list of pending Core merges.

- CAPT-UPG-020: reciprocal-review scorer/harness; empirical effectiveness requires observed trial evidence.
- CAPT-UPG-021: read-only sparse symbol index over Discovery/SEAL-admitted candidates; real-repository performance requires benchmark evidence.
- CAPT-UPG-022: Tree-sitter structural-hash probe; grammar/runtime and semantic-equivalence claims are separate.
- CAPT-UPG-023: chunk-stability/FastCDC probe; chunk reuse does not prove provider prefix-cache reuse.
- CAPT-UPG-024: cognitive-debt projection and `capt-debt` surface; absence of reported debt does not prove correctness.

The former Inversion Labs/Forge PR line is not an open Core-main queue. It remains a separate edition/history lineage; for example #104 is closed unmerged and #119 merged into its separate Labs integration base, not Core `main`.

The owner-approved public-release design (#111) and plans (#116) were preserved on current `main` through PR #128. Secure Intake/Quarantine, Projects, the full human-first results layer, composer context palette, and Search/Deep Research product governance remain plans unless separately proven in source. Model Council alpha is merged via #153; native answer/receipt separation is present at `d33a5e4`. Neither closes the entire public-release plan.

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

`CAPTNativeMac` is a merged Swift application target with governed chat, approvals, runtime/provider controls, session persistence, authored-skill visibility, and cross-surface test source. Historical build/test results in [`DESKTOP.md`](DESKTOP.md) do not establish a build of this HEAD or a signed/notarized/distributed public release.

## Authority invariant

The governed runtime path is shown below. The standalone `capt memory` commands use the local CAPT Solo MemoryEngine directly; their success does not establish EventStore admission or model continuation.

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
