# 04 — State, Recovery, Evidence, and Verification

## EventStore

Implementation: `capt_runtime/store.py` (`EventStore`). The authoritative local ledger is SQLite, append-only at the event level, with canonical JSON payload digests and a chained ledger digest.

Core duties:

```text
schema initialization
append/stream sequencing
optimistic concurrency/version checks
aggregate state replay support
ledger head identity
idempotency admission/completion
checkpoint persistence support
multi-process contention behavior
```

Never hand-edit `runtime.db`. Use RuntimeService/CLI or an isolated test state directory.

## Event ordering and aggregate ownership

- Aggregate classes live in `capt_runtime/aggregates/`.
- `MissionAggregate` and `TaskAggregate`: objective/work states.
- `CapabilityAggregate`: grants, leases, reservations, consumption.
- `ClaimAggregate`: proposed/decided claims.
- `DriverRunAggregate`: external run lifecycle/reconciliation.
- `HumanApprovalAggregate`: approval queue/decisions.
- `capt_runtime/replay.py`: reconstructs durable state from event streams; full and checkpoint replay must be equivalent.
- `capt_runtime/kernel.py`: command/event envelope construction, transition commits, invariants, checkpoint coordination.

Expected concurrency errors are explicit (`ConcurrencyConflict`, `IdempotencyConflict`, `IntegrityViolation`, `IllegalTransition`, `CapabilityDenied`, `CapabilityViolation`, `ReconciliationRequired`). They are guardrails, not invitations to bypass the store.

## Checkpoints

Implementation: `capt_runtime/checkpoint.py`.

A checkpoint records ledger head/event identity, manifest digest, and required artifact integrity. Key functions:

```text
create_checkpoint(store, checkpoint_id, created_at, policy_digest)
verify_checkpoint(manifest)
can_dispatch_consequential(manifest)
manifest_integrity_digest(manifest)
```

A checkpoint is a governed recovery boundary. It is not a snapshot permission to re-execute external work. `capt resume` resumes runtime service state; it preserves the no-repeat rule for uncertain external boundaries.

## Recovery on startup

`desktop/capt_runtime_service._reconcile_stranded_driver_runs()` runs before duplicate command callers are accepted. It inspects persisted DriverRuns and applies ordering-aware recovery:

- only ordering-proven no-dispatch states may be treated as non-executed failures;
- running/suspended external work becomes conservatively lost/suspended/indeterminate;
- authority consumption is preserved;
- reconciliation or explicit governed cancellation resolves the task;
- a duplicate command does not itself resume a crashed lifecycle.

Test-only crash injection is environment-gated with `CAPT_TEST_OUROBOROS_CRASH_AFTER`. It is inert for normal operators.

## Evidence

`capt_runtime/verification.py` and `desktop/desktop_runtime_client.py` supply evidence construction/projection.

Evidence examples:

```text
artifact hash evidence
command exit evidence
captured repository baseline/delta view
provider artifact path/digest
```

Artifact-hash evidence proves the designated artifact’s bytes matched the recorded digest at verification time. It does not promote provider response content into factual truth by itself.

## VerificationResult

Functions:

```text
capture_git_status(target_path)
verify_repository_unchanged(target_path, before_digest)
verify_no_git_mutation(target_path, before_git_status)
verify_artifact(path, expected_digest)
build_verification_result(...)
build_contradicted_verification_result(...)
```

Positive verification requires relevant invariants to hold. A failure constructs and persists a contract-valid contradicted verification record with real evidence IDs. This is intentionally not erased: contradiction is evidence about the run.

Provider execution uses a read-only target-root model. If the target changes during execution or a required artifact fails digest verification, task completion claim cannot be accepted. Work in a stable target directory and inspect `capt evidence`.

## ClaimGuard

`guard_claim(statement)` rejects prohibited/overclaiming language before the claim pipeline. For accepted bounded statements, RuntimeService proposes a Claim, records evidence and verification, then records a ClaimGuard decision. The final claim decision is CAPT state, not a provider declaration.

Remember:

```text
Provider: “I fixed it.”            → untrusted output, not a claim decision
Artifact hash matches              → evidence
Verification Result: verified      → verification support
ClaimGuard: accept                 → authorized acceptance of bounded claim
Task: succeeded                    → lifecycle completion after the above
```

## Operator inspection commands

```zsh
capt status
capt evidence
capt --json evidence
capt checkpoint
capt resume
```

`capt evidence` selects the first/most relevant mission if `--mission` is omitted. Use `--mission <id>` when inspecting a specific run. It displays mission spec, evidence, verification, and ClaimGuard projection. `--json` is preferable for preserving full structured output during diagnosis.

## Safe reset/testing pattern

```zsh
export CAPT_STATE_DIR="$(mktemp -d)"
capt start
# perform isolated test
capt evidence
capt stop
rm -rf "$CAPT_STATE_DIR"
unset CAPT_STATE_DIR
```

Do not delete a real `~/.capt` state directory to “clear a stuck run”; that destroys evidence/recovery context. Use cancellation/reconciliation or preserve a copy before any deliberate operator-led maintenance.
