# CAPT Memory Hermes Conformance (M1-memory, ADR-DT-M1-MEM-001)

## Scope

Proves the genuine Hermes ExecutionDriver (`capt_runtime/drivers/hermes.py`,
real `/Users/knowurknot/.local/bin/hermes` v0.19.1) receives a trigger-governed
ContextPack and cannot bypass policy. The test exercises the **actual
CAPT-to-Hermes dispatch path** — the driver boundary is not faked.

## Method

`tests/capt_runtime/test_memory_trigger_hermes.py` runs real Hermes dispatches
at 32k / 64k / 96k / 128k (`parametrize("steps", [1,2,3,4])`). Each run:
1. CAPT fires the mandatory retrieval trigger (`require_retrieval_before_planning`)
   and builds the ContextPack.
2. CAPT builds the work order with `contextPackRef` (digest + selected count)
   and `memoryPolicyRef` (policy version + digest + steps).
3. `HermesDriver.submit(work_order)` launches the real Hermes process with a
   trivial bounded prompt (no wasteful token generation).
4. The prompt Hermes receives embeds ONLY the ContextPack slice reference —
   raw memory content is never forwarded (`build_prompt` in `hermes.py`).

## Proofs

1. **CAPT activates memory policy before Hermes invocation** — the pack exists
   before `submit` is called.
2. **Hermes receives only the authorized ContextPack slice** — `build_prompt`
   embeds `contextPackDigest` + `selectedRecordCount`; raw content absent
   (`test_prompt_contains_only_contextpack_slice_reference`).
3. **Hermes cannot request raw memory access** — the driver surface has no
   memory API; the slice is the only memory reference.
4. **Hermes cannot increase the trigger threshold** — `test_hermes_cannot_alter_policy`
   asserts the driver exposes no `update_policy` / `widen_threshold` / etc.
5. **Hermes cannot suppress a trigger** — `test_hermes_cannot_suppress_trigger`.
6. **Hermes cannot replace CAPT-selected memory** — the prompt carries only the
   CAPT slice reference.
7. **Hermes session context inventoried/classified** — observations returned
   with `trust=untrusted`, `observedBy=hermes` (`test_hidden_hermes_context_labeled_external`).
8. **Hermes-native memory labeled external-driver** — observations are
   `trust=untrusted`.
9. **External-driver context cannot override CAPT policy** — `memoryPolicyRef`
   unchanged by the run.
10. **ContextPack and Hermes prompt/request digests linked** — the work order's
    `contextPackRef.contextPackDigest` equals the pack digest; the prompt embeds it.

## Swap proof

`test_removal_of_hermes_does_not_break_trigger_logic` confirms the same
`MemoryTriggerEngine` logic works with the reference driver path when Hermes is
removed — equivalent CAPT semantics, not identical model output.

## Evidence

Real Hermes runs: `hermes -z <prompt> -t terminal --safe-mode --pass-session-id`
completes in ~5s for a trivial prompt. 10 Hermes conformance tests pass
(including 4 real multi-setting dispatches).
