# CAPT-UPG-013: ContextPack Merkle / Component Provenance Experiment

- **Campaign ID**: `CAPT-UPG-013`
- **Issue**: #77
- **Branch**: `upgrade/capt-upg-013-context-merkle`
- **PR**: #78
- **Implementation head at evidence creation**: `12168fb8590477d6173df0187f42c34be979e014`
- **Disposition**: `IMPLEMENTED_PENDING_EXECUTION_PROBE`

## Scope implemented

`capt_runtime/context_merkle.py` provides an explicitly non-authoritative component-provenance experiment over ContextPack data:

- fixed component identities/order for policy, usage, selection, exclusions, compression, and lineage;
- deterministic component leaf digests and binary Merkle root;
- changed/unchanged component localization;
- explicit preservation of the existing canonical `contextPackDigest` contract identity;
- explicit statement that Merkle identity does not imply provider prompt-cache behavior;
- a separate exact prompt-prefix serialization plan with independent prefix/full-prompt digests.

## Tests authored

`tests/capt_runtime/test_context_merkle.py` covers:

1. a selected-record digest change changes the `selection` component and root while unrelated component leaves remain stable;
2. equivalent ContextPack projections produce identical leaves/root;
3. changing content after a declared stable prefix keeps the prefix digest stable while changing the full-prompt digest; changing content before the breakpoint changes the prefix digest.

## Probe authored

`scripts/context_merkle_probe.py` measures only local tree-construction/invalidation behavior. It intentionally emits `providerCacheClaim: false` and must not be cited as provider cache evidence.

## Verification boundary

No exact-head execution evidence is available from the connected environment. Therefore no pytest or benchmark result is claimed.

Current evidence class:

`SOURCE_IMPLEMENTED / TESTS_AUTHORED / PROBE_AUTHORED / EXACT_HEAD_EXECUTION_NOT_OBSERVED`

Required before promotion beyond probe status:

```bash
pytest tests/capt_runtime/test_context_merkle.py
python scripts/context_merkle_probe.py
```

Any provider prompt-cache claim requires a separate provider-specific benchmark and is outside this item's current evidence.
