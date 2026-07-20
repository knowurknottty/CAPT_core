# CAPT Solo v0.4 — Validation Harness

The Validation Harness executes a 12-stage pipeline against a `Skill` before it
can be published. It is the quality gate that separates a generated skill from
a publishable one.

## The 12 stages

1. **schema** — required skill fields present (skill_id, name, version,
   workflow, rollback_strategy); semantic version format.
2. **idempotency** — skill execution is deterministic / repeatable.
3. **determinism** — outputs are stable across runs.
4. **io_contract** — declared inputs/outputs match actual behavior.
5. **failure_path** — failure modes are documented.
6. **rollback** — rollback strategy present and >=10 chars.
7. **secret** — no secret patterns in the skill definition.
8. **proof** — declared verification requirements satisfied by source-procedure
   evidence (harness-generated types are produced after this stage passes).
9. **compatibility** — compatibility declaration recognized (capt-solo/python/
   hermes).
10. **conflict** — no name collision with published skills.
11. **trust** — trust metadata present and consistent.
12. **governance** — governance approval recorded before publish.

A stage may `pass`, `warn` (non-blocking), or `fail` (blocks publication). The
harness returns a `ValidationReport` with per-stage `StageResult` (status,
evidence_ids, warnings, failure_reasons, duration_ms, trace_id, artifacts).

## Implemented

- All 12 stages implemented and executed in order.
- `warn` vs `fail` distinction (warnings do not block).
- Proof stage checks declared requirements + supporting evidence.
- Rollback strategy enforced (>=10 chars).
- Secret scanning via `screen()`.

## Experimental

- Live sandbox execution of skill workflow (currently dry-run / fixture check).

## Future

- Automated io_contract inference from procedure runs.
- Cross-skill conflict resolution.

## Limitations

- Validation is static + evidence-based; it does not guarantee runtime safety
  in every environment.
- Sandbox execution is limited (fixture directory creation, not full run).

## Security Boundaries

- Unsafe command patterns (rm -rf, sudo, format) in workflow block validation.
- Secret patterns block validation.
- Disallowed permissions block validation.
- A skill without satisfied proof requirements cannot be validated.

## Verification

- `tests/test_v04_foundry.py` (skill validate, 12 stages).
- `tests/test_v04_workflow_proof.py` (workflow proof independence).
- `verify_runtime.py` (skill_validate).
