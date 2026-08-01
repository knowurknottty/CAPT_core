# Recovered prior run — PROVISIONAL evidence, NOT canonical

Status: **PROVISIONAL. Superseded by the canonical run.**

These files were produced by an earlier execution of
`skills/hermes/capt-core-runtime/tests-acceptance/run-acceptance.sh` on
2026-08-01T02:26Z, before the harness was hardened.

They are retained because the session that produced them was interrupted
(repeated exit 130 on the controlling terminal) and the run was never
independently verified from outside the harness. They are preserved rather
than deleted so that the prior claim is auditable, not so that it can be
cited as proof.

## Why they are not canonical

1. The harness that wrote them used `set -uo pipefail` without `-e` and
   without ERR/EXIT traps, so a mid-script failure could not be distinguished
   from success by exit code alone.
2. The evidence directory was not resolved to an absolute path, was not
   asserted to be inside the worktree, and no `00-evidence-root.txt` sentinel
   was written; the run's own identity (host, PID, branch, HEAD, CAPT home)
   was never recorded alongside the artifacts.
3. Per-step stderr and per-step exit codes were not captured to disk. Only
   the harness's own narration survived.
4. The isolation check ran only at the end (step 7). Nothing refused to start
   if `CAPT_SOLO_HOME` had resolved to owner state.
5. The temporary isolated root `/tmp/capt-skill-acceptance.Fsp3xv` referenced
   by these artifacts is a scratch path; the artifacts cannot be replayed from
   this directory alone.

## Disposition

Do not merge these numbers into the canonical report. The canonical run lives
in `acceptance-evidence/canonical-<UTC timestamp>/` and carries its own
sentinel, per-step exit codes, stderr, isolation report, and manifest.
