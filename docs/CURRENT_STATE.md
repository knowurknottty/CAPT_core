# CAPT Core — Current State

This is the concise public status source for the repository. It intentionally separates the numbered package version, merged integration state, release authorization, and independent open work.

## Truth classes

### 1. Numbered package release

`pyproject.toml` still declares **`capt-solo 0.5.0`**. Preserved evidence under `release_evidence/v0.5/` applies to that historical release lineage only.

### 2. Merged integration `main`

The `main` baseline inspected for this reconciliation was `a6601d61fa5a807f2ba04ca4fda84bc8d42505b0`. Resolve the literal current `main` SHA from Git; this documentation merge itself will advance it. PR #117 was merged at merge commit `4a654a74083cf341f8557983ce256949198a02e7`; PR #45 then added the preserved DeepSeek/Ouroboros research record without changing runtime semantics.

PR #117's merged head was `570babeef113943860c1268722200a48639e406d`. The merge brought the formerly stacked Core implementation through UPG-019/native/provider convergence onto `main`, including:

- CAPT-UPG-001→019 and corrected exact historical replay/checkpoint semantics;
- bounded production IPC framing, rejection audit, state permissions, resource ceilings, and injection-assurance work;
- governed cross-model continuation/context binding and no-repeat recovery semantics;
- durable Cohort EventStore persistence, evidence admission, operator steering, Chamber projection, and stale-epoch/quorum semantics;
- governed artifact promotion, capability lease inspect/revoke, `.capt-flight`, provenance DAG, epistemic ladder, replay fork, and Security Closure Cockpit;
- first-class local OpenAI-compatible provider execution/prewarm and coherent provider/model persistence;
- native Swift `CAPTNativeMac` governed chat/operator source with session isolation, typed runtime projections, encrypted session cache, and origin-session-bound async updates;
- pinned authored-skill bytes bound into exact model-visible approval identity;
- macOS ↔ RuntimeService ↔ MCP shared-ledger acceptance.

Closed-unmerged PR #118 is not a separately merged authority; its provider/model-coherence semantics were reconciled into the #117 line before merge.

### 3. Engineering verification vs release authorization

The merged #117 head has mixed-but-truthful CI evidence:

- M0-A Contract & Runtime Proof: **PASS**;
- Native macOS Swift: **PASS**;
- Release Security: **FAIL** on run `32440329043` for exact head `570babeef113943860c1268722200a48639e406d`.

The prior detailed Security Closure Cockpit snapshot at `33e24146094242d7a88612cea39267ef52a1d2e1` recorded `releaseAuthorized=false` with **2 PASS / 0 FAIL / 19 NOT_VERIFIED / 26 NOT_APPLICABLE**. Those exact counts belong to that exact candidate head and are not silently relabeled as the merged head's gate result.

Therefore the current release posture remains:

`IMPLEMENTED_CROSS_SURFACE_VERIFIED_RELEASE_SECURITY_BLOCKED`

**Merged does not mean release-certified.** The public release remains blocked until the Security Closure Cockpit has legitimate exact-head evidence for every applicable release-blocking control, returns `releaseAuthorized=true`, and final release artifacts are rebuilt/re-hashed from that authorized source commit.

### 4. Separate open work

The following remain independent of the merged Core authority unless separately reconciled and merged:

- CAPT-UPG-020→024 benchmark/probe work: PRs #89, #91, #93, #95, #97;
- Inversion Labs / Forge edition lineage: PRs #104, #108, #109, #110, #112, #119;
- public-release design/planning authority: PRs #111 and #116;
- workflow/archive material such as #99; historical merge #45 remains a documentation record, not runtime authority.

See [`PR_TOPOLOGY.md`](PR_TOPOLOGY.md) for the routing map.

## Native macOS status

The native surface is no longer “SwiftUI contract only.” `CAPTNativeMac` is a real buildable Swift application target with governed chat, approval, runtime/provider controls, session persistence, and cross-surface tests.

What is **not** implied: current convergence-head signing/notarization/distribution/auto-update release proof. A successful source build is not a notarized product release.

## Cohort status

Cohorts are no longer “durability later.” Merged `main` contains durable Cohort EventStore state, reconstruction, evidence admission, governed steering, epoch handling, and the Cohort Chamber projection. Council-scale public-product orchestration remains a separate planned tranche.

## Provider status

Local OpenAI-compatible endpoints (including the configured MTPLX path), Ollama, and governed provider execution are present in merged `main`. Provider activation persists a coherent provider/model tuple and legacy provider registries are backfilled without overwriting user configuration.

The dormant generic native `MLX / mlx_lm` placeholder is intentionally **not** represented as a working native adapter. A materially configured local OpenAI-compatible MLX/MTPLX service is a different path.

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
       DriverHost / bounded drivers
                |
                v
        replaceable inference models
```

No UI, MCP client, model, Cohort projection, security checker, provider manager, or prompt-enhancement engine becomes a parallel source of CAPT authority.
