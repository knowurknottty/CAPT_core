# CAPT Standalone Harness v0.5 — Residual Backlog (post-release)

SHA-bound to: b45c4b005c9171172d055697a55034006bb0f2fe
Date: 2026-08-05

Items are ordered by release-impact. None blocks v0.5; all are
documented for v0.6 planning.

## P1 (recommended next release)
1. **Repository-wide lint baseline (Ruff)**
   - Current: 2,721 findings across the full repository (inherited from
     the pre-release baseline; final v0.5 quality claims are scoped to
     targeted harness tests + installed proof).
   - Target: CI gate with zero findings or an explicit allowlist with
     review dates.

2. **Plugin version axis**
   - v0.5 declares no plugin registry/axis. version-map.md documents the
     axis as NOT ESTABLISHED. v0.6 should define the plugin axis and map
     existing runtime/plugin surfaces onto it.

3. **OpenAI-compatible packaged CAPT driver**
   - LM Studio endpoint (http://127.0.0.1:1234/v1) was live during the
     proof but is NOT wrapped in a packaged CAPT ExecutionDriver. A
     generic OpenAI-compatible driver would decouple the model operator
     from Hermes CLI availability.

## P2 (hardening)
4. **Multi-user / enterprise operator identity**
   - Operator identity is the local macOS user (operator-<user>),
     session-bound. No multi-user, tenant isolation, or enterprise
     identity claim is made. v0.6 should add operator authorization
     policies (which ops which operator may run).

5. **TaskResolver redispatch semantics**
   - The resolver rejects redispatch of completed tasks when forbidden.
     v0.6 should add explicit operator-facing redispatch policy
     (allow/deny per task type) and document the capability scope
     matrix.

6. **Verification policy expansion**
   - Verification requires a clean worktree (git status --porcelain
     empty) for repo_unchanged/no_git_mutation. Session-local files must
     be gitignored. A policy for dirty-but-expected trees (e.g. explicit
     ignore lists) would reduce operator friction.

7. **ClaimGuard statement registry**
   - Only the M0-B allowlisted statements are accepted. v0.6 should add
     a declarative statement registry with provenance per statement so
     new driver claims can be added without touching code.

## P3 (parked / non-goals)
8. **TaskExecutionSnapshotCreated restoration** — explicitly out of
   scope (no snapshot-based task restoration in v0.5).
9. **Contract-bundle migration** — out of scope (no migration of
   contract bundles).
10. **Free-text fields on frozen contracts** — prohibited by
    additionalProperties=false on ContextSlice/ExecutionDriverWorkOrder;
    objective travels by missionId/taskId reference (TERRA directive).
11. **Second objective authority / out-of-band transport** — prohibited.
12. **New IPC protocol, bytecode, dual-layer encryption, ECP runtime
    integration** — out of scope for v0.5; see prior architecture
    reframe.
13. **Model backend bundling** — the wheel does not bundle/vendor a
    model; the operator provides Hermes CLI (or another driver).
