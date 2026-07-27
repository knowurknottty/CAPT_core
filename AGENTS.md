# AGENTS.md — Universal Agent Entrypoint (CAPT)

Read this file first. It is the single entrypoint for any agent or harness
entering this repository. CAPT is **workspace-native, not prompt-native**: the
repository carries its own authority, state, tasks, checkpoints, and evidence.
You should not need a large bootstrap prompt to understand it.

## Authority order

When sources conflict, resolve in this order:

1. `CAPT_CANON.md` → `docs/CAPT_CANON.md` (constitutional invariants I-01..I-15)
2. Approved architectural invariants (I-01..I-15)
3. `architecture/registry.yaml` (machine-readable subsystem registry)
4. Approved ADRs (`docs/adr/`)
5. `CANONICAL_ARCHITECTURE.md` → `docs/CANONICAL_ARCHITECTURE.md`
6. `CANONICAL_OWNERSHIP_MATRIX.md` → `docs/CANONICAL_OWNERSHIP_MATRIX.md`
7. Current implementation contracts and tests (`capt_solo/`, `tests/`)
8. Implementation evidence (`docs/evidence/`, `checkpoints/`, `evidence/`)
9. Historical and forensic materials

### Non-negotiable principles

- **Existing code is implementation evidence, not automatic architectural authority.**
- **Historical documents are evidence, not canon.**
- **Architecture governs implementation.** When code and architecture conflict,
  the code changes — not the architecture.
- **Canon may only change through an explicit architectural decision process**
  (an ADR). A code change cannot redefine a subsystem's canonical home,
  responsibilities, or layer.
- **Contradictions must be surfaced, not silently reconciled.** If you find a
  conflict between canon, registry, implementation, and tests, report it and
  (where evidence-backed and within your authority) repair the lowest-authority
  layer, recording the contradiction.

## Startup procedure (every agent must do this)

1. Read `AGENTS.md` (this file).
2. Read `CURRENT_STATE.md` (authoritative live state).
3. Read `CHECKPOINT.md` (immediate resume contract).
4. Inspect `TASK_QUEUE.md` and `tasks/` (active work).
5. Read the canonical files relevant to the active task.
6. Verify repository status (`git status`, `git log -1`, branch).
7. Continue from the declared resume point.

Do not begin substantive work before steps 1–6. The `capt workspace` CLI
encodes this procedure: `capt workspace bootstrap` prints the minimal ordered
reading list; `capt workspace status` reports live state.

## Operating rules

- **Evidence before assertion.** No claim enters Trust/Knowledge without linked
  evidence and provenance.
- **Explicit uncertainty.** Confidence is always represented; `unknown` is a
  first-class value.
- **No hidden network behavior.** No operation requires a network. Remote
  capabilities are opt-in and fail safe offline (I-01, I-09).
- **No hidden persistence.** Nothing is written outside the declared workspace
  without explicit, logged intent.
- **Local-first defaults.** SQLite is the canonical store; exports are local.
- **Bounded failure.** A subsystem failure is contained; it does not cascade
  into silent corruption of others (I-07).
- **Backward compatibility.** Public APIs and persisted schemas evolve with
  migration; breaking changes require a version + migration path (I-08).
- **Optional capabilities degrade independently.** A disabled optional subsystem
  never breaks core (I-09).
- **No silent weakening** of consent, provenance, trust, or security.
- **Verify before claiming completion.** Run the relevant tests / `verify_runtime.py`
  / `capt workspace validate` and report real results.
- **Iteration exhaustion is a checkpoint, not completion.** If you hit the turn
  limit or a blocker, write a checkpoint and stop — do not fabricate success.

## Owner gates (stop and ask; do not proceed autonomously)

Only stop for:

- **Public/private boundary** — a [B] decision about what ships publicly.
- **Licensing uncertainty** — unknown or conflicting license obligations.
- **Security exposure** — a vulnerability requiring disclosure/coordination.
- **Destructive migration** — a schema/state migration that cannot be reversed
  from a backup.
- **Irreconcilable canonical conflict** — canon vs registry vs implementation
  that no evidence-backed repair can resolve.
- **External dependency requiring owner credentials or approval** — anything
  needing secrets, push access, or publish rights.

Everything else (refactor, simplify, dedupe, strengthen APIs, improve tests/docs/
validation/packaging, reduce debt) is within your autonomous authority provided
public behavior stays compatible, invariants are preserved, evidence supports the
change, and tests remain green.

## Workspace layout (root)

```
AGENTS.md                      this file (entrypoint)
CAPT_CANON.md                  pointer → docs/CAPT_CANON.md
CANONICAL_ARCHITECTURE.md      pointer → docs/CANONICAL_ARCHITECTURE.md
CANONICAL_OWNERSHIP_MATRIX.md   pointer → docs/CANONICAL_OWNERSHIP_MATRIX.md
WORKSPACE.md                   workspace contract (human-readable spec)
CURRENT_STATE.md               authoritative live state
CHECKPOINT.md                  immediate resume contract
TASK_QUEUE.md                  human-readable task queue
TOOLING.md                     tooling + CLI reference
SECURITY_BOUNDARIES.md         trust boundaries + handling of untrusted content
RELEASE_STATE.md               release readiness state
architecture/                  registry.yaml + JSON schemas
decisions/  evidence/  memory/  knowledge/  tasks/  checkpoints/  logs/  tools/
docs/                         canonical architecture, ADRs, evidence, subsystem docs
capt_solo/                    the runtime
tests/                        pytest suite
capt_cli.py                   CLI (incl. `capt workspace`, `capt architecture`)
verify_runtime.py             structured verification harness
doctor.sh / verify.sh / install.sh / uninstall.sh
```

## Harness adapters

Thin, non-constitutional pointers back to this file exist for common harnesses:
`.codex/README.md`, `.claude/CLAUDE.md`, `.github/copilot-instructions.md`,
`.hermes/README.md`. They never become independent constitutions.
