# CAPT-UPG-013: ContextPack Merkle / Component Provenance Experiment

- **Campaign ID**: `CAPT-UPG-013`
- **Issue**: #77
- **PR**: #78
- **Rebuilt base**: corrected CAPT-UPG-012 @ `94b118259ecffe0c855d7202100e7c8b5c4cf14d`
- **Disposition**: `IMPLEMENTED_PENDING_EXECUTION_PROBE`

## Scope implemented

`capt_runtime/context_merkle.py` provides an explicitly non-authoritative component-provenance experiment over ContextPack data:

- fixed component identities/order for policy, usage, selection, exclusions, compression, and lineage;
- deterministic component leaf digests and binary Merkle root;
- changed/unchanged component localization;
- explicit preservation of the existing canonical `contextPackDigest` contract identity;
- explicit statement that Merkle identity does not imply provider prompt-cache behavior;
- a separate exact prompt-prefix serialization plan with independent prefix/full-prompt digests.

`tests/capt_runtime/test_context_merkle.py` covers deterministic roots, local invalidation, unaffected-leaf stability, and separation of stable-prefix identity from full-prompt changes.

`scripts/context_merkle_probe.py` measures local construction/invalidation only and explicitly emits `providerCacheClaim: false`.

## Verification boundary

This item was rebuilt scope-only on the corrected 012 stack. No exact-head pytest or probe result is claimed from this environment.

Required:

```bash
pytest tests/capt_runtime/test_context_merkle.py
python scripts/context_merkle_probe.py
```

Any provider-cache claim requires a separate provider-specific experiment.
