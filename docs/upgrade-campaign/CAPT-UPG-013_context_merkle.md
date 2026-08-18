# CAPT-UPG-013 — ContextPack Merkle / Component Provenance Experiment

- **Campaign ID:** `CAPT-UPG-013`
- **Issue:** #77
- **PR:** #78
- **Base:** verified CAPT-UPG-012 @ `6f88d565df84e3ce41fc04e5ec145998bc4bf490`
- **Disposition:** `IMPLEMENTED_VERIFIED_AS_LOCAL_PROVENANCE_PROBE`

## Scope

`capt_runtime/context_merkle.py` is explicitly non-authoritative and provides:

- fixed ContextPack component identities/order for policy, usage, selection, exclusions, compression, and lineage;
- deterministic component leaf digests and binary Merkle root;
- changed/unchanged component localization;
- preservation of the canonical `contextPackDigest` contract identity;
- explicit `providerCacheHitClaim: false` semantics;
- a separate exact serialized prompt-prefix identity model, because provider caching depends on exact prefix layout rather than Merkle identity.

## Executable probe

`scripts/context_merkle_probe.py` now resolves the repository root itself, so the documented direct invocation works without an external `PYTHONPATH` workaround.

Observed locally on the repaired branch:

```text
3 passed
iterations: 1000
changedComponents: ["selection"]
meanMicroseconds: ~80.4
providerCacheClaim: false
```

This timing is an environment-specific local construction measurement, not a provider-cache benchmark and not a general performance guarantee.

## Verification boundary

The mechanism is verified as an internal provenance/invalidation probe only. Any claim about OpenAI, Anthropic, OpenRouter, or another provider's prompt-cache hit rate requires a separate provider-specific benchmark over actual serialized prompts and cache telemetry.

Exact-commit full-suite verification is recorded on PR #78 after this commit.
