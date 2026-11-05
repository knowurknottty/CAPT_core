# Quantum Leap v3 — Phase 2 bounded verification report

**Date:** 2026-10-19 (UTC)
**Repo:** knowurknottty/CAPT_core
**Working branch:** experiment/quantum-leap-v3-hardening
**Baseline pin:** e28b66504c422946a66409d0de12e71f1646aae6
**Scope:** read-only inspection of immutable Git objects; no runtime authority changes, model calls, provider spend, claim promotion, production checkout change, deployment, or service restart.

## Input integrity

Maintainer-supplied original claims corpus: `claims_v3_original.json`, 52 claims, SHA-256 `0cb55a016847d4c34951efb6bceccfe3505720ddda99cd7d6871973cb394bae3`. The encoding includes 34 author-labeled `full`, 13 `partial`, and five `none` fidelity mappings. The predicate compiler has eight kinds, not a general-purpose prose-to-DSL translator.

## Empirical results

| Git pin | WITHIN | EXCEEDS | UNSUPPORTED | INCONCLUSIVE | Full-fidelity WITHIN | D_proxy |
|---|---:|---:|---:|---:|---:|---:|
| c5b6f6a | 43 | 4 | 5 | 0 | 33 | 19 |
| 3f11800 | 43 | 4 | 5 | 0 | 33 | 19 |
| e28b665 | 42 | 5 | 5 | 0 | 32 | 20 |

The v3 predicate-status counts were reproduced after correcting an accidentally double-escaped test matcher introduced during this implementation. The original corpus was not rewritten to force agreement. The additional `EXCEEDS` at HEAD is `PU7`: 87 original top-level modules versus 88 now.

Other exceptions: `AS1a`, `AS1b`, `AS3` are *partial-fidelity predicate mismatches* and should not be presented as falsifications of Astra's broader prose. `PU8` uses `splitlines` while the original count used `wc -l` semantics. The five `UNSUPPORTED` cases cannot be resolved by static predicates in this vocabulary.

## Certainty debt — deliberately restricted proxy

`D_proxy = 52 - number of author-labeled full-fidelity claims with WITHIN predicate verdict`.

At HEAD, `D_proxy = 20`; earlier pins yielded `19`. The number is a **conservative obligation-counting proxy**, not evidence that 32 natural-language propositions have been semantically proved, and not a production Certainty Debt Ratchet.

All verifier outputs unconditionally include `semantic_entailment: NOT_ASSESSED` and `promotion_eligible: false`. Those flags must remain false until independent meaning-preservation checks, custody, and runtime integration have each passed.

## History and falsification sensitivity

Across **99 first-parent commits**, starting October 8, 2026 UTC, ten distinct claim IDs exhibited at least one predicate-status transition. Some are expected historical additions rather than regressions; `PU7` changed to `EXCEEDS` at e28b665.

At HEAD, **42/42 applicable true-predicate mutations were rejected**. These mutate the predicate itself, not source truth or natural-language meaning. They demonstrate a narrow level of test discrimination, not general soundness of a claim compiler.

## Tests and operational boundaries

The isolated Git-fixture regression suite completed **12/12** tests after correction, including nested symbol scope, open-schema failure, invalid regex handling, line convention, anchored-definition and mention forms, literal collection size, dynamic-constructor rejection, pinned reads, and non-promotability of results.

The first full-history call exceeded the broker's synchronous transport limit; durable CAPT Node status later confirmed a completed exit-0 operation and the JSON evidence file. No blind retry occurred. Operation ID: `ql-v3-phase2-history-mutations-20261019-11`.

## What this does *not* establish

- No automatic natural-language claim extraction/translation or verified entailment.
- No independently reviewed semantic truth labels.
- No integration with ClaimGuard, RuntimeService, EventStore, or the Learning Plane.
- No trusted evaluator isolation or split custody against a same-UID filesystem adversary.
- No assessment of the deployed RuntimeService revision.
- No automated gate preventing debt growth; the +1 here is observed, not yet enforced.

## Immediate next gates

1. Independently adjudicate claim-to-predicate meaning (including negative controls that preserve predicate truth but falsify prose).
2. Add a versioned, reviewer-attested mapping registry and immutable evidence references; define expiry semantics.
3. Run a shadow-only ratchet against source changes with a declared exception register and regression budgets.
4. Keep the generator arm (CCF+) closed until semantic and custody gates pass.
