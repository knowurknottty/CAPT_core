# CAPT Standalone Harness v0.5 — Terminal Release Decision

Date: 2026-08-05
Attribution: knowurknot

## VERDICT: CAPT_MODEL_OPERATOR_PROVEN_AND_RELEASE_READY

## Basis (each independently evidenced)
1. **Source identity (clean, SHA-bound)**
   - HEAD b45c4b005c9171172d055697a55034006bb0f2fe on
     release/capt-standalone-final; git status --porcelain EMPTY
     (.hermes.md gitignored, not deleted). [git-head.txt, git-status.txt]

2. **Full source suite from the clean SHA**
   - 766 passed, 12 deselected in 19.83s, exit 0. [full-suite.log]
   - Deselection = project rule `-m 'not slow'`; all 12 slow tests are
     real-Hermes/memory-trigger tests whose capability is independently
     proven by the installed lifecycle proof (3 real Hermes executions).

3. **Packaged wheel from the clean SHA**
   - artifacts/capt_solo-0.5.0-py3-none-any.whl
     sha256 348fe9da477e0323d9c9b294677a1e10de4f9245373a27300367a9e8bdf879b3
   - Installed --no-deps into a fresh venv, PYTHONPATH= cleared, run from
     /tmp outside the repo; imports proven from the wheel.

4. **Installed governed model operator — REAL model lifecycle proof**
   - Authenticated `capt harness command run_approved_hermes_inspection`
     through the installed wheel; real Hermes 0.20.0 subprocess.
   - start -> health -> capabilities -> model task 1 (real execution,
     evidence-backed finding, verification, ClaimGuard, checkpoint) ->
     idempotent replay (no re-execution) -> model task 2 (distinct
     objective; driver inventory UNKNOWN=0) -> checkpoint -> stop ->
     restart on same ledger (chain digest matches) -> resume
     (not_repeated) -> model task 3 after restart -> clean stop.
   - Ledger: 0 -> 13 -> 26 -> 39 events across the sequence.
   - 3 real model artifacts with sha256 digests. [artifacts/*, installed/ledger-*.db]

5. **Raw authority matrix (installed, adversarial)**
   - 7/7 forgery cases rejected (forged operator, forged session,
     unsupported schema, unsupported op, missing field, forged shutdown,
     forged resume) with ZERO mutation and healthy-after proof.
   - Conflicting idempotency payload rejected
     (classification=idempotency, fingerprint-conflict detail), no
     mutation. [installed/adversarial-battery.py + run output]

6. **Defect discovered & fixed during the proof**
   - create_mission_with_approval early-return idempotency check ignored
     the stored fingerprint; same key + different payload silently
     returned "idempotent" and dropped the payload. Fixed in b45c4b0
     with regression test test_idempotency_key_conflicting_payload_rejected.
   - Also fixed during proof: client recv timeout decoupled from connect
     timeout (6af19cd); ClaimGuard allowlisted claim (6737f2c);
     artifact.create lease grant (ac6d057); non-contract field removal
     (3aa1be5); capabilities advertisement (cb8089d).

7. **Closure artifacts (this evidence dir)**
   - evidence-manifest.md (provenance, suite, wheel, lifecycle,
     authority matrix, commit history, driver inventory)
   - version-map.md (product 0.5.0 vs runtime 0.1.0 vs contract 1.0.0,
     plugin axis NOT ESTABLISHED; axis split independently confirmed by
     the real model)
   - execution-limitation-statement.md (8 documented limitations, none
     blocking v0.5)
   - residual-backlog.md (P1/P2/P3, none blocking)
   - operator-handoff.md (exact zsh commands to reproduce)
   - artifacts/ (wheel + sha, 3 model artifacts + digests)
   - installed/ (ledger evidence, adversarial battery)

## Non-blocking residuals (documented)
- Ruff repo-wide lint baseline (2,721 findings, pre-existing).
- Plugin version axis NOT ESTABLISHED (v0.6).
- No OpenAI-compatible packaged driver (LM Studio live but unwrapped).
- Operator identity is local macOS user only.
- Verification requires clean worktree.

## Previous verdicts superseded
- STANDALONE_CAPT_CORE_HARNESS_PROVEN (provisional, fixed-function)
  -> superseded by this verdict for the packaged model operator.
- NOT_READY (closure gaps) -> resolved: manifest, deselection
  accounting, worktree hygiene, raw authority matrix, version map,
  handoff, limitation statement, backlog all now present.
- CAPT_MODEL_OPERATOR_NOT_PROVEN_WITH_ACTUAL_EXHAUSTED_BLOCKER
  (rejected by user as real-but-not-exhausted) -> superseded: the
  missionId/taskId reference path was implemented, proven, and shipped.
- CAPT_MODEL_OPERATOR_NOT_PROVEN_WITH_ACTUAL_EXHAUSTED_REFERENCE_PATH
  (invalid premature declarations) -> superseded by this verdict.
