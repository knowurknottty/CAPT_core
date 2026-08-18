# CAPT-UPG-020: Reciprocal-Review Effectiveness Benchmark

- **Campaign ID**: `CAPT-UPG-020`
- **Issue**: #88
- **Branch**: `upgrade/capt-upg-020-reciprocal-benchmark`
- **Disposition**: `HARNESS_IMPLEMENTED / EMPIRICAL_RUN_PENDING`

## Implementation

`benchmarks/reciprocal_review.py` scores observed trials across five modes:

- self review;
- naive agreement;
- independent reviewer;
- deterministic verification;
- independent reviewer + deterministic verification.

It computes confusion-matrix counts, precision, recall, F1, false-rejection rate, trial count, and optional mean token/cost/latency values.

The harness enforces:

- independent reviewer identity must differ from generator identity;
- deterministic verification modes must name a verification domain;
- consensus is explicitly not verification;
- no model calls or fabricated trial results occur in the scorer.

`benchmarks/reciprocal_review_trials.template.json` is explicitly marked a template/non-evidence artifact.

## Tests authored

`tests/test_reciprocal_review_benchmark.py` covers scoring, separation-of-duty validation, verification-domain requirements, and all-five-mode comparison without inventing a winner.

## Evidence boundary

No populated observed CAPT benchmark dataset has been run in the connected environment. Therefore no claim that reciprocal review improves defect detection is accepted yet.

Current evidence class:

`BENCHMARK_HARNESS_IMPLEMENTED / TESTS_AUTHORED / EMPIRICAL_EFFECTIVENESS_UNMEASURED`

Required probe completion:

1. generate a controlled defect corpus;
2. execute all five modes under recorded model/verification identities;
3. save exact run receipts and evidence refs;
4. score them with this harness;
5. compare defect-detection benefit against false-rejection/token/cost/latency tradeoffs.
