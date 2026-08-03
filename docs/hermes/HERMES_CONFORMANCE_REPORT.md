# Hermes Conformance Report

> **Precise status (human-readable): `CAPT_HERMES_EXECUTION_DRIVER_PROVEN`**
>
> The earlier broad token `CAPT_HERMES_CONFORMANCE_PROVEN` is intentionally
> narrowed here. This work proves a *genuine external Hermes ExecutionDriver* —
> a real Hermes process receives a bounded read-only CAPT work order, performs
> its own internal model call, returns untrusted output, and stays outside
> CAPT's authoritative state and trust-promotion boundary. It does **not**
> establish per-model-turn CAPT interception, Mode B bootstrap-bridge ownership,
> suppression of every internal Hermes model decision, OS-level sandboxing,
> repository-write governance, complete Hermes feature conformance, or
> production readiness. The narrower token is the accurate one; the broader
> token, if any tooling expects it, should be treated as equivalent to this
> precise classification and not as a stronger claim.

Branch: `feat/capt-runtime-hermes-execution-driver`
Base: `5fb323d6edd8511b687eaec9f6656fc4b4d0b320` (`capt-runtime-m0`)
Environment: macOS 26.4.1 · CPython 3.12 (`/opt/homebrew/bin/python3.12`) · pytest

## 1. Verification commands and results

| # | Command | Exit | Result |
|---|---|---|---|
| 1 | `python3.12 -m py_compile capt_runtime/drivers/hermes.py tests/capt_runtime/test_hermes_driver.py tests/capt_runtime/hermes_e2e_proof.py` | 0 | COMPILE_OK |
| 2 | `git diff --check` | 0 | no whitespace errors |
| 3 | `pytest tests/capt_runtime/test_hermes_driver.py -q` | 0 | **28 passed** |
| 4 | `pytest tests/capt_runtime/test_m0b_driver.py -q` | 0 | **51 passed** (frozen suite, unchanged) |
| 5 | `pytest tests/capt_runtime -q` | 0 | **136 passed** |
| 6 | `pytest -q` (full repository) | 0 | **497 passed, 44 skipped** |
| 7 | `python3 tests/capt_runtime/hermes_e2e_proof.py` | 0 | real Hermes run + swap + replay |
| 8 | `ruff check --select E,F <new files>` | 0 | **All checks passed** |
| 9 | `ruff check --select S105,S106,S107,S608 capt_runtime/drivers/hermes.py` | 0 | no hardcoded secrets |
| 10 | Removal proof (see §4) | 0 | 51 M0-A + 51 M0-B pass without the driver |

### Notes on lint scope

The repository has **no ruff configuration**. Full default-ruleset ruff reports
472 pre-existing findings across `capt_runtime/` (45 in the frozen reference
driver alone), so a whole-repo ruff gate is not a meaningful pass/fail signal on
this baseline. The gate applied was `--select E,F` (real errors, not style
opinions) on the newly added files: **0 findings**. Baseline `E,F` on the frozen
`capt_runtime/` is 64 findings — untouched by this branch.

`ruff format --check` was **not** used as a gate: the existing codebase is not
ruff-formatted, so it would report the entire repository as unformatted. Applying
it would have produced a large unrelated diff across frozen files.

### Not run, and why

| Check | Status |
|---|---|
| TypeScript build | **N/A** — no TypeScript in this repository |
| Schema generation / drift | **N/A** — `contracts/` is byte-identical on this branch; no schema was regenerated because none was changed |
| mypy / pyright | not configured in this repository; Pyright ran via the editor LSP during authoring and reported 0 diagnostics on the final files |
| Dependency/licence audit | no dependency was added; `capt_runtime/drivers/hermes.py` imports stdlib only |

## 2. Frozen-contract integrity

```
git diff --stat 5fb323d..HEAD -- contracts/           →  (empty)
git diff --stat 5fb323d..HEAD -- tests/capt_runtime/test_m0b_driver.py  →  (empty)
git tag --list 'capt-runtime-m0'                      →  capt-runtime-m0 (unmoved)
```

No frozen contract, no frozen test, and no frozen schema was modified. The
Hermes driver validates against the **existing** `ExecutionDriverDescriptor` and
`ExecutionDriverWorkOrder` definitions with no schema edit.

## 3. Test inventory (28 new tests)

Contract / mapping: descriptor validates against the frozen contract; driver
satisfies the `ExecutionDriver` protocol; registry accepts the descriptor and
classifies it `untrusted`; registry rejects identity spoofing; missing executable
raises instead of fabricating.

Context containment: prompt derives only from the ContextSlice (8 forbidden
governance tokens asserted absent); minimal env excludes credentials by name and
value; credential-shaped extras are refused.

Forged authority: 6 parametrised forgery payloads rejected; benign output accepted.

Capability: write operation rejected before Hermes is contacted; expired lease
blocks dispatch; revoked lease blocks dispatch; wrong-driver lease blocks
dispatch; write-capable slice refused.

Lifecycle: unknown-run inspect/cancel raise; reconcile of an unknown run reports
`external_state_unknown` rather than success; timeout budget fails closed;
duplicate `driverRunId` rejected at the driver.

Real runtime: identity probe; full governed read-only run with a live process.

Removal: CAPT runtime intact with the driver module deleted; reference driver
still completes the read-only proof standalone.

## 4. Removal proof (executed)

`capt_runtime/drivers/hermes.py`, `tests/capt_runtime/test_hermes_driver.py`, and
`tests/capt_runtime/hermes_e2e_proof.py` were physically moved out of the tree.

| Check | Result |
|---|---|
| `import capt_runtime, capt_runtime.driver_host, capt_runtime.drivers.openharness` | OK |
| M0-A suite (contracts, ledger, aggregates, capability, claim, replay, authority) | **51 passed** |
| Frozen M0-B suite | **51 passed** |
| All `tests/capt_runtime` | **108 passed** |
| Reference driver acceptance scenario | **1 passed** |
| `git status --short contracts/` | empty — contracts unchanged |

Files were then restored; `tests/capt_runtime` returned to **136 passed**.

## 5. Swap proof (executed)

The same bounded work order was run through the real Hermes driver and through
the CAPT reference driver against the same fixture repository.

| Property | Result |
|---|---|
| Both reached `verified` | true |
| Both left the target repository byte-identical | true |
| Both produced the same bounded ClaimGuard-accepted statement | true |
| Both reconciled to `reconciled_completed` | true |
| Artifacts distinct (no substitution) | true |

Equivalent CAPT semantics, different prose — as required.

## 6. Restart / reconciliation (executed)

Checkpoint `cp-hermes` created; full replay and checkpoint-tail replay produced
equivalent state (`replayEquivalent: true`, 8 events applied, 0 re-applied after
checkpoint). A **separate OS process** (`tests.capt_runtime.restart_process`)
replayed the ledger and produced an identical digest:

```
full_digest   = sha256:b82feb61ce120acf71d420e7074d7f657b6d7a57b0b73e290f12dd5b90e5c3e1
replay_digest = sha256:b82feb61ce120acf71d420e7074d7f657b6d7a57b0b73e290f12dd5b90e5c3e1
exit code 0
```

No duplicate execution occurred on replay.

## 7. Read-only proof properties

| Required property | Status | Evidence |
|---|---|---|
| Target hashed before and after | met | `048716dd…389c90` identical both sides |
| No repository mutation | met | digest equality asserted in code, not narrated |
| Staging-only artifact creation | met | `realpath` containment; assertion on path prefix |
| Read-only capability grants | met | lease ops: `RepositoryRead`, `FilesystemRead`, `ArtifactCreate`, `AnalysisOnly` |
| Minimized ContextSlice | met | 8 governance tokens asserted absent from the prompt |
| Real Hermes execution | met | PID 51294, exit 0, 11.80 s |
| Untrusted observation ingestion | met | `trust: untrusted` recorded at ingest |
| Independent CAPT artifact verification | met | digest recomputed by CAPT, not trusted from the driver |
| Bounded ClaimGuard decision | met | bounded accepted; `"The issue was fixed."` rejected |
| Checkpoint / restart / reconciliation / replay | met | §6 |
| No git writes, commits, pushes during the proof | met | `noGitMutation: true` |

## 8. Honest gaps

* Mode A does not intercept per-model-turn or per-tool-call activity inside the
  Hermes process. Stated in the ADR and the ownership trace; not claimed anywhere
  as achieved.
* Bridge-specific adversarial tests (socket auth failure, stale turn ID, runner
  crash, bridge impersonation, bridge disconnect) are **not applicable** to
  Mode A — there is no socket and no runner. The equivalent Mode A failure modes
  (process crash, non-zero exit, timeout, empty output, duplicate run, missing
  executable, identity spoof, forged authority) are all tested.
* The full-repo ruff style gate was not applied; see §1 for the reason and the
  narrower gate that was applied instead.
