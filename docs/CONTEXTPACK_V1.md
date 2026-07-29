# ContextPack v1

ContextPack v1 is CAPT Core's local, deterministic context exchange format. It
adapts existing mission, evidence, retrieval/context-builder, AntiToken, and
receipt data into a portable working set. It does not call models, contact a
network, persist a pack automatically, sign data, or execute recovery.

## Construction and validation

```python
from capt_solo.contextpack import build_context_pack, validate_context_pack

pack = build_context_pack(
    mission, intent, assumptions,
    invariants=invariants, evidence=evidence, memory=memory, receipts=receipts,
    rendered_context=rendered_context, token_budget=budget,
    evaluation_clock="2026-07-28T00:00:00Z", confidence=0.8,
    assumption_review_status="reviewed_none_found",
    protected_fact_review_status="reviewed",
)
validation = validate_context_pack(pack)
if validation.status != "PASS":
    # Candidate is not usable; inspect typed blocks and remediation.
    raise RuntimeError(validation.to_dict())
```

The pack is deeply immutable and its digest covers its semantic fields. The
validation result is separate and does not mutate the candidate. It compares
protected facts derived from source records against the rendered context, so
the rendered text cannot define its own truth.

## Determinism and compatibility

Use an explicit timezone-bearing evaluation clock. With identical semantic
inputs and clock, ContextPack v1 produces canonical JSON and the same digest.
Strict parsing rejects unknown semantic fields. Compatibility-inspection mode
reports unknown fields without silently dropping them or recalculating a valid
digest.

Token accounting always names its measurement status. `heuristic_estimated`
does not claim model-exact token counts. A declared budget overflow is a typed
`BUDGET_BLOCK`.

## Boundaries

ContextPack v1 is an additive RC contract. Investigation journals, persisted
decisions, context scores/diffs, attention and scheduler logic, hierarchical
memory/HMC paging, strategy, and cognitive garbage collection are deliberately
deferred. See the [design contract](superpowers/specs/2026-07-28-contextpack-v1-design.md).
