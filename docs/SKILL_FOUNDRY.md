# CAPT Solo v0.4 — Skill Foundry

The Skill Foundry converts verified procedures into publishable, governed
skills. It is the production surface for "CAPT can do X" claims.

## Lifecycle

```
candidate -> generated -> validating -> validated -> reviewing -> approved -> published
                                                                          -> deprecated -> revoked
```

- **candidate**: created from a verified procedure (`create_candidate`).
- **generated**: `build_skill` produces a `Skill` from the candidate.
- **validating**: `validate` runs the 12-stage harness.
- **validated**: harness passed; skill is sound but not yet reviewed.
- **reviewing**: `submit_for_review` queues for human/agent review.
- **approved**: `approve` records a named reviewer.
- **published**: `publish` records a CTP receipt; skill is now usable.
- **deprecated / revoked**: governance actions.

`approve` is NOT `publish`. A skill may be approved but never published; a
published skill carries a CTP receipt linking the publication to an actor.

## Key APIs

- `SkillFoundry.create_candidate(procedure_id)` -> candidate_id
- `SkillFoundry.build_skill(candidate_id, name=, verification_requirements=, ...)`
- `SkillFoundry.validate(skill_id, ValidationHarness)` -> ValidationReport
- `SkillFoundry.submit_for_review(skill_id)`
- `SkillFoundry.approve(skill_id, approver=)`
- `SkillFoundry.publish(skill_id, ctp_tx_id=)`
- `SkillFoundry.get(skill_id)`, `get_by_name(name)`

## Implemented

- Full 7-state lifecycle with explicit transitions.
- 12-stage validation harness (schema, idempotency, determinism, io_contract,
  failure_path, rollback, secret, proof, compatibility, conflict, trust,
  governance).
- Rollback strategy required (>=10 chars); empty rollback blocks validation.
- Permission allow-list enforced (`ALLOWED_PERMISSIONS`).
- Proof requirements declared and checked against source-procedure evidence.
- CTP receipt on publish.

## Experimental

- Composition of skills into workflows (see Composition Engine).
- Workflow proof independence (a composed workflow does NOT inherit component
  verification — see Workflow Proof Engine).

## Future

- Automated review assignment.
- Cross-skill conflict resolution beyond name collision.
- Sandboxed live execution of skill workflows.

## Limitations

- Skills are local-first; no remote execution or federation.
- Validation is static + evidence-based; it does not guarantee runtime safety
  in all environments.
- Composition requires all components to be published.

## Security Boundaries

- No skill may execute with elevated privileges beyond its declared
  permissions.
- Secret patterns in skill definitions are rejected by the harness.
- Published skills never overwrite local canonical skills silently.
- Rollback strategy is mandatory; a skill without one cannot be validated.

## Verification

- `tests/test_v04_foundry.py` (skill generation, validation, publish, rollback).
- `tests/test_v04_cli.py` (CLI skill subcommands).
- `tests/test_v04_plugin.py` (plugin skill tools).
- `verify_runtime.py` exercises build -> validate -> publish end to end.
