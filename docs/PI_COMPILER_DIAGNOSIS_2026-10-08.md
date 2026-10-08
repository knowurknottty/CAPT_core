# Prompt Intelligence compiler repair — 2026-10-08

## Observed problem

Screenshot of native CAPT Prompt Intelligence: `COMPILER UNAVAILABLE`,
`r0`, zero executed stages, original/upgrade digest identical, with OMNI/META
route placeholders. This means the **route was selected but no complete
model-backed upgrade was retained**. PI "AUTO"/manual-stage selection does not
guarantee that a compiler is reachable or has produced a structured response.

## Verified configuration and no-cost probes

- User's persisted local `~/.capt/ui/prompt-compiler.json` declares first
  `openrouter / z-ai/glm-5.3-flash` with remote compilation explicitly enabled;
  second `mtplx / Youssofal/Qwen3.8-27B-MTPLX-Optimized-Speed`.
- Both selections construct a compiler under the existing private runtime
  credentials. No secret values were printed or recorded.
- Local MTPLX endpoint `127.0.0.1:18085` rejects connections.
- A read-only GET of OpenRouter's public model catalog showed the configured
  GLM model exists and advertises `response_format` and
  `structured_outputs`. No model inference was issued.
- Prior code swallowed transport/HTTP/structured-output failures, returned
  `compiler_unavailable`, and discarded the attempted provider failure
  codes, producing an indistinguishable deterministic proposal.
- The strict JSON schema omitted `requestedCapabilities` from its
  `required` list. OpenAI-compatible strict output schema requires every
  declared property to be required. The fix also removes provider-incompatible
  `maxItems` on the wire, keeping the 32-item bound in local validation.

**Open:** A real paid provider stage has not been dispatched or verified.
Do not claim the OpenRouter HTTP error, billing behavior, or actual inference
result was observed. The schema issue is source-proven; exact remote failure
cause remains unproven until an authorized stage runs.

## Repair

- Makes wire schema portable for strict JSON-schema structured outputs.
- Fallback keeps literal prompt and exposes **safe failure categories**,
  e.g. `openrouter: HTTP_400`, `mtplx: TRANSPORT_UNAVAILABLE`, or
  `Compiler credential unavailable`; never serializes provider response
  text, URL, echoed prompt, bearer key or stack trace.
- The explanation is persisted as a PromptProposal rationale in EventStore
  and survives replay, rather than being hidden in a volatile log.
- Native UI explicitly distinguishes **no retained enhancement** from a
  successful PI result and explains that an attempted provider request may
  have incurred usage before failure.
- Does not change provider priority, introduce unauthorized fallback models,
  approve execution, or automatically retry billable calls.

## Recovery in the installed app

1. Examine the new PromptProposal warning and compiler diagnostic.
2. Verify OpenRouter is enabled, its credential is valid, and remote Prompt
   Compilation authorization matches the policy you intend to use.
3. If you prefer local inference, start the **matching** local server/model
   before retrying. Having LM Studio open is not proof that the configured
   MTPLX server on port 18085 is running.
4. For an already persisted `compiler_unavailable` proposal, **Cancel
   Proposal** and submit the objective again. The previous result will not
   retroactively upgrade itself. "Use Original" remains an explicitly
   selectable, separate HumanApproval basis.
5. Run one intentionally bounded test prompt before attempting costly
   multi-stage software-development compilation. Inspect the stage-run
   counter, differing hashes, acceptance criteria and provider/model.

## Test and release boundaries

Mocked multi-stage compilation must produce a distinct upgrade,
`ready_for_approval`, stage receipts and verification criteria. Simulated
HTTP failures must produce non-sensitive actionable status; errors must
never be silent, never result in an automatic original-vs-upgrade selection,
and must not mutate authority or claim that a model stage completed.
A full regression suite and signed UI release must match the exact committed
source before marking the fix installed.
