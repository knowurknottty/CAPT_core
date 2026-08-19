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

It computes confusion-matrix counts, precision, recall, F1, false-rejection rate, trial count, and optional mean token/cost/latency values. Undefined ratios and unrecorded optional metrics remain `null` rather than being misreported as measured zero.

The harness enforces:

- independent reviewer identity must differ from generator identity;
- deterministic verification modes must name both a verification domain and verification evidence reference;
- every observed trial must identify its case, exact case digest, run, ground-truth evidence, and run evidence;
- a case ID may not silently change digest, defect label, or ground-truth reference across modes;
- all five modes must cover the same case set before cross-mode comparison is eligible;
- consensus is explicitly not verification;
- no model calls or fabricated trial results occur in the scorer.

`benchmarks/reciprocal_review_trials.template.json` is explicitly marked a template/non-evidence artifact.

Schema v1.2 additionally requires a single controlled `protocolRef`, explicit `repeatId`, reviewer blinding assertions plus leakage-control evidence for independent-review modes, identical case+repeat observations across modes, class-balance accounting, and per-mode replicate metrics/variance. A populated five-mode corpus is only `empiricalInferenceEligible` when the case/repeat set is comparable, both defect and clean cases are present, at least two repeats exist in every mode, and blinding controls are satisfied. Eligibility is a methodological gate, not a claim that reciprocal review wins.

## Tests authored

`tests/test_reciprocal_review_benchmark.py` covers scoring, separation-of-duty validation, verification evidence requirements, duplicate trial rejection, ground-truth provenance, case-fingerprint consistency, zero-denominator handling, optional-metric missingness, and same-case-set comparison without inventing a winner.

## Evidence boundary

No populated observed CAPT benchmark dataset has been run in the connected environment. Therefore no claim that reciprocal review improves defect detection is accepted yet.

Current evidence class:

`BENCHMARK_HARNESS_HARDENED / TESTS_AUTHORED / EMPIRICAL_EFFECTIVENESS_UNMEASURED`

Required probe completion:

1. generate a controlled defect corpus;
2. execute all five modes under recorded model/verification identities;
3. preserve case digests and ground-truth provenance, and save exact run receipts/evidence refs;
4. score them with this harness;
5. verify reviewer blinding / leakage controls in the execution protocol;
6. compare defect-detection benefit against false-rejection/token/cost/latency tradeoffs, including class balance and repeated-run variance.
