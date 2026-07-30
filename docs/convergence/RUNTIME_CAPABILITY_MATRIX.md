# RUNTIME_CAPABILITY_MATRIX — capability-by-capability runtime audit

Generated: 2026-07-30. Question: is provider-neutral runtime already
functionally achieved? We audit each capability against integration HEAD
`716ecc9`. Classification: implemented / partial / Hermes-independent /
Hermes-coupled / absent.

Key context from this pass:
- `capt_solo/pulse.py` is the ONLY model-runtime touchpoint; disabled by default,
  lazy `urllib` import inside `complete()`/`chat()`; zero `import hermes` in core.
- `verify_runtime.py` is ABSENT at HEAD (exists only on public main as part of
  the security-hygiene delta) — so the "runtime contract" doc-07 command
  `python3 verify_runtime.py` cannot run on the integration candidate. This is a
  documentation-truth gap (PUBLIC_CLAIM_LEDGER C / Package C recovery).
- `research/adapter.py` `ResearchAdapterRegistry` is the only registry pattern
  in tree; it covers research-task execution, NOT model generation.

## Capability matrix

| # | Capability | Status | Evidence | Notes |
|---|---|---|---|---|
| 1 | Runtime abstraction (contract) | ❌ absent | no `capt_solo/adapters/`; `pulse.PulseGateway` is single-impl, not behind a contract | research adapter is a different contract (task exec) |
| 2 | Request construction | 🟡 partial | `pulse.complete(prompt, max_tokens)` / `chat(messages)` — minimal, no structured builder | Hermes-independent (pure local call) |
| 3 | Provider selection | ❌ absent | no provider registry; pulse has no provider concept | — |
| 4 | Model selection | ❌ absent | pulse has no model param | — |
| 5 | Invocation | 🟡 partial | `PulseGateway.complete/chat` invoke one gateway | Hermes-independent |
| 6 | Streaming | ❌ absent | not in pulse | — |
| 7 | Structured output | ❌ absent | none | — |
| 8 | Tool calling | ❌ absent (at runtime layer) | tool governance exists in foundry, but no runtime adapter tool-call contract | — |
| 9 | Multimodal | ❌ absent | none | — |
| 10 | Cancellation | ❌ absent | pulse has no timeout/cancel (only `timeout_s` config field, unused in complete) | — |
| 11 | Retry | ❌ absent | none | — |
| 12 | Telemetry | ❌ absent | none | — |
| 13 | Provenance | 🟡 partial | records carry `provenance` field (default "hermes"/"local"); pulse calls do NOT yet stamp adapter provenance on the generated record | Hermes-independent at record level |
| 14 | Adapter registration | 🔁 other-abstraction | `ResearchAdapterRegistry.register/get/health` — research scope only | reusable pattern, not model-runtime |
| 15 | Adapter discovery | ❌ absent | none | — |
| 16 | Fallback | 🔁 other-abstraction | `LocalFallbackAdapter` in research; pulse has no fallback | reusable pattern |
| 17 | Local execution | ✅ Hermes-independent | pulse disabled-by-default; core runs with NO runtime configured (proven socket-deny import test) | this is the critical neutrality fact |
| 18 | Remote execution | 🟡 partial | pulse `complete()` does `urllib.request` to a configured endpoint when enabled | opt-in, lazy |
| 19 | Offline operation | ✅ Hermes-independent | with pulse disabled, entire core operates offline (memory/CTP/evidence/verification/knowledge/contextpack/foundry) | proven today |

## Interpretation
- **Architecture-level neutrality: ACHIEVED and EVIDENCED** (capabilities 17, 18,
  19 + zero hermes imports). The system does not require any provider to function.
- **Operational provider-neutrality (the doc 15 §E contract): NOT achieved.**
  There is exactly one runtime path (pulse), no adapter contract, no provider/
  model selection, no second proven path. The required "two distinct paths"
  proof cannot be constructed today.
- The research adapter registry (14/16) is a DESIGN PRECEDENT proving the pattern
  works in-tree, but it is not the model-runtime contract.

## Conclusion for Q3
Provider-neutral runtime is **functionally achieved at the architecture level
(core imports/operates without Hermes, offline, local-first) but NOT at the
operational contract level** (no adapter abstraction, no provider/model
selection, no two-path proof). This matches the prior report: deferral to
v0.5.1 is consolidation of an operational contract, not recovery of missing
core function. Current public claims ("model-agnostic architecture; no harness
dependency") are TRUE and evidenced; they do not assert an operational adapter
layer.
