# Prompt Intelligence compiler token budgets

**Defect:** The compiler TokenCostGovernor was constructed with
max_tokens_per_session=131_072. The same governor is shared across successive
OMNI, META, FORGE and SIGMA stages. Its consumed-token counter is cumulative,
so otherwise-bounded stages could be rejected when their combined usage
exceeded 131,072. This was not evidence that a single model invocation
exceeded the provider context window.

**Repair:** The compiler session budget now totals 1,000,000 estimated tokens
for the whole session. Independently, each compiler request is checked for
98,304 estimated input tokens, preserving 32,768 requested output tokens as a
conservative 131,072-token combined envelope. The estimate uses JSON length/4;
it is a heuristic, NOT tokenization or verified per-model metadata. Actual
provider constraints can be smaller or larger. Any over-limit request fails
before transport, without removing evidence or claiming a larger provider
context window.

**Unchanged:** compiler cost hard ceiling $0.01 per session; request count 32;
remote-compilation consent; no silent replay; separate selected execution model
configuration; raw context and evidence stay intact. No increase to financial
authority is implied by this repair.

**Verification:** regression invokes four compiler stages using a synthetic
input whose combined accounting exceeds 155,153 tokens but whose individual
stages fit the per-request cap. A second regression confirms a single oversized
stage produces COMPILER_STAGE_CONTEXT_LIMIT before invoking its transport.
Provider or model metadata must be verified before extending per-request caps
for larger-context models.
