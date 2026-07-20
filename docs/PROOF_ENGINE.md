# CAPT Solo v0.4 — Proof Engine

The Proof Engine records evidence objects and aggregates them against
declared requirements. It is the epistemic backbone: no capability or skill is
reported as verified without a satisfied proof aggregate.

## Evidence Model

An `Evidence` object has: `type` (from `KNOWN_EVIDENCE_TYPES`), `source`,
`hash`, `trust` (0.0–1.0), `scope`, `created_at`, `expires_at`. Evidence older
than `DEFAULT_EVIDENCE_TTL` (90 days) is treated as stale and excluded from
aggregation unless renewed.

## Requirements & Aggregation

- `ProofEngine.set_requirements(scope, [ProofRequirement(type, min_count, scope, min_trust)])`
- `ProofEngine.aggregate(capability_id)` -> `ProofAggregate`
  - `satisfied`: all requirements have `have >= min_count` with valid, in-scope,
    sufficiently-trusted evidence.
  - `satisfied_requirements` / `unsatisfied_requirements`: per-requirement detail.
  - `evidence_count`: number of valid evidence objects.

## Implemented

- Evidence recording with type/source/hash/trust/scope.
- Requirement declaration per scope.
- Aggregation with staleness (TTL), scope matching, trust threshold.
- Idempotent re-aggregation.

## Experimental

- Harness-generated proof types (`static_analysis`, `fixture`, `execution`,
  `output`, `failure_path`, `rollback`, `secret`, `schema`) are produced by
  `validate()` after the proof stage passes; they are satisfiable when the
  skill carries supporting evidence from its source procedure.

## Future

- Cross-scope evidence composition.
- Automated evidence renewal.

## Limitations

- Aggregation is evidence-count based; it does not model causal sufficiency.
- Trust is operator-assigned, not derived.

## Security Boundaries

- Evidence hashes are content-addressed; tampering is detectable.
- Stale evidence is excluded by default.
- No evidence is auto-generated outside the harness validation path.

## Verification

- `tests/test_v04_foundry.py` (proof aggregation, requirements).
- `verify_runtime.py` (proof_aggregate, capability_verify).
