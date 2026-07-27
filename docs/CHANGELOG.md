# CAPT Solo — Changelog

## v0.4.1 (2026-07-27) — Engines + Memory Convergence + Release Hardening

### Added
- **Public engines** (owner priority):
  - `capt_solo.engines.mathematics` — safe AST parser (no eval/exec), exact
    `Fraction` arithmetic, dimensional quantities (7 SI base dims), structural-
    affine linear solving, extrema-safe intervals, derivation provenance.
  - `capt_solo.engines.physics` — on the math substrate; classical mechanics,
    thermodynamics, circuits, waves; every relation explicitly classified
    (established law / model / approximation / empirical / hypothesis /
    speculative); dimensional validation.
  - `capt_solo.engines.invention` — structured 17-step workflow, explainable
    feasibility scoring, contradiction detection, safety gates, revision history;
    integrates math/physics results; no patentability claims.
- **Memory convergence** (`capt_solo.memory.types`): explicit 14-type memory
  taxonomy, non-destructive revision, provenance chains, quarantine of malformed
  data; DREAM output labeled inferred (never overwrites canonical memory).
- **PULSE gateway** (`capt_solo.pulse`): optional, disabled-by-default, no network
  on import, fails closed.
- **Verified State Identity (VSI) verification subsystem**
  (`capt_solo/verification/`): verification is bound to the STATE being verified,
  not to conversation age. A `VerifiedStateIdentity` captures repo/branch/HEAD/
  scoped file hashes/dependency/runtime/environment/command/scope. When the VSI is
  unchanged, prior evidence is reused (no rerun); when it changes, only the
  affected scope is re-verified. Eliminates verification loops on long missions.
  `capt verify run --scope X` and `capt verify status` CLI commands.
- **Universal Workspace layer**: repository-native, harness-neutral execution
  context. Root `AGENTS.md` (single entrypoint + authority order + startup
  procedure + owner gates), `WORKSPACE.md`, `CURRENT_STATE.md`, `CHECKPOINT.md`,
  `TASK_QUEUE.md`, `SECURITY_BOUNDARIES.md`, `TOOLING.md`, `RELEASE_STATE.md`,
  `CONTRIBUTING.md`. JSON Schemas for workspace/task/checkpoint/agent-capabilities.
- **`capt workspace` CLI group**: `status` / `validate` / `bootstrap` /
  `checkpoint` / `tasks` / `next` / `capabilities` / `archive-checkpoint`.
  Local-first, no network I/O; `validate` is a CI gate for workspace consistency.
- **Concurrency detection** in `workspace_status` (parallel active-task claims,
  other-agent claims, active+completion_commit inconsistency).
- **Release-boundary governance review** (`docs/RELEASE_GOVERNANCE.md`): every
  subsystem classified PUBLIC / RESEARCH / EXTERNAL / OPTIONAL from registry
  evidence; owner [B]/[S] gates prepared (no irreversible decisions made).
- **MIT LICENSE** (resolves a release blocker; consistent with pyproject).

### Fixed
- Version identity drift: README, release docs, installer/verify/uninstall
  banners reconciled to `0.4.1`.
- I-15 ("Evidence over implementation", ADR-0006) added to the CAPT_CANON
  invariant table (canon/ADR reconciliation).
- `architecture show` duplicate subparser that broke the entire CLI parse.
- `foundry/harness.py` skill-execution sandbox: replaced `os.system` shell
  injection with shell-free `subprocess.run(shlex.split(...))`.
- `architecture/debt.yaml`: all 17 items reconciled to `resolved` with evidence.

### Security
- Capability spoofing and schema `additionalProperties` bypass rejected by
  validation; default capability manifest denies network/browser/secrets.
- Negative regression tests for hostile task content, harness injection, and
  capability spoofing.

## v0.4.0 (2026-07-19) — Proof-Governed Cognitive Operating System

### Added
- **Skill Foundry**: procedure → skill candidate → evidence → 12-stage validation
  → review → publish. Full lifecycle with explicit transitions.
- **Proof Engine**: evidence objects + aggregation against declared requirements.
- **Capability Registry**: candidate→validated→proven→verified (3 distinct,
  idempotent events). 12 explicit degradation reason codes with structured records.
- **ClaimGuard**: claim validation with downgraded language; scoped degradation
  (macOS-only ≠ global revoke).
- **Knowledge Bubble Runtime**: v2 manifest (bubble_id, version, namespaces,
  artifact inventory, per-artifact hashes, manifest hash, signature placeholder,
  redaction declaration, declared permissions/dependencies, export policy,
  provenance) + 12-step validation (manifest before payload). Quarantine-by-default.
- **Governance Layer**: all consequential actions CTP-bounded + audited.
- **Workflow Proof Engine**: composed workflows carry independent proof; do NOT
  inherit component verification.
- **Migration safety gate**: backup-gated forward migration (sqlite3.backup() +
  integrity_check + receipt; abort on failure). `ALLOW_MIGRATION_WITHOUT_BACKUP=False`.
- **CLI**: `foundry` group (skills, capabilities, bubbles, governance, curate, audit).
- **Plugin**: 10 new v0.4 foundry tools (46 total).
- **Doctor/verify**: extended with v0.4 checks (schema v4, backup dir, foundry
  import, 12 degradation codes, CLI availability, plugin count, verify_runtime).
- **Boundary audit**: `api.py` + `capt_cli.py` confirmed SQL-free; regression test.

### Changed
- `SCHEMA_VERSION` 3 → 4 (v0.4 tables: composite_workflows, workflow_proofs,
  governance_audit, capability_degradations).
- `build_skill` rollback default is now `None` (empty string is respected as a
  real, validation-failing value).

### Schema
- Forward-only migrations. Backup taken before any version bump. Idempotent re-open.

### Verification
- 348 tests passing (migration, workflow proof, degradation, bubble, CLI, plugin,
  foundry, boundary, v0.1–v0.3 regression).
- `verify_runtime.py` exercises all subsystems end to end.
- `doctor.sh` reports v0.4 environment health.

## v0.3.0 — Lifecycle, Sessions, Procedures, Prospective Memory
## v0.2.0 — KHSB bus, CTP transactions, retrieval feedback
## v0.1.0 — Memory engine, core, plugin scaffold
