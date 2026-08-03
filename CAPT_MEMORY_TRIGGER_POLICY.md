# CAPT Memory Trigger Policy (M1-memory, ADR-DT-M1-MEM-001)

## Trigger interval

Fixed at **32,768 tokens** (`TRIGGER_INTERVAL_TOKENS` in
`capt_runtime/memory/policy.py`). Every trigger type has an independent step
count. Effective token thresholds are exact multiples of 32,768. No arbitrary
non-32k values are permitted; a raw token threshold that is not an exact
multiple is rejected by `tokens_to_steps` (see `test_48k_rejected`).

## Supported ladder

| Steps | Tokens |
|---|---|
| 1 | 32,768 |
| 2 | 65,536 |
| 3 | 98,304 |
| 4 | 131,072 |
| 5 | 163,840 |
| 6 | 196,608 |
| 7 | 229,376 |
| 8 | 262,144 |

The architecture supports further 32k increments without code changes beyond
configuration limits (`SUPPORTED_LADDER_STEPS` is documentation; the model safe
limit is the only hard ceiling).

## Validation

- zero → rejected (`min_steps=1`)
- negative → rejected
- non-integer → rejected
- above safe limit → rejected (`max_steps=model_safe_limit_steps`)
- raw non-multiple-of-32k → rejected by `tokens_to_steps`

## Trigger types (independent steps)

| Trigger | Purpose | Default (steps) |
|---|---|---|
| retrieval | governed memory query before planning | 8 |
| compression | compress/summarize active context | 8 |
| checkpoint | persist execution state + context refs | 8 |
| consolidation | episodic → semantic/procedural candidate | 8 |
| hardStop | suspend if safe construction impossible | 8 (model safe limit) |

## Precedence (narrowing only)

```
constitutional > runtime_policy > model_provider > project_policy
> operator_selected > driver_preference
```

`MemoryTriggerPolicy.with_update` enforces: a lower-authority source may not
widen a bound set by a higher authority. `effective_policy` resolves the
effective policy by taking the minimum across layers (highest authority wins,
operator narrows further).

## Persistence

`MemoryTriggerEngine` logs every policy change to `memory_policy_log`
(policy_version, policy_digest, previous_policy_digest, source, operator_id,
command_id, correlation_id, timestamp, effective_json). Reconnect/replay
reconstructs the exact effective policy via `reconstruct_policy(version)`.

## Source of truth

The runtime is the single writer. The desktop submits `update_memory_trigger_policy`
through the authenticated command path; it never mutates config or runtime state
directly. Hermes (driver) has no policy-write surface.
