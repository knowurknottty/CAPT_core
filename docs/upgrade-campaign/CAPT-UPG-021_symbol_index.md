# CAPT-UPG-021: Discovery-Guided AST/Symbol Sparse Index

- **Campaign ID**: `CAPT-UPG-021`
- **Issue**: #90
- **Branch**: `upgrade/capt-upg-021-symbol-index`
- **Disposition**: `PROBE_IMPLEMENTED / EMPIRICAL_REPOSITORY_BENCHMARK_PENDING`

## Implementation

`capt_runtime/discovery/symbol_index.py` consumes only accepted file candidates from a supplied SEAL/Discovery result. It re-checks that candidate paths resolve under the discovery root and never discovers additional files.

Current probe scope:

- Python AST class/function/method/async symbol extraction;
- stable symbol IDs and content digests;
- source-byte and per-symbol byte accounting;
- unsupported-language reporting;
- parse/read failure reporting;
- transparent lexical symbol selection with explicit selected + omitted lists;
- precision/recall and byte-reduction scoring against caller-supplied relevant symbol IDs.

The index is marked `derived_read_only`; sparse selection carries `sufficiencyClaim: false`, and metrics carry `contextSufficiencyProven: false`.

## Tests authored

`tests/test_discovery_symbol_index.py` covers:

1. only accepted SEAL file candidates are indexed;
2. unsupported source languages remain visible;
3. rejected candidates cannot leak into the index;
4. selected/omitted symbols and precision/recall/byte-reduction accounting;
5. syntax/parse failure remains visible rather than being silently treated as coverage.

## Evidence boundary

No exact-head test execution or real-repository precision/recall benchmark is available in the connected environment.

Current evidence class:

`SOURCE_PROBE_IMPLEMENTED / TESTS_AUTHORED / REAL_REPOSITORY_BENCHMARK_UNMEASURED`

Required empirical completion:

- run against representative repositories already admitted by SEAL;
- define labeled relevance sets for real tasks;
- measure precision, recall, token/byte reduction, missed dependencies, latency, and edit invalidation behavior;
- only promote automatic sparse-context selection if missed-context rates are acceptable.
