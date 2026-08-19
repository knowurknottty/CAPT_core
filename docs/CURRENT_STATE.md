# CAPT Core — Current State

This is the concise public status source for the repository. It intentionally separates the numbered package version, protected `main`, the terminal convergence candidate, and release authorization.

## Truth classes

### 1. Numbered package release

`pyproject.toml` still declares **`capt-solo 0.5.0`**. Preserved evidence under `release_evidence/v0.5/` applies to that historical release lineage only.

### 2. Protected `main`

Protected `main` remains the published integration baseline. It includes the normal CLI/on-ramp, durable runtime and memory foundations, shared operator layer, provider/model configuration foundations, Textual/Tk operator surfaces, and pinned authored-skill verification.

`main` is not the authority for the newer terminal convergence work until PR #117 is actually merged.

### 3. Terminal convergence candidate

The terminal candidate is **PR #117**, branch `integration/capt-core-terminal-convergence-r2`. It is the semantic reconciliation point for the formerly stacked Core implementation branches rather than a mechanical mega-merge.

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

- local Core Python suite on the frozen runtime snapshot: **1,055 passed / 57 skipped / 12 deselected / 0 failures** in a clean Python 3.14 environment;
- GitHub M0-A on the terminal candidate: **PASS on Python 3.10 and Python 3.12**, including conformance, full regression, wheel build/install, clean installed imports, package-content inspection, contract reproducibility, and TypeScript parity;
- Swift local normal: **64 tests / 7 explicit live/cross-surface skips / 0 failures**;
- Swift strict concurrency + warnings-as-errors: **PASS**;
- ThreadSanitizer: **64 / 7 skipped / 0 failures**, no sanitizer finding;
- GitHub Native macOS Swift workflow: **PASS**, including unit tests and `CAPTNativeMac` build;
- contract drift: **PASS** (`11 generated files match the schema source`);
- fatal Python lint subset (`E9/F63/F7/F82`): **PASS**;
- MCP PR #2 full suite against the frozen Core runtime snapshot: **259 passed / 0 failures**;
- MCP Ruff: **PASS**;
- disposable macOS ↔ RuntimeService ↔ MCP acceptance: **CROSS_SURFACE_PASS** with one provider dispatch, idempotent replay, mismatched-reuse rejection, restart reconstruction, task `awaiting_verification`, and no manufactured verification ID.

A Python 3.10 Textual teardown race discovered by CI was repaired by making the presentation-only status callback tolerate the `StatusBar` already being unmounted. The post-fix Python 3.10 and 3.12 M0-A matrices are both green.

The repository-wide broad Ruff `F/E9` sweep is **not clean**: it still contains legacy unused-import/local/redefinition debt outside the convergence slice. This is tracked as cleanup debt, not represented as a release gate pass.

### 4. Release authorization

Integration verification and release authorization are deliberately separate.

The Security Closure Cockpit is now wired into GitHub Release Security CI as an exact-head, fail-closed gate rather than allowing an unrelated green workflow badge to imply release authorization. The current candidate result is:

- decision: **BLOCKED**;
- `releaseAuthorized=false`;
- **2 PASS / 0 FAIL / 19 NOT_VERIFIED / 26 NOT_APPLICABLE**;
- the two exact-head PASS attestations currently come from full-history `gitleaks` and the installed-runtime dependency `pip-audit`;
- all remaining applicable release-blocking controls stay blocked until their required evidence class is supplied.

`NOT_VERIFIED` means evidence is absent/stale/incomplete; it is not equivalent to a discovered vulnerability. Ordinary Python/Swift/MCP tests are not promoted into security attestations.

Therefore the truthful current classification is:

`IMPLEMENTED_CROSS_SURFACE_VERIFIED_RELEASE_SECURITY_BLOCKED`

This is a strong integration candidate, **not yet a release-certified protected-main merge**.

## Deliberate exclusions

The terminal Core line does **not** absorb:

- CAPT-UPG-020→024 benchmark/probe work while its empirical/exact-head classifications remain pending;
- Inversion Labs / Forge edition-specific runtime, UI, or lexical-analysis work;
- Inversion Eval work in the separate MCP repository;
- uncommitted or dirty foreign-worktree state.

The superseded Core implementation PRs through UPG-019/native/provider convergence have been closed **unmerged as superseded by PR #117**, preserving their review history without presenting stale bases as competing release candidates.

## Native macOS status

The native surface is no longer “SwiftUI contract only.” `CAPTNativeMac` is a real buildable Swift application target with governed chat, approval, runtime/provider controls, session persistence, and cross-surface tests.

What is **not** implied: current convergence-head signing/notarization/distribution/auto-update release proof. A successful source build is not a notarized product release.

## Cohort status

Cohorts are no longer “durability later.” The convergence line contains durable Cohort EventStore state, reconstruction, evidence admission, governed steering, epoch handling, and the Cohort Chamber projection. Council-scale public-product orchestration remains a separate planned tranche.

## Provider status

Local OpenAI-compatible endpoints (including the configured MTPLX path), Ollama, and governed provider execution are present in the convergence line. Provider activation persists a coherent provider/model tuple and legacy provider registries are backfilled without overwriting user configuration.

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
