# CAPT Runtime M0-A — Triple-Recursion Ledger

This ledger records the auditable findings from the three-pass process applied
to every substantial artifact (ADR, schema, generator, runtime, tests, docs).
Per the mission, only auditable findings and decisions are recorded — not
hidden chain-of-thought.

Pass 1 = Construct, Pass 2 = Adversarial review, Pass 3 = Reconcile.

## Findings

| # | Artifact | Pass 2 finding | Correction | Files | Evidence | Residual |
|---|----------|---------------|-----------|-------|----------|----------|
| A | aggregates | `OWNED_FIELDS` conflated authoritative ownership with read-only references (missionId/taskId shared across aggregates), so the disjointness check was meaningless | Split into `OWNED_FIELDS` (qualified, e.g. `mission.state`) vs `REFERENCE_FIELDS`; test asserts zero overlap | aggregates/*.py, test_aggregates.py | `test_ownership_disjoint` passes; 0 overlaps | none |
| B | generator | Python dataclass aliases evaluated eagerly before variant types existed → `NameError` on import | Topological emit order (`topological_order`) so dependencies precede dependents | emit_python.py, schema_model.py | `import capt_contracts` clean; 121 types | none |
| C | constraint schema | `additionalProperties:false` plus a stray `details` ref left an unsafe generic escape hatch | Removed `details`; all constraint variants closed; `additionalProperties:false` enforced | constraint.schema.json | fixture `invalid-constraint-extra` rejected | none |
| D | capability | Grant and lease in separate streams would allow revoke-grant without invalidating live lease (window where revoked grant still has active lease) | Lease lives INSIDE the grant aggregate; revoke kills both atomically | capability.py | `test_revocation_blocks_use` | none |
| E | capability | A crash mid-effect was undetectable: no record that a consequential use was attempted | Two-phase reservation→finalization; open reservation = awaiting reconciliation after restart | capability.py, replay | `test_indeterminate_not_retried` | none |
| F | idempotency | Replayed command returned stored result but with `status:"applied"`, hiding that it was a replay | `commit_command` rewrites `status="idempotent"` on replay path | store.py | `test_duplicate_command_idempotent` | none |
| G | outbox | Risk that an event could be published before commit | `dispatch()` called ONLY after `commit_command` returns; outbox row written in same txn | store.py, services.py | `test_outbox_not_dispatched_before_commit` | none |
| H | claim | A completion claim could be accepted on an unverified or fabricated verification | `decide` checks authority BEFORE transition; verification must cite evidence the claim holds; `verifiedBy.kind` must be verification_plane | claim_driver.py, services.py | `test_unverified_completion_rejected`, `test_claimguard_cannot_fabricate_evidence` | none |
| I | capability grant | A grant with a valid shape but citing an unknown PolicyDecisionId would be authorized | `issue_grant` rejects grants whose `policyDecisionId` is not in the recorded ledger | services.py | `test_grant_cites_unknown_policy_rejected` (added) | none |
| J | event ordering | Timestamps alone could not order events safely across processes | Monotonic `globalSequence` + per-stream `streamVersion`; hash chain over payload digests | store.py | `test_stream_versions_monotonic`, `test_hash_chain_integrity` | none |
| K | checkpoint | A checkpoint could be declared `clean` while consequential work was unresolved | `recoveryState` DERIVED from open reservations, never supplied by caller | checkpoint.py | `test_recovery_state_derived_from_open_reservations` | none |
| L | checkpoint | Corrupted/incompatible checkpoint could seed replay with bad state | `verify_checkpoint` checks schemaVersion + runtimeVersion + integrityDigest BEFORE trust; order: compatibility then integrity | checkpoint.py | `test_corrupted_checkpoint_rejected`, `test_incompatible_schema_rejected` | none |
| M | cross-language | Python `%r` and TS `JSON.stringify` emitted different error strings for the same violation, silently breaking parity | Both use canonical JSON representation; fixtures assert byte-identical error lists | validator_py.txt, validator_ts.txt, fixtures | `test_cross_language_fixture_parity` (20 cases) | none |
| N | generator | Non-determinism risk from dict iteration / insertion order | Sorted traversal everywhere; no timestamps/paths/hostnames in output; `--out` dir param | generate.py, schema_model.py | `test_generation_reproducible` (byte-identical diff) | none |
| O | authority | Authority planes could be confused by a permissive default | Deny-by-default `require_authority` matrix; each act permitted for exactly one plane | authority.py | `test_plane_separation` (5 sub-assertions) | none |

## Triple-recursion coverage

- ADRs 0101–0111: each reviewed in Pass 2; findings A, C, D, E, G, H, I, J, K, L, O trace to specific ADRs.
- Schema (12 files): finding C; all discriminants closed.
- Generator + bindings: findings B, M, N.
- Runtime store/aggregates/services: findings A, D, E, F, G, H, I, J, K, L.
- Tests: each finding has a named test; 51 conformance tests, all passing.

## Residual uncertainty

- M0-A does not execute a real external driver; the DriverRun aggregate is
  contract + state model only (ADR-0111). The consequential boundary is
  modeled and tested via `check_lease` + reservation/finalization, not a live
  side effect. This is in scope per the mission ("do not introduce an external
  execution driver yet").
- Exactly-once external effects are NOT claimed (spec invariant 12). The proof
  covers effectively-once via idempotency, durable receipts, and reconciliation.
