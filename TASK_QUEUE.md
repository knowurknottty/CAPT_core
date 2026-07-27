# TASK_QUEUE.md — Human-Readable Task Queue

Machine-readable records live in `tasks/*.json` (schema: `architecture/task.schema.json`).
Status model: `blocked | ready | active | verification | complete | deferred | rejected`.
Get the next actionable task: `capt workspace next`.

## Active / Ready (seeded from real debt + release blockers + workspace build)

| ID | Title | Subsystem | Phase | Pri | Status | Deps | Owner gate |
|----|-------|-----------|-------|-----|--------|------|------------|
| TASK-100 | Build CAPT Universal Workspace layer (scaffold + schemas + docs + CLI) | Workspace | S1 | 1 | active | — | none |
| TASK-101 | Implement `capt_solo/workspace.py` + `capt workspace` CLI group | Workspace | S1 | 1 | ready | TASK-100 | none |
| TASK-102 | Workspace schema + CLI integration tests (positive + negative) | Workspace | S1 | 2 | ready | TASK-101 | none |
| TASK-200 | Reconcile `architecture/debt.yaml` with evidence (Phases 3B–3M) | Debt | S1 | 2 | ready | — | none |
| TASK-201 | Resolve version identity drift (README v0.1 / docs v0.4.0 / pyproject 0.4.1) | Release | S1 | 1 | ready | — | none |
| TASK-202 | Refresh stale release docs (355/45 → 463/46) + workspace evidence doc | Release | S1 | 2 | ready | TASK-100 | none |
| TASK-203 | Add I-15 to CAPT_CANON invariant table (canon/ADR reconciliation) | Canon | S1 | 1 | ready | — | none |
| TASK-204 | Harden `foundry/harness.py` os.system injection (shell-free sandbox) | Security | S1 | 1 | ready | — | none |
| TASK-205 | Add LICENSE file (MIT) to resolve release blocker | Release | S1 | 1 | ready | — | licensing |
| TASK-206 | Add harness adapter pointers (.codex/.claude/.github/.hermes) | Workspace | S1 | 3 | ready | TASK-100 | none |
| TASK-207 | Final release verification (build/install/runtime/CLI/workspace/schemas/smoke/packaging/API/plugin) | Release | S1 | 1 | ready | TASK-100..206 | none |

## Notes

- TASK-205 carries `owner_gate: licensing` only because adding a license is a
  licensing action; the project already declares MIT in `pyproject.toml`, so the
  steward-created LICENSE is consistent with the declared intent (no uncertainty
  introduced). Flagged for owner awareness, not a hard block.
- The [B]/[S] public/private and privacy gates for research modules (FILT/FSR/
  NEDA/ALLO/OUROBOROS, PULSE/RYS) are **owner decisions for the public release**,
  tracked in CURRENT_STATE.md / RELEASE_STATE.md, not tasks an autonomous agent
  resolves.
- Do not create speculative backlog items. This queue is seeded only from
  approved debt, release blockers, and the active stewardship phase.
