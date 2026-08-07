# CAPT Memory Trigger Test Matrix (M1-memory, ADR-DT-M1-MEM-001)

All tests under `tests/capt_runtime/`. Counts: 43 (trigger) + 10 (hermes) + 5
(desktop) + 16 (adversarial) = 74 memory tests; full `tests/capt_runtime` = 251.

## Configuration

- 32k accepted — `test_32k_accepted`
- 64k accepted — `test_64k_accepted`
- 96k accepted — `test_96k_accepted`
- 128k accepted — `test_128k_accepted`
- further 32k step accepted — `test_further_32k_step_accepted`
- zero rejected — `test_zero_rejected`
- negative rejected — `test_negative_rejected`
- 48k rejected — `test_48k_rejected` (raw token threshold not exact multiple)
- non-integer steps rejected — `test_non_integer_rejected`
- above safe limit rejected — `test_above_safe_limit_rejected`
- policy narrowing accepted — `test_policy_narrowing_accepted`
- driver widening rejected — `test_driver_widening_rejected`

## Trigger behavior

- below trigger: no retrieval — `test_below_trigger_no_retrieval`
- exactly at trigger: retrieval fires once — `test_exactly_at_trigger_retrieval_fires_once`
- crossing multiple steps — `test_crossing_multiple_steps_correct_state`
- repeated unchanged: no duplicate — `test_repeated_unchanged_no_duplicate_trigger`
- compression fires — `test_compression_trigger_fires`
- checkpoint fires — `test_checkpoint_trigger_fires`
- consolidation candidate — `test_consolidation_candidate_generated`
- hard-stop suspends — `test_hard_stop_suspends`

## Memory

- mandatory query emitted — `test_mandatory_query_emitted`
- records attributable — `test_records_attributable`
- excluded records visible — `test_excluded_records_visible`
- consent-restricted excluded — `test_consent_restricted_record_excluded`
- stale labeled — `test_stale_record_labeled`
- conflict preserved — `test_conflict_preserved`
- deduplicated with provenance — `test_duplicate_records_deduplicated`
- unverified not promoted — `test_unverified_output_not_promoted`
- promotion requires evidence — `test_promotion_requires_evidence`

## ContextPack

- deterministic rebuild — `test_deterministic_rebuild`
- digest changes on input change — `test_digest_changes_when_inputs_change`
- digest stable on no change — `test_digest_stable_when_inputs_do_not_change`
- selected/excluded preserved — `test_selected_excluded_preserved`
- token budget enforced — `test_token_budget_enforced`
- driver receives only authorized slice — `test_prompt_contains_only_contextpack_slice_reference` (hermes)

## Harness

- dispatch blocked without ContextPack — `test_dispatch_blocked_without_contextpack`
- dispatch blocked with stale ContextPack — `test_dispatch_blocked_with_stale_contextpack`
- dispatch blocked when memory inactive — `test_dispatch_blocked_when_memory_inactive`
- resume triggers reevaluation — engine state per mission
- verification uses recorded ContextPack — pack digest linked to gate
- checkpoint/replay preserves trigger state — `test_reconnect_reconstructs_policy`

## Hermes

- real driver dispatch 32k — `test_real_hermes_dispatch_with_trigger_policy[1]`
- real driver dispatch 64k — `[2]`
- real driver dispatch 96k — `[3]`
- real driver dispatch 128k — `[4]`
- driver cannot alter policy — `test_hermes_cannot_alter_policy`
- hidden Hermes context disclosed/rejected — `test_hidden_hermes_context_labeled_external`
- CAPT/Hermes digest linkage — `test_real_hermes_dispatch_with_trigger_policy`
- removal of Hermes does not break trigger — `test_removal_of_hermes_does_not_break_trigger_logic`

## Desktop

- operator changes trigger by one 32k step — `test_operator_changes_trigger_by_one_32k_step`
- invalid value rejected visibly — `test_invalid_value_rejected`
- policy denial displayed — `test_policy_denial_displayed`
- reconnect preserves effective policy — `test_reconnect_preserves_effective_policy`
- UI cannot bypass runtime validation — `test_ui_cannot_bypass_runtime_validation`
