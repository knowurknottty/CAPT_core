# CAPT-UPG-023: FastCDC / Content-Defined Chunking Evaluation

- **Campaign ID**: `CAPT-UPG-023`
- **Issue**: #94
- **Branch**: `upgrade/capt-upg-023-fastcdc-probe`
- **Disposition**: `BENCHMARK_HARNESS_IMPLEMENTED / FASTCDC_RUNTIME_PROBE_PENDING`

## Implementation

`benchmarks/chunk_stability.py` compares fixed-size and content-defined chunk identity under edits.

Implemented metrics:

- chunk count and size distribution;
- unique/duplicate chunk count;
- reused chunk identities with multiplicity;
- reusable chunk bytes;
- byte reuse ratio;
- post-edit chunk churn ratio.

The module provides an optional `fastcdc` adapter. Missing or failing adapter/dependency is reported explicitly rather than silently replaced with a different algorithm.

Every comparison explicitly records:

```text
llmPrefixCacheClaim = false
providerCacheEvidence = null
```

This item therefore does not resurrect the unsupported claim that FastCDC automatically improves LLM prompt-prefix caching.

## Tests authored

`tests/test_chunk_stability_probe.py` validates the scoring machinery using a transparent delimiter-based content-defined fixture:

- a prefix insertion demonstrates the benchmark can detect chunk-identity stability advantages when they exist;
- duplicate chunks are matched by multiplicity;
- fixed-size chunking/summary is deterministic;
- no provider-cache claim is emitted.

The delimiter fixture is a test of the **benchmark scorer**, not evidence for FastCDC itself.

## Evidence boundary

No exact-head pytest execution and no real FastCDC adapter run is available in the connected environment.

Required probe completion:

1. install/resolve an approved FastCDC implementation in an isolated benchmark environment;
2. run representative insert/delete/replace/append/repetition edits over CAPT memory/artifact/repository corpora;
3. compare against fixed-size chunks for reuse, churn, dedup and runtime;
4. decide `PROBE_COMPLETE_ACCEPT` or `PROBE_COMPLETE_REJECT` from those results;
5. keep any provider-prefix-cache experiment separate.
