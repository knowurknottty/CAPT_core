# CAPT Hermes Skill — Acceptance Report

Skill: `capt-core-runtime` (namespace `capt`)
Target repository: `/Users/knowurknot/capt-solo`
Skill worktree: `/Users/knowurknot/capt-core-skill-worktree` (branch `feature/hermes-capt-core-runtime-skill`)
Canonical CAPT: capt-solo 0.5.0 (editable install at `/Users/knowurknot/capt-solo`)
Interpreter: `/Users/knowurknot/capt-solo/.venv/bin/python` (Python 3.12.13)
Selection source: `explicit:CAPT_ACCEPT_PY` (deterministic; see interpreter-hardening note)

---

## Final Status

`CAPT runtime skill release-ready for bootstrap-governed use; Hermes tool-loop enforcement remains observational and unverified.`

---

## Verdict

| Check | Result | Evidence |
|---|---|---|
| Unit tests (pytest) | **28 passed** | `acceptance-evidence/canonical-20260801T033050Z/08-test-results.txt` |
| Canonical acceptance | **PASS** (exit 0) | `acceptance-evidence/canonical-20260801T033050Z/99-harness-result.json` |
| Adversarial matrix (12 scenarios) | **12/12 PASS** | `acceptance-evidence/adversarial-20260801T033113Z/MATRIX.json` |
| External replay | **PASS** (continuity PROVEN) | `acceptance-evidence/external-replay-20260801T033139Z/replay-verdict.json` |
| Schema validation | **VALID** (0 errors) | `acceptance-evidence/canonical-20260801T033050Z/04-schema-validation.txt` |
| Hash verification | **29/29 OK** | `shasum -a 256 -c MANIFEST.sha256` |
| Owner-state isolation | **UNCHANGED** (21 files / 6 checkpoints) | `07-isolation-report.json`, adversarial `MATRIX.json` |
| Secret scan | **0 hits** across 360 evidence files | see Phase 8 scan |
| Interpreter determinism | **explicit, reproducible** | `01-environment-report.json` → `interpreter` block |

**Production-ready: YES** — all three suites (canonical acceptance, adversarial
matrix, external replay) pass against the post-hardening code, with evidence
generated after the interpreter-determinism fix.

**Orinth adapter: READY FOR ORINTH VALIDATION** (not ORINTH VERIFIED — see
`CAPT_SKILL_ORINTH_ADAPTER_GUIDE.md`).

---

## Verified facts

1. The skill boots a CAPT mission through the canonical `capt --json agent status`
   CLI and emits a schema-valid boot report (`03-boot-report.json`, schema
   `capt-core-runtime/boot-report/v1`).
2. A checkpoint is written and reloaded in a separate process
   (`05-checkpoint-receipt.json`, `reload_verified: true`).
3. The original boot process is terminated; resume runs in a fresh process with
   a different PID and different session_id; `continuity_verdict=PROVEN`,
   `transcript_inheritance=none`.
4. The 12 adversarial scenarios each fail safely and truthfully (see matrix).
5. External replay recovers continuity from explicitly-persisted artifacts only,
   in a fresh clone at a new path, with no transcript, no shared temp root,
   and no unrecorded environment variables.
6. Owner CAPT state (`~/.capt-solo`, `capt-solo/.capt/checkpoints`) is never
   written by any harness run; fingerprint 21 files / 6 checkpoints unchanged.
7. Interpreter selection is deterministic: `CAPT_ACCEPT_PY` is passed explicitly
   to every script; no ambient venv activation or `command -v python` fallback
   is used.

## Observed behavior

- `capt_execution_mode` is reported as `GOVERNED` **only** because the CAPT gate
  (`MemoryUseGate`) authorized the boot. This describes the CAPT execution path.
- `hermes_session_mode` is `BOOTSTRAP_DEGRADED` in every artifact. Hermes
  plugin `pre/post_tool_call` hooks are **observational** — tool authorization is
  NOT runtime-enforced in Hermes. This is stated explicitly in every report and
  in the doctor's `hermes.tool_auth` row.

## Inferred behavior

- A new ContextPack is rebuilt per boot (digests differ between boot and resume
  by design). This is expected, not a defect.
- Session ids are per-process; differing session ids between boot and resume are
  the expected signal of a genuine fresh-process resume.

## Unverified claims

- **Orinth compatibility is NOT verified.** The adapter guide specifies how to
  run the skill under Orinth, but no Orinth session has executed it. Label is
  `READY FOR ORINTH VALIDATION`, not `ORINTH VERIFIED`.
- **Metaphysical identity / complete cognitive equivalence** across replays is
  not claimed. External replay proves *persisted-state recovery* and *semantic
  identity* of selected fields, not that the two runs are cognitively identical.

## Known limitations

1. `hermes_session_mode: BOOTSTRAP_DEGRADED` — Hermes tool-loop enforcement is
   not proven. GOVERNED applies to the CAPT gate only.
2. The harness allocates its own temp `CAPT_SOLO_HOME` (defense by construction);
   an ambient owner-pointing `CAPT_SOLO_HOME` is ignored unless explicitly
   overridden via `CAPT_ACCEPT_HOME` (which is then refused pre-write if it
   resolves to owner state).
3. External replay requires the workspace basename to match the checkpoint's
   `project_id` (CAPT's `FOREIGN_WORKSPACE` guard). This is a real CAPT
   constraint, documented and respected — not worked around.
4. `shellcheck` is not installed in this environment; `bash -n` is the strongest
   available syntax check. All 9 scripts pass `bash -n`.

## Failed tests

- None in the final post-hardening run. (Pre-hardening, the unit suite reported
  provisional 23/23; on re-run against the original uncommitted scripts it was
  actually 19/23 due to PATH/env gaps in the test harness — fixed by making the
  test `run()` helper inject the canonical venv onto PATH and set
  `CAPT_ACCEPT_PY`. The "23/23" was therefore a misreported number; the truthful
  current count is 28/28 including 5 new interpreter-determinism tests.)

## Deferred work

- Orinth cross-model validation run (separate session; see adapter guide).
- A pinned, non-editable CAPT distribution install (currently editable).
- CI wiring to run the three harnesses on every push.

---

## Evidence directory and manifest

- Canonical: `acceptance-evidence/canonical-20260801T033050Z/`
  Manifest SHA256: `f7636d8c6d16bacc3a3d291136eaff516dee86f907bdb08ecbf652e5e7d40700`
- Adversarial: `acceptance-evidence/adversarial-20260801T033113Z/`
  Manifest SHA256: `cca022d10174d024faf38c044eaa4c5fb0ed9b8d2a9bde10bdd15d0485c0264a`
- External replay: `acceptance-evidence/external-replay-20260801T033139Z/`
  Manifest SHA256: `7cfd8f69566e1c47753edbbd32ac688473143fb5a6f76a0cbaef1f6c77c76990`

## Interpreter-hardening note

Before this fix, `capt-doctor.sh` resolved Python via `command -v python ||
command -v python3` and activated `$WS/.venv` if present — both ambient-state
dependent. An ad-hoc probe running the doctor without the venv on PATH produced
false `WRONG_CHECKOUT` / `WRONG_PYTHON` failures. A shared
`scripts/capt-select-python.sh` now selects the interpreter by strict precedence
(explicit `CAPT_ACCEPT_PY` → workspace venv → PATH python3 → PATH python →
deterministic failure), records the selection source, and is exported to every
downstream script and harness. 5 new regression tests prove: explicit override
wins over system python, missing override fails precisely, explicit valid
interpreter yields canonical identity, CWD shadowing is detected without
switching interpreters, and two fresh shells reproduce the same identity.
