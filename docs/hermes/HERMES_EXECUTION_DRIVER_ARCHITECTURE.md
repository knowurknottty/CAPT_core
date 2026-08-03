# Hermes ExecutionDriver Architecture

## Module

`capt_runtime/drivers/hermes.py` — the only place a Hermes process is contacted.
Imports: Python standard library plus `capt_runtime.contracts` and
`capt_runtime.ingestion`. No `import hermes`.

## Surface

`HermesDriver` implements the frozen `ExecutionDriver` protocol exactly:

| Method | Behaviour |
|---|---|
| `describe()` | returns `DESCRIPTOR` (`driverId: hermes`, `writeCapable: false`) |
| `submit(work_order)` | refuses a write-capable slice, rejects a duplicate run id, validates the work order against the frozen contract, launches the real process, returns untrusted output |
| `inspect(run_id)` | driver-side view of run state; raises `KeyError` for unknown runs |
| `cancel(run_id, reason)` | SIGTERM to the process group, marks the run cancelled |
| `resume(run_id, input)` | refuses to resume a cancelled run |
| `reconcile(run_id)` | reports `external_state_unknown`; never asserts success |

`isinstance(HermesDriver(...), ExecutionDriver)` is asserted in the test suite.

## Execution sequence

1. `DriverHost.dispatch` rejects structurally unsafe operations.
2. `verify_lease` revalidates identity, mission, task, status, revocation,
   validity window, operation coverage, path scope, and budget.
3. `require("ExecutionDriverWorkOrder", …)` validates against the frozen schema.
4. `build_prompt(context_slice, operations)` derives the prompt from the
   ContextSlice alone.
5. `subprocess.Popen` with `shell=False`, explicit argv, `minimal_env()`,
   `cwd=target`, `start_new_session=True`.
6. `communicate(timeout=budgets.maxSeconds)`; on overrun the process **group** is
   SIGKILLed and `HermesDriverFailure` is raised.
7. Non-zero exit, empty output, or a forged-authority marker → raise. Never a
   fabricated observation.
8. A `DriverObservation` is built with `trust: untrusted`.
9. **CAPT** writes the staging artifact and computes its digest. Hermes never
   writes an artifact.
10. `DriverHost.ingest` → `validate_observation` (identity, run binding,
    duplicate/conflict) and `validate_artifact_candidate` (`realpath`
    containment, existence, digest match).
11. `DriverHost.verify` recomputes the target tree digest independently.
12. `ClaimGuard` bounds what may be asserted.
13. Reconcile, checkpoint.

## Failure semantics

| Condition | Behaviour |
|---|---|
| Executable missing | `HermesDriverUnavailable` |
| Non-zero exit | `HermesDriverFailure` with stderr tail |
| Budget exceeded | process group SIGKILL, `HermesDriverFailure` |
| Empty stdout | `HermesDriverFailure` |
| Forged authoritative marker | `IngestionRejection` |
| Write-capable slice | `HermesDriverFailure` before any launch |
| Duplicate run id | `HermesDriverFailure` before any launch |
| Lease invalid | `CapabilityViolation` before any launch |

There is no fallback path and no degraded-success path. Failure is always
reported as failure.

## Deliberate non-goals

* No `RuntimeAggregate`, `RuntimeManifest`, or `RuntimeIdentity` — explicitly out
  of scope.
* No repository-write authority.
* No new wire contract, no contract modification.
* No plugin-registry tools. The integration lives in `DriverRegistry`, which is
  where it belongs; the generic Hermes plugin registry is not used.
* No second bridge.
