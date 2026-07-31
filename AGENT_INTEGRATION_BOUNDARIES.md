# AGENT_INTEGRATION_BOUNDARIES.md — GOVERNED_AGENT_BOOT_PROVEN

Defines the exact ownership boundary between this repo (capt-solo) and the
external Hermes harness, and where CAPT may and may not reach.

## A. This repo owns (do not let Hermes reach inside)
- CAPTRuntime composition root (`capt_solo.runtime.CAPTRuntime`) — single
  construction site; never instantiate parallel MemoryEngine/CTp/KHSB/
  ClaimGuard/ContextPack/MemoryUseGate.
- Memory (engine, episodic, semantic, autobiographical, engram, hmc).
- CTP transactions, KHSB bus, ClaimGuard, ContextPack, MemoryUseGate.
- Lifecycle: sessions, procedures, prospective memory, checkpoint store.
- Foundry: ProofEngine, CapabilityRegistry, SkillFoundry, ValidationHarness,
  KnowledgeBubbleRuntime.
- ModelProvider abstraction (`capt_solo.model_task` / `pulse`) — the ONE
  canonical model-execution boundary; LM Studio adapter is in scope.

## B. Hermes harness owns (do not modify from this repo)
- Outer turn loop, model call dispatch, retry/continuation.
- System-prompt construction (byte-stable per conversation; CAPT must NOT
  rebuild it mid-turn).
- Transcript accumulation + compaction (`context_compressor`).
- Tool registry + approval flow + provider routing internals.
- Plugin loader (`hermes_cli/plugins.py`, `middleware.py`).

## C. Shared seam (the integration surface)
- Hermes `PluginContext`: `register_tool`, `register_hook`, `register_middleware`.
- CAPT governance registers hooks/middleware that call the canonical CAPTRuntime.
- Data flow:
  - INBOUND (Hermes → CAPT): `pre_llm_call` kwargs (messages, model, session) →
    CAPT builds ContextPack + runs MemoryUseGate → returns injected context.
  - OUTBOUND (CAPT → Hermes): ContextPack text via the `pre_llm_call` context
    arg; KHSB/checkpoint persisted to `~/.capt-solo`; tool results captured via
    `transform_tool_result`.
- Credential boundary: `LM_STUDIO_API_KEY` read only from process env by the
  provider; never printed, hashed, or persisted. Hermes `.env` is out of scope.

## D. Forbidden
- Editing Hermes core files from this repo (AGENTS.md: "plugins that touch core
  files" are rejected).
- Rebuilding the system prompt mid-conversation (breaks prompt cache).
- Parallel CAPT subsystem instances.
- Any credential exposure.

## E. Contract gap to close (next milestone)
- Repo plugin: legacy `plugin.json`/`get_plugin()` → current
  `plugin.yaml`/`register(ctx)`. Reference: `~/.hermes/plugins/biocapt/plugin.yaml`.
