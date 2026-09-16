# CAPT Core

## Local-First, Auditable, Model-Agnostic Cognitive Infrastructure

**Author:** Kirk Brown, Inversion Labs
**Repository:** `knowurknottty/CAPT_core`
**Status:** Public architecture whitepaper; implementation state evolves independently of the numbered `0.5.0` package release
**Version:** 2.1
**Source snapshot:** 2026-09-15, `1e85bac5d17cde342a1ae55e6ee3da5fa681ff61`

## Abstract

Most AI systems organize memory, tools, workflow state, and evaluation around a temporary model session. CAPT inverts that dependency: models remain replaceable inference components, while a durable governed runtime owns state, authority, memory, execution history, evidence, verification, context policy, and recovery.

The core thesis is:

> **The model is a component, not the system of record.**

## Architectural problem

Context windows are bounded. Model behavior varies. Providers change. Processes crash. Tool calls can outlive a client request. A system that binds identity, memory, authority, and completion to a probabilistic transcript cannot reliably distinguish fluent output from verified state.

CAPT externalizes those durable responsibilities.

## System responsibilities

CAPT separates:

- persistent memory from transient context;
- EventStore runtime authority from operational transaction journaling;
- capability/lease/approval from model suggestion;
- driver execution from evidence admission;
- evidence from verification;
- verification from claim acceptance;
- task completion from mission completion;
- source/test presence from release proof.

## Runtime architecture

```text
Operator / application
   -> CLI / TUI / desktop / compatibility client
   -> authenticated RuntimeService
      -> EventStore
      -> governance: capability / lease / approval
      -> memory + ContextPack policy
      -> checkpoint / replay / recovery
      -> evidence / verification / ClaimGuard
      -> DriverHost
         -> replaceable models/tools
```

Presentation surfaces do not become alternate runtimes.

## Memory and context

The CAPT Solo Memory Engine stores standalone local knowledge. Runtime-owned memory uses the separate `capt_runtime.memory.store.MemoryStore`; the Runtime Memory Governor and ContextPack form its bounded working-context layer. The `capt memory` commands use Solo MemoryEngine directly, so success there does not establish EventStore admission or model continuation. Durable memory is not dumped indiscriminately into a model merely because it exists.

## Governance and execution

RuntimeService owns governed state transitions. DriverHost executes bounded work under runtime authority. External output remains untrusted until admitted through evidence/verification boundaries.

Merged lifecycle hardening enforces authority gates on mission and driver-run transitions and emphasizes conservative recovery: when CAPT cannot prove whether external dispatch occurred, it should suspend/reconcile rather than silently execute the operation again.

## Operator productization

Merged `main` is substantially newer than the original v0.5 user experience. It includes a normal CLI on-ramp, shared operator layer, provider/model foundations, CaveCAPT presentation verbosity, a Textual TUI MVP, a Tk desktop operator MVP, and a SwiftUI client-contract library plus the `CAPTNativeMac` executable target. Historical native build/test receipts do not establish a build of this HEAD or signed/notarized distribution.

Merged TUI/provider and native work includes inspectable prompt enhancement, response modes, requested context budgets, human review/approval, cognitive provenance, and bounded provider execution transport. PR #148 and the subsequent semantic operator-control merge provide prompt proposals and shared configuration/session coordination; this operator state does not replace EventStore authority. Native change `d33a5e4` separates the model answer from execution-details JSON. Change `1e85bac` routes additional actionable research prompts through prompt intelligence; it does not prove research execution or answer correctness.

PR #146 merged CAPT-UPG-020–024: reciprocal-review and structural-hash/chunk-stability harnesses, a discovery-guided symbol-index probe, and cognitive-debt observability. Their presence does not establish empirical review benefit, context sufficiency, semantic equivalence, or provider-cache gains.

## Providers

Provider registration, discovery, model listing, execution, and release proof are separate capability levels. Merged ProviderDriver source supports Ollama native generation and OpenAI-compatible chat-completions transport; controlled protocol tests do not substitute for exact-head live-provider installed-runtime proof.

## Hermes

Hermes remains a compatibility/execution client. CAPT does not transfer runtime authority to Hermes.

Historical v0.5 Hermes evidence and active lifecycle hardening remain distinct evidence classes. A later operator-supplied LOCAL-002 record referenced `evidence/hermes-local-002-r6` / `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04` and claimed `HERMES_LOCAL_002_COMPLETE` with 98/0/0 focused and 174/0/2 broader results, but the prior audit reported that Terra could not retrieve the branch, commit, or named report from the GitHub remote/API. This review does not establish their current remote availability. Those LOCAL-002 statements are therefore **currently unverified metadata**. Destructive external-provider/tool-kill rollback remains independently unproven.

## Multi-perspective cognition

PR #153 merged Model Council alpha above Cohorts: topology and logical Vessel expansion, digest-bound launch interlocks, deterministic claim/dissent analysis, targeted challenges, governed EventStore plan/analysis persistence, checkpoint/replay support, and a read-only Council Chamber projection. Multiple Vessels in one Cohort do not multiply independent model identities.

The 24,000-Vessel maximum describes logical topology, not measured provider concurrency. Durable Council state does not prove a live end-to-end provider scheduler, paid-provider scale acceptance, or successful mission completion. Consensus and stored evidence references do not create Verification or ClaimGuard acceptance; analysis remains unverified.

## SOMA context-compression primitives

PR #156 merged SOMA M0: canonical coding trajectories, an explicit reducer-result contract, deterministic event-budget reduction, and receipts binding input, retained/removed content, policy, and budget. Local arena, reconstruction, and benchmark helpers measure retained declared importance and critical-event preservation, including duplicate accounting and an undefined ratio when no critical events exist.

This is a local contract slice, not proven live runtime context integration, semantic reconstruction, measured model-quality or token-cost improvement, or external competition readiness. A compression receipt is not a CAPT Verification record.

## Security

Local-first reduces mandatory cloud dependence but is not itself a security guarantee. Merged source includes authenticated runtime IPC and bounded framing, provider resource ceilings, covered authenticated encryption at rest, and adversarial prompt/context/provider regression coverage. PR #155 adds lifecycle authority gates, digest-only envelope-identity refusal auditing, and honest absent-context provenance. Read projections provide observability, not execution or completion authority.

`capt_runtime/context_pipeline.py` and `context_merkle.py` are explicitly UNSHIPPED experiments, not live security/context controls. The live ContextPack producer is `MemoryTriggerEngine._fire_retrieval`.

The threat model still assumes one trusted local OS user and trusted host/runtime dependencies. Covered field encryption is not whole-disk protection; source controls do not prove protection from host compromise, comprehensive multi-user authorization, universal process isolation, exactly-once arbitrary external effects, or model/prompt safety. Signed/notarized/distributed release proof remains separate.

SecurityGate authorization is exact-SHA-bound. Historical passing and failing receipts remain historical; current HEAD has no inherited release authorization, and this paper establishes no current-HEAD Release Security run. See [`SECURITY.md`](SECURITY.md) and [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md).

## Evaluation principle

CAPT should be judged by system properties: authority integrity, memory provenance, context boundaries, idempotency/recovery truthfulness, evidence sufficiency, verification correctness, claim discipline, and restart/provider continuity—not by the eloquence of one model response.

## Current implementation status

The repository has four relevant truth classes:

1. numbered package release (`0.5.0`);
2. newer merged `main` productization capabilities;
3. bounded alpha/probe source and remaining unproven integration or empirical claims;
4. exact evidence/release proofs scoped to particular source identities.

See [`CURRENT_STATE.md`](CURRENT_STATE.md) for the current detailed state.

## Conclusion

The model generates and reasons.

CAPT remembers, governs, records, verifies, and recovers.

Humans and explicit runtime policy remain authoritative.

> **A convincing answer is not the same thing as a verified system state.**