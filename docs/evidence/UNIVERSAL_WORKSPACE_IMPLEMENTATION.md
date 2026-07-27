# Universal Workspace Implementation — Evidence

**Date:** 2026-07-26
**Session:** CAPT v0.4 Public Release Stewardship (integration/full-public-architecture, HEAD `dc806b4`)
**Task:** Prompt #1 (Universal Workspace Layer) + Prompt #2 (Release Stewardship)
**Verification:** all claims below re-run this session; no prior-session result reused as final evidence.

## What changed

### Files created (root workspace contract)
- `AGENTS.md` — single agent entrypoint: authority order, startup procedure,
  operating rules, owner gates.
- `CAPT_CANON.md`, `CANONICAL_ARCHITECTURE.md`, `CANONICAL_OWNERSHIP_MATRIX.md` —
  thin **pointers** to the canonical sources in `docs/` (no duplication; the
  canonical docs are referenced by tests, registry, and 6 ADRs).
- `WORKSPACE.md` — workspace contract: contents, state classes, permissions,
  resume protocol, concurrency model.
- `CURRENT_STATE.md` — authoritative live state (branch/HEAD/tests/blockers).
- `CHECKPOINT.md` — immediate resume contract (commit `dc806b4`).
- `TASK_QUEUE.md` — human-readable queue seeded from real debt + release blockers.
- `SECURITY_BOUNDARIES.md` — trust classes, golden rules, hostile-content handling.
- `TOOLING.md` — workspace CLI reference.
- `RELEASE_STATE.md` — release readiness + open blockers + owner gates.
- `LICENSE` — MIT (matches `pyproject.toml` declaration; was missing — a release blocker).
- `architecture/workspace.schema.json`, `task.schema.json`, `checkpoint.schema.json`,
  `agent-capabilities.schema.json` — JSON Schemas (draft-07, validated by a
  dependency-free internal validator in `capt_solo/workspace.py`).
- `tasks/TASK-*.json` (11 records) — seeded from `architecture/debt.yaml` (resolved
  items) + release blockers + workspace build tasks.
- `decisions/ evidence/ memory/ knowledge/ tasks/ checkpoints/ logs/ tools/` — dirs.
- `.codex/README.md`, `.claude/CLAUDE.md`, `.github/copilot-instructions.md`,
  `.hermes/README.md` — thin harness adapters pointing back to AGENTS.md.

### Code created
- `capt_solo/workspace.py` — local-first workspace engine: `validate_workspace`,
  `workspace_status`, `bootstrap_reading_list`, `list_tasks`, `next_task`
  (capability-aware), `capabilities_manifest`, `generate_checkpoint`,
  `archive_checkpoint`, and a minimal draft-07 JSON Schema validator (no
  `jsonschema` dependency required). Performs **no network I/O**; reads
  markdown/JSON/YAML as data, never executes them.
- `capt_cli.py` — added `workspace` command group (status/validate/bootstrap/
  checkpoint/tasks/next/capabilities/archive-checkpoint) and **fixed a pre-existing
  duplicate `architecture show` subparser** that broke the entire CLI parse.

### Files reused / repaired (no duplication)
- Canonical docs kept at `docs/`; root files are pointers.
- `architecture/registry.yaml` source_of_truth unchanged.
- `docs/CAPT_CANON.md` — added **I-15** to the invariant table (ADR-0006 already
  established I-15; the table was stale — a canon/ADR contradiction repaired).
- `README.md` — corrected version `v0.1` → `v0.4.1`, doc/tool counts, added
  Universal Workspace section.
- `capt_cli.py` — corrected stale `v0.3 — Memory Review CLI` module docstring.
- `architecture/debt.yaml` — all 17 items marked `resolved` with evidence notes
  (they were addressed across Phases 3B–3M but the file was never reconciled).
- `docs/RELEASE_AUDIT_v0.4.md`, `docs/RELEASE_CANDIDATE_v0.4.0.md` — added dated
  reconciliation notes (463 tests / 46 checks; prior snapshots said 355 / 45).

### Security hardening
- `capt_solo/foundry/harness.py` — replaced `os.system(f"cd {workdir} && {st} ...")`
  (shell-injection surface; skill workflow content is untrusted) with shell-free
  `subprocess.run(shlex.split(st), ...)`. A hostile `echo x; rm -rf ~` step no
  longer executes the trailing command. Regression test added.

## Authority model
1. `docs/CAPT_CANON.md` (invariants I-01..I-15)
2. Approved invariants
3. `architecture/registry.yaml`
4. ADRs (`docs/adr/`)
5. `docs/CANONICAL_ARCHITECTURE.md`
6. `docs/CANONICAL_OWNERSHIP_MATRIX.md`
7. Implementation + tests
8. Evidence
9. Historical/forensic

Existing code is implementation evidence, not architectural authority. Contradictions
are surfaced, not silently reconciled (e.g. I-15 gap; version drift; duplicate parser).

## Schema decisions
- Minimal internal draft-07 validator (type/required/properties/enum/pattern/
  format/minLength/minimum/maximum/additionalProperties/array-items) chosen to
  avoid a hard `jsonschema` dependency in the local-first runtime. If `jsonschema`
  is installed, `capt workspace validate` could delegate to it; the internal
  validator is the portable default.
- `task.schema.json` uses `additionalProperties: false` so a task record cannot
  silently add authority-granting fields. `owner_gate` is an enum; a task cannot
  self-clear a real gate.
- `completion_commit` allows `null` (uncompleted) or a 7–40 hex SHA.

## CLI behavior (verified this session)
- `capt workspace validate` → exit 0, `ok=true`, 0 fail, 1 warn (external/
  planned namespaces absent — expected).
- `capt workspace status` → branch/HEAD/clean/active_task/owner_gates.
- `capt workspace bootstrap` → 9-line ordered reading list.
- `capt workspace next` → highest-priority READY task with satisfied deps + caps.
- `capt workspace capabilities` → manifest (network/browser/secrets false by default).
- `capt workspace tasks` → lists `tasks/*.json`.
- `capt workspace checkpoint` / `archive-checkpoint` → regenerate / archive.

## Harness adapters
Thin pointers only. Each adapter file redirects to AGENTS.md + CURRENT_STATE.md +
CHECKPOINT.md. No independent constitution.

## Trust boundaries
- Canonical > implementation > evidence > task/checkpoint (untrusted data) >
  external/tool output (untrusted data) > agent-local scratch (ephemeral).
- Task/checkpoint records validated; cannot grant capabilities or redefine authority.
- No network I/O in workspace tooling; no secret persistence; logs must not contain
  secrets (screener in `capt_solo/memory/secrets.py`).

## Test results (this session)
- `tests/test_workspace.py` — 24 tests (schema valid/invalid, missing-file,
  invalid-reference, stale-checkpoint, circular-dependency, capability-mismatch,
  bootstrap-ordering, CLI integration, clean-checkout). **All pass.**
- `tests/test_workspace_security.py` — 10 tests (hostile task rejected, malformed
  checkpoint rejected, task cannot grant caps, no network imports, secret screener,
  harness injection regression). **All pass.**
- Full suite: `463 passed` (pre-existing) + 34 new = consistent; no regressions.
- `verify_runtime.py`: 46 pass. `architecture/validate_registry.py`: 15 pass.

## Limitations
- The internal schema validator is a subset of draft-07 (no `$ref`, `allOf`,
  `anyOf`, `not`); sufficient for the four workspace schemas.
- `workspace.registry_ns` warns about absent `capt_solo.constitution` /
  `capt_solo.reasoning*` dirs — these are spec-only/Research subsystems (Ontology,
  Constitution, Reasoning) intentionally not implemented in core; the warn is
  honest, not a failure.
- Owner gates for public release ([B] public/private boundary for research modules;
  [S] privacy review for Consent/Sync; [B]+[S] PULSE/RYS) remain owner decisions,
  not resolved by this autonomous pass.

## Remaining debt
- None blocking the workspace layer. Release-blocker-class items (LICENSE, version
  drift, I-15, stale docs) resolved this session. The [B]/[S] owner gates are the
  only outstanding public-release decisions (see RELEASE_STATE.md).
