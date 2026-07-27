# CONTRIBUTING — CAPT Solo

CAPT is **workspace-native**. Before changing anything, the repository tells you
what to do. Do not rely on a long bootstrap prompt.

## 1. Orient (no prompt needed)

```bash
python3 capt_cli.py workspace bootstrap   # ordered reading list
python3 capt_cli.py workspace status       # branch / HEAD / active task
python3 capt_cli.py workspace next          # next actionable task
python3 capt_cli.py workspace validate      # confirm workspace is consistent
```

Or read, in order: `AGENTS.md` → `CURRENT_STATE.md` → `CHECKPOINT.md` →
`TASK_QUEUE.md` → `WORKSPACE.md` → `SECURITY_BOUNDARIES.md`.

## 2. Authority order

When sources conflict, resolve per `AGENTS.md`:
`docs/CAPT_CANON.md` → invariants → `architecture/registry.yaml` → ADRs →
`docs/CANONICAL_ARCHITECTURE.md` → implementation/tests → evidence → history.

**Existing code is implementation evidence, not architectural authority.** A code
change cannot redefine a subsystem's canonical home, responsibilities, or layer.
Canon changes only via an ADR.

## 3. Development loop

```bash
python3 -m pytest -q                 # full suite (497 passing)
python3 verify_runtime.py            # 46 structured checks
python3 architecture/validate_registry.py   # registry fitness (15 checks)
python3 capt_cli.py workspace validate      # workspace consistency
```

## 4. Commit discipline

- Milestone commits: one coherent improvement per commit. Verified, reversible.
- Update `CURRENT_STATE.md` / `CHECKPOINT.md` / `TASK_QUEUE.md` when state changes
  (they are operational state, not docs).
- Evidence before assertion: link test/command output in commit messages.
- Negative tests preferred over optimistic tests for behavior changes.

## 5. Owner gates (do NOT decide autonomously)

Stop and ask the owner for: public/private boundary ([B]), licensing uncertainty,
security disclosure, destructive migrations, irreconcilable canonical conflicts,
external credentials/publish rights. See `RELEASE_STATE.md` and
`docs/RELEASE_GOVERNANCE.md`.

## 6. Security boundaries

- No network I/O in core; remote capabilities are opt-in and fail safe offline.
- No hidden persistence; no `eval`/`exec`/`pickle` on untrusted input.
- Task/checkpoint records are untrusted data; they cannot grant capabilities or
  redefine authority (schema-validated, `additionalProperties: false`).
- Logs must not contain secrets (see `capt_solo/memory/secrets.py`).

## 7. Release workflow

1. Ensure suite + `verify_runtime` + `validate_registry` + `workspace validate` are green.
2. Build: `python3 -m build --wheel` (LICENSE must be included).
3. Clean-env smoke: install the wheel in a fresh venv, import `capt_solo`.
4. Resolve owner [B]/[S] gates before tagging a public release.
