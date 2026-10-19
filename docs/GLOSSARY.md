# CAPT Core glossary

> These definitions describe the design and documented source interfaces at [`0d8e46d`](https://github.com/knowurknottty/CAPT_core/tree/0d8e46d095243e80febd4e30f5ae52c9202316d9). Precise schema fields are defined by source/contracts, not by this glossary.

| Term | Meaning | Where to go deeper |
|---|---|---|
| **Admission** | The governed act of accepting an operation, observation, or evidence into the authoritative runtime record. Not a synonym for external effect success. | [Governance](GOVERNANCE.md) |
| **Agent / model** | The replaceable inference component that can propose plans, text, or tool uses. Its output is not an authority source. | [Mental model](MENTAL_MODEL.md) |
| **Approval / HumanApproval** | A scoped human authorization evaluated at the runtime boundary. Approval does not mean work was executed or verified. | [Governance](GOVERNANCE.md) |
| **Artifact candidate** | Data or a file returned by a model/tool pending appropriate inspection and promotion. | [Proof engine](PROOF_ENGINE.md) |
| **Capability** | A bounded permission or available operation; capability existence is not an unrestricted license to act. | [Capability registry](CAPABILITY_REGISTRY.md) |
| **Checkpoint** | A recorded recovery boundary for runtime state. Not by itself proof of a complete workload replay. | [User guide](USER_GUIDE.md) |
| **ClaimGuard** | A claim-control boundary differentiating observed evidence from an authorized statement or completed outcome. | [ClaimGuard](CLAIMGUARD.md) |
| **Cohort** | A governed arrangement of model perspectives/participants; consensus is not verification. | [Architecture](ARCHITECTURE.md) |
| **ContextPack** | Information assembled for a model invocation under context and authority policy; distinct from all durable state CAPT retains. | [Architecture](ARCHITECTURE.md) |
| **Driver / DriverHost** | Bounded execution mechanism that attempts authorized work. A completed driver run is not automatically a completed task. | [Runtime source](../capt_runtime/driver_host.py) |
| **EventStore** | CAPT's durable event authority, not the transient model transcript. | [Store source](../capt_runtime/store.py) |
| **Evidence** | Recorded observations, receipts, or artifacts that can support later adjudication; not automatically verified truth. | [Release evidence](RELEASE_EVIDENCE.md) |
| **Idempotency key** | Identity used to recognize or reject duplicate operations according to a particular command contract; not a guarantee over every third-party side effect. | [CLI](CLI.md) |
| **Lease** | Bounded, revocable authorization associated with a capability/operation. | [Governance](GOVERNANCE.md) |
| **MemoryEngine (Solo)** | Separate local memory implementation exposed by `capt memory`; it is not automatically the authoritative runtime memory ledger. | [Memory source](../capt_solo/memory/engine.py) |
| **Mission / Task** | Governed work entities with distinct lifecycles and completion rules. | [User guide](USER_GUIDE.md) |
| **Model Council** | A multi-perspective analysis mechanism; agreement among participants does not manufacture a verifier receipt. | [Current state](CURRENT_STATE.md) |
| **Operator projection / UI** | A view or control surface over runtime state, not an alternate authority plane. | [TUI](TUI.md) |
| **Provider** | An adapter or external/local model execution endpoint; being configured or healthy is not proof of a successful inference. | [Providers](PROVIDERS.md) |
| **Provenance** | Traceable origin, identities, digests and authorship/evidence lineage; preserve the project's historical authorship. | [Agent policy](../AGENTS.md) |
| **Reconciliation** | Determining what happened after an uncertain effect or interrupted operation before considering another dispatch. | [Technical manual](TECHNICAL_MANUAL.md) |
| **Release-proven** | Evidence that a specific built and distributed artifact satisfies its applicable release requirements; stronger than source-present or test-pass. | [Release evidence](RELEASE_EVIDENCE.md) |
| **RuntimeService** | Authoritative runtime command and query boundary over state and governance. | [Service source](../capt_runtime/services.py) |
| **ToolBroker / ToolExecution** | Governed tool dispatch and its durable execution/reconciliation lifecycle; neither implies unrestricted shell/file access. | [Tool broker source](../capt_runtime/tool_broker.py) |
| **Verification** | Separate evaluation of admitted evidence against an explicit claim/requirement. A green fixture verifies only its tested scope. | [Validation](VALIDATION.md) |

## Two distinctions worth memorizing

**Solo memory vs governed runtime memory:** `capt memory store` writes standalone local Solo memory (normally `~/.capt-solo`), not automatically the RuntimeService/EventStore or a model's context.

**Source vs proof:** the order is **source present → tested → integrated → installed → live external dependency verified → release proven**. No stage is implied merely because an earlier stage exists.

[Documentation index](README.md) · [Explained simply](EXPLAINED_SIMPLY.md) · [Technical manual](TECHNICAL_MANUAL.md)
