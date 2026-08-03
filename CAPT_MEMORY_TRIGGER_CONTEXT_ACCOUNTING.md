# CAPT Memory Context Accounting (M1-memory, ADR-DT-M1-MEM-001)

## Authoritative path

`capt_runtime/memory/accounting.py` owns context accounting. It measures
current usage across all accounted components and computes the next 32k
trigger boundary.

## Accounted components (`ContextUsage`)

- system_instructions
- policy_constraints
- mission_spec
- task_graph
- current_messages
- selected_memory
- tool_schemas
- driver_instructions
- retrieved_documents
- artifacts
- model_output_reserve
- verification_reserve
- retry_reserve
- transport_overhead (where measurable)

## Token estimation

No exact tokenizer is available in this runtime. Estimation uses
`chars / 4.0` (English/code mixed). Every estimated value is labeled
**ESTIMATED** and the method (`chars/4.0 (ESTIMATED; no exact tokenizer
available)`) is recorded in the evaluation report (`estimationMethod`). When a
provider/runtime supplies measured token counts, `measured=True` overrides the
estimate and the confidence rises.

## Exposed fields (evaluation report)

- `estimatedTokens` / `measured` flag
- `estimationMethod`
- `confidence` / `errorMargin` (0.5 default for estimates)
- `reservedBudget` (model safe limit tokens)
- `remainingBudget`
- `nextTriggerBoundary`
- per-trigger state (`fires`, `boundary`, `tokens`, `steps`)

## Next boundary math

`next_trigger_boundary(current, steps) = ceil(current / interval) * interval`
where `interval = steps * 32_768`. A trigger fires when
`current >= boundary AND not already_fired_for_boundary` (idempotent).

## No character-count-as-token abuse

Character counts are never presented as unlabeled token counts. The estimate
is explicit and the assumption is recorded. See `test_estimate_labeled_estimated`
and `test_estimate_monotonic_with_text`.

## Evidence

- `ContextAccounting.evaluate` unit-covered in `test_memory_trigger.py`.
- `ContextUsage.total()` sums all components.
