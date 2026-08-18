# CAPT-UPG-022: Tree-sitter Structural/Semantic Hashing Probe

- **Campaign ID**: `CAPT-UPG-022`
- **Issue**: #92
- **Branch**: `upgrade/capt-upg-022-tree-sitter-hash`
- **Disposition**: `PROBE_IMPLEMENTED / TREE_SITTER_RUNTIME_BENCHMARK_PENDING`

## Implementation

`benchmarks/tree_sitter_hashing.py` provides:

- normalized Tree-sitter-like named-node representation without source coordinates;
- anonymous punctuation/whitespace and comment-node exclusion;
- named-leaf text retention so identifier/literal edits invalidate hashes;
- whole-tree and named-subtree digests;
- changed/unchanged subtree-path comparison;
- optional `tree_sitter_language_pack` adapter that reports `dependency_unavailable` or `parse_unavailable` explicitly rather than pretending fallback results are Tree-sitter evidence.

Every result explicitly records:

```text
behavioralEquivalenceClaim = false
semanticEquivalenceClaim = false
```

Equal structural hashes are therefore only a candidate structural-identity signal for provenance/invalidation, not proof that two programs behave the same.

## Tests authored

`tests/test_tree_sitter_hashing_probe.py` covers:

1. deterministic normalized identity;
2. identifier/leaf changes invalidate hashes;
3. comment-only changes are excluded from structural identity in the normalized probe;
4. changed named-subtree paths remain visible;
5. no semantic/behavioral-equivalence claim is emitted.

## Evidence boundary

No exact-head test execution and no live Tree-sitter grammar benchmark is available in the connected environment. No production adoption is authorized.

Required empirical completion:

- run the probe with actual Tree-sitter grammars on representative CAPT-supported languages;
- measure stability under whitespace/comments/renames/literal changes/refactors;
- compare invalidation precision against file-content hashes and language-native AST approaches;
- quantify false stability / false invalidation before using it for test selection or cache invalidation.
