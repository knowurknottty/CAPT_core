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


## Final acceptance evidence — source 7aa7510

- Tested source commit:
  `7aa7510b063e3ec8c35e8ba3eceef5a58bf8bdd0`.
- Full Python Core gate: **1,975 passed; 70 skipped; 13 deselected**.
  Local evidence: `~/capt-node-workspace/pi-repair-core-full.log`.
- Native Swift gate: **148 passed; 9 skipped; zero failures**.
  Local evidence: `~/capt-node-workspace/pi-repair-swift-test.log`.
- Mocked remote structured-output pipeline: OMNI and META both ran with
  distinct prompt output and acceptance criteria; no paid calls.
- Simulated HTTP 400 and offline local fallback:
  persisted safe failure codes, retained original prompt, and did not
  copy response bodies/secrets into the proposal or ledger replay.
- A genuine pre-upgrade checkpoint was accepted:
  `cp-cmd-455fa6a0bdc94b2a` at EventStore head 23368.
- Resident RuntimeService restarted after confirming zero nonterminal
  DriverRuns. New runtime: **HEALTHY**, distribution **0.5.0**,
  ledger digest unchanged at restart, installed source marker
  `7aa7510b063e3ec8c35e8ba3eceef5a58bf8bdd0`.
- Watchdog re-enabled and CAPT-Bot restarted; Bot health `ok`.
- Signed native CAPT.app copied byte-identically from clean staging;
  installed executable SHA-256:
  `1085922f24d03b8442b18beaeed760af152a09c23c3c27431d4250d33c492955`.
  Native app launched and was activated through TIA. The old failed
  proposal was not visible in the activated chat, so a new live
  `COMPILER UNAVAILABLE` banner was **not** personally witnessed
  in TIA. Swift source/test and signed binary prove the UI logic
  is shipped, not that every historical session displays it.
- Installed compiler factory introspection: `FailoverPromptCompiler`,
  with strict wire-schema required keys matching all declared properties.
- No OpenRouter paid inference call or charge was initiated by this
  repair/verification. **Remote paid model-stage success remains unproven**;
  next operator-initiated PI compilation will be the proper live acceptance
  test, after checking expected spend/authority.

**Disposition:** source/schema/runtime/UI repair shipped and regression
verified; actual remote provider output is not represented as tested.
