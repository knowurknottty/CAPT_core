# Hermes Removal / Swap Proof

Both proofs were executed, not described.

## 1. Removal

`capt_runtime/drivers/hermes.py`, `tests/capt_runtime/test_hermes_driver.py`, and
`tests/capt_runtime/hermes_e2e_proof.py` were physically moved out of the working
tree, making the Hermes integration genuinely unavailable.

| Check | Command | Result |
|---|---|---|
| CAPT imports still work | `import capt_runtime, capt_runtime.driver_host, capt_runtime.drivers.openharness` | OK |
| Frozen M0-A tests pass | `pytest test_contracts test_ledger test_aggregates test_capability test_claim test_replay test_authority -q` | **51 passed** |
| Frozen M0-B 51-test suite passes unchanged | `pytest tests/capt_runtime/test_m0b_driver.py -q` | **51 passed** |
| All runtime tests pass | `pytest tests/capt_runtime -q` | **108 passed** |
| CAPT reference driver still operates | `pytest ...::test_m0b_read_only_acceptance_scenario -q` | **1 passed** |
| Frozen contracts unchanged | `git status --short contracts/` | empty |

Files were then restored and `pytest tests/capt_runtime -q` returned
**136 passed**.

Conclusion: CAPT has **no** hard dependency on Hermes. The integration is a leaf
module that can be deleted without affecting the frozen runtime.

## 2. Swap

The identical bounded work order (same fixture repository, same lease shape, same
operations, same read-only policy) was executed through both drivers in one run.

| Property | Hermes driver | Reference driver | Equivalent |
|---|---|---|---|
| Verification status | `verified` | `verified` | yes |
| Repository unchanged | true | true | yes |
| Bounded ClaimGuard statement | "Repository inspected in read-only mode." | same | yes |
| Overclaim rejected | `ClaimRejected` | `ClaimRejected` | yes |
| Reconcile result | `reconciled_completed` | `reconciled_completed` | yes |
| Artifact path | `hermes-analysis-dr-hermes-1.md` | `analysis-dr-ref-1.md` | distinct (no substitution) |
| Observation prose | LLM-authored analysis | deterministic file statistics | **intentionally different** |

Machine-checked assertion block from the run:

```json
{"bothVerified": true,
 "bothRepoUnchanged": true,
 "bothSameBoundedClaim": true,
 "bothReconciledCompleted": true,
 "artifactsDistinct": true}
```

The proof script exits non-zero if any of these is false.

Requirement met: **equivalent CAPT semantics, not identical prose.** The
observation text differs — as it must, since one is a language model's analysis
and the other is a deterministic scan — while every CAPT-authoritative outcome is
identical.
