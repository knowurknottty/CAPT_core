# CAPT Core — Current State

This is the concise public status source for the repository. It intentionally separates the numbered package version, protected `main`, the terminal convergence candidate, and release authorization.

## Truth classes

### 1. Numbered package release

`pyproject.toml` still declares **`capt-solo 0.5.0`**. Preserved evidence under `release_evidence/v0.5/` applies to that historical release lineage only.

### 2. Protected `main`

Protected `main` remains the published integration baseline. It includes the normal CLI/on-ramp, durable runtime and memory foundations, shared operator layer, provider/model configuration foundations, Textual/Tk operator surfaces, and pinned authored-skill verification.

`main` is not the authority for the newer terminal convergence work until PR #117 is actually merged.

### 3. Terminal convergence candidate

The terminal candidate is **PR #117**, branch `integration/capt-core-terminal-convergence-r2`. The current local verification line additionally reconciles PR #118's provider/model coherence fix onto the latest PR #117 head before publication.

The convergence candidate contains, as one coherent lineage:

- CAPT-UPG-001→019 functionality and the corrected replay/checkpoint state model;
- bounded production IPC framing, rejection audit, state permissions, resource ceilings, and injection-assurance work;
- governed cross-model continuation/context binding and no-repeat recovery semantics;
- durable Cohort EventStore persistence, evidence admission, operator steering, Chamber projection, and stale-epoch/quorum semantics;
- governed artifact promotion, capability lease inspection/revoke, `.capt-flight`, provenance DAG, epistemic ladder, replay fork, and Security Closure Cockpit;
- first-class local OpenAI-compatible provider execution/prewarm and coherent provider/model persistence;
- native Swift macOS chat/operator application source with session isolation, typed runtime projections, encrypted session cache, and origin-session-bound async updates;
- pinned authored-skill bytes bound into the exact model-visible approval identity;
- macOS ↔ RuntimeService ↔ MCP shared-ledger acceptance.

Fresh 2026-08-19 convergence verification has independently reproduced:

- full Core Python suite: **1,055 passed / 57 skipped / 12 deselected / 0 failures** in a clean Python 3.14 environment;
- Swift normal: **64 tests / 7 explicit live/cross-surface skips / 0 failures**;
- Swift strict concurrency + warnings-as-errors: **PASS**;
- ThreadSanitizer: **64 / 7 skipped / 0 failures**, no sanitizer finding;
- contract drift: **PASS** (`11 generated files match the schema source`);
- fatal Python lint subset (`E9/F63/F7/F82`): **PASS**;
- MCP PR #2 full suite against the same Core candidate: **PASS**;
- MCP Ruff: **PASS**;
- disposable macOS ↔ RuntimeService ↔ MCP acceptance: **CROSS_SURFACE_PASS** with one provider dispatch, idempotent replay, mismatched-reuse rejection, restart reconstruction, task `awaiting_verification`, and no manufactured verification ID.

The repository-wide broad Ruff `F/E9` sweep is **not clean**: it currently reports legacy unused-import/local/redefinition debt outside the convergence slice. This is tracked as cleanup debt, not represented as a release gate pass.

### 4. Release authorization

Integration verification and release authorization are deliberately separate.

The Security Closure Cockpit remains fail-closed until every applicable release-blocking control has legitimate exact-head evidence. The most recent terminal-candidate gate was **BLOCKED / releaseAuthorized=false**, with zero controls falsely promoted from ordinary unit tests. Final artifact hashes and the final exact-head gate are recorded on PR #117 after the terminal verification pass.

Therefore the truthful current classification is:

`IMPLEMENTED_CROSS_SURFACE_VERIFIED_RELEASE_SECURITY_BLOCKED`

This is a strong integration candidate, **not yet a release-certified protected-main merge**.

## Deliberate exclusions

The terminal Core line does **not** absorb:

- CAPT-UPG-020→024 benchmark/probe work while its empirical/exact-head classifications remain pending;
- Inversion Labs / Forge edition-specific runtime, UI, or lexical-analysis work;
- Inversion Eval work in the separate MCP repository;
- uncommitted or dirty foreign-worktree state.

## Native macOS status

The native surface is no longer “SwiftUI contract only.” `CAPTNativeMac` is a real buildable Swift application target with governed chat, approval, runtime/provider controls, session persistence, and cross-surface tests.

What is **not** implied: current convergence-head signing/notarization/distribution/auto-update release proof. A successful source build is not a notarized product release.

## Cohort status

Cohorts are no longer “durability later.” The convergence line contains durable Cohort EventStore state, reconstruction, evidence admission, governed steering, epoch handling, and the Cohort Chamber projection. Council-scale public-product orchestration remains a separate planned tranche.

## Provider status

Local OpenAI-compatible endpoints (including the configured MTPLX path), Ollama, and governed provider execution are present in the convergence line. Provider activation now persists a coherent provider/model tuple and legacy provider registries are backfilled without overwriting user configuration.

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
