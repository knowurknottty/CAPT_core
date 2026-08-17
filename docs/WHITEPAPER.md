# CAPT Core

## Local-First, Auditable, Model-Agnostic Cognitive Infrastructure

**Author:** Kirk Brown, Inversion Labs  
**Repository:** `knowurknottty/CAPT_core`  
**Status:** Public architecture whitepaper; implementation state evolves independently of the numbered `0.5.0` package release  
**Version:** 2.1

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

The CAPT Solo Memory Engine stores durable local knowledge. The Runtime Memory Governor and ContextPack form a separate bounded working-context layer. Durable memory is not dumped indiscriminately into a model merely because it exists.

## Governance and execution

RuntimeService owns governed state transitions. DriverHost executes bounded work under runtime authority. External output remains untrusted until admitted through evidence/verification boundaries.

Active lifecycle hardening emphasizes conservative recovery: when CAPT cannot prove whether external dispatch occurred, it should suspend/reconcile rather than silently execute the operation again.

## Operator productization

Merged `main` is substantially newer than the original v0.5 user experience. It includes a normal CLI on-ramp, shared operator layer, provider/model foundations, CaveCAPT presentation verbosity, a Textual TUI MVP, a Tk desktop operator MVP, and a SwiftUI client-contract library.

The active TUI/provider integration adds inspectable prompt enhancement, response modes, requested context budgets, human review/approval, cognitive provenance, and bounded provider execution transport. Open-PR implementation is not described as a numbered release until it merges and passes the matching acceptance gates.

## Providers

Provider registration, discovery, model listing, execution, and release proof are separate capability levels. Active ProviderDriver work supports Ollama native generation and OpenAI-compatible chat-completions transport; controlled protocol tests do not substitute for exact-head live-provider installed-runtime proof.

## Hermes

Hermes remains a compatibility/execution client. CAPT does not transfer runtime authority to Hermes.

Historical v0.5 Hermes evidence and active lifecycle hardening remain distinct evidence classes. A later operator-supplied LOCAL-002 record referenced `evidence/hermes-local-002-r6` / `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04` and claimed `HERMES_LOCAL_002_COMPLETE` with 98/0/0 focused and 174/0/2 broader results, but Terra could not retrieve the branch, commit, or named report from the current GitHub remote/API. Those LOCAL-002 statements are therefore **currently unverified metadata**. Destructive external-provider/tool-kill rollback remains independently unproven.

## Multi-perspective cognition

Cohorts coordinate bounded contributions, quorum, dissent, and cognitive debt over CAPT authority. The current Cohort slice does not yet claim durable cross-process persistence/reconstruction or evidence admission.

## Security

Local-first reduces mandatory cloud dependence but is not itself a security guarantee. Current limitations include incomplete CAPT-managed encryption at rest, lack of multi-user authorization, unsigned independent audit roots, incomplete production IPC/resource-ceiling hardening, and incomplete adversarial prompt/context/provider assurance.

The active SecurityGate work is intentionally fail-closed and should remain BLOCKED until each applicable control has exact-head evidence.

## Evaluation principle

CAPT should be judged by system properties: authority integrity, memory provenance, context boundaries, idempotency/recovery truthfulness, evidence sufficiency, verification correctness, claim discipline, and restart/provider continuity—not by the eloquence of one model response.

## Current implementation status

The repository has four relevant truth classes:

1. numbered package release (`0.5.0`);
2. newer merged `main` productization capabilities;
3. active stacked integration work (#44/#46/#47/#48/#49);
4. exact evidence/release proofs scoped to particular source identities.

See [`CURRENT_STATE.md`](CURRENT_STATE.md) for the current detailed state.

## Conclusion

The model generates and reasons.

CAPT remembers, governs, records, verifies, and recovers.

Humans and explicit runtime policy remain authoritative.

> **A convincing answer is not the same thing as a verified system state.**