# CAPT Core Architecture

CAPT Core is local-first governed cognitive infrastructure around replaceable inference models and bounded external tools. Durable responsibility stays outside any transient model session.

## Authority topology

```text
Human / application / compatibility client
              |
   CLI / TUI / native macOS / MCP
              |
      shared Operator/control layer
              |
      authenticated local IPC
              v
        RuntimeService
              |
   +----------+-----------+----------------+
   |                      |                |
EventStore            Governance       Memory/context
ordered authority     grants/leases    durable memory
history               approvals        + ContextPack
   |                      |                |
   +---------- governed execution ----------+
              |
       +------+------+
       |             |
   DriverHost     ToolBroker
       |             |
 model drivers   tool adapters
       |             |
replaceable AI   bounded effects
```

This diagram describes governed runtime operations. Standalone `capt memory` commands call Solo MemoryEngine directly; they do not establish EventStore admission or model continuation.

No presentation surface, MCP client, external model, Hermes client, Cohort coordinator, discovery scanner, authored-skill pack, prompt enhancer, provider manager, tool adapter, or security checker becomes a parallel runtime.

## Merged convergence architecture

PR #117 reconciled the formerly stacked runtime, provider, native, security, authored-skill, and UPG-001→019 lines on `main`. Later merges extend the same authority spine rather than creating new ones:

- **PR #126** adds durable ToolExecution state and ToolBroker with local/SSH/Docker terminal plus file/code adapters;
- **PR #129** adds managed-local Agent Skills import/verify, contextual selection, exact approval binding, anti-drift enforcement, and native skill visibility;
- **PR #146** merges UPG-020–024: reciprocal-review scoring, admitted-candidate symbol indexing, structural-hash/chunk-stability probes, and the cognitive-debt projection/`capt-debt` surface. Empirical effectiveness and provider-cache reuse remain separate proof obligations;
- **PR #148** merges governed Settings/Skills/model/filesystem/shell/provider controls and the native/TUI golden authority tranche;
- **`42a6cd2`** merges the semantic operator-control API; **PR #153** merges Model Council alpha; **PR #155** adds read projections and further authority hardening.

Key integrated properties:

- exact historical replay reconstructs the ledger prefix rather than seeding old state with present snapshots;
- governed replay forks create new history without reactivating historical approvals/capabilities;
- Cohorts own durable EventStore state, evidence admission, epoch/round semantics, and governed steering;
- artifact promotion has its own authoritative transaction rather than filesystem side effects pretending to be verification;
- capability leases remain bounded/revocable authority;
- authored-skill bytes are verified and bound into the exact model-visible approval identity before one-use execution;
- managed-local skill material is revalidated at execution so approved context cannot silently drift;
- ToolBroker records prepared/admitted/dispatch/effect/settlement/reconciliation facts separately from adapter intent;
- provider/model changes are session-isolated in the native client;
- MCP and native macOS remain compatibility/control surfaces over the same RuntimeService/EventStore authority.

## Durable layers

### Operator control and read projections

`desktop/operator_control.py` persists revisioned configuration/session coordination. The semantic API binds provider, model, canonical workspace root, prompt-intelligence mode, and proposal/approval cursors; stale revisions are rejected. This coordination state is non-authoritative: execution, evidence, verification, claims, and completion still come from RuntimeService/EventStore.

Runtime queries expose `approvals`, `missions`, `tasks`, and `checkpoints`, including derived approval staleness and checkpoint integrity reporting. A read projection does not grant authority or mutate an approval into a new state.

### EventStore

Authoritative ordered runtime history, replay, sequence identity, stream versions, and integrity chain.

### CTP

Operational transaction/recovery journal; it does not replace EventStore authority.

### Durable memory / ContextPack

Runtime-owned `capt_runtime.memory.store.MemoryStore` and governed bounded model context are separate layers; the standalone `capt_solo.memory.engine.MemoryEngine` is a distinct store and is not automatically bridged into them. Context selection/provenance is frozen at the approval/execution boundary where required. The live ContextPack producer is `MemoryTriggerEngine._fire_retrieval`; `context_pipeline.py` and `context_merkle.py` are explicitly unshipped, unwired design/experiment modules.

### KHSB

In-process coordination and compatibility substrate. It remains non-authoritative; cross-process/distributed authority is not inferred from it.

### Cohorts

Merged `main` includes durable Cohort persistence/reconstruction, evidence admission, governed steering, epoch handling, and Chamber projection. Cohort majority/quorum is not verification and cannot bypass RuntimeService authority.

### Model Council alpha

Merged alpha source includes topology/launch contracts, deterministic claim analysis, durable Council state, and Council Chamber projection. Declared vessel counts are not measured provider concurrency or evidence of model quality; Council consensus cannot manufacture verification. This alpha does not establish a live Council provider scheduler, native Council UI, or release proof.

## Governed model execution

RuntimeService admits commands under explicit authority. DriverHost executes bounded model work. A provider/model result yields observations/artifact candidates and leaves verification, ClaimGuard, task completion, and mission completion distinct.

Prompt proposals are durable, revisioned review material bound into human approval. The merged compiler supports OMNI/META and bounded FORGE repository analysis/SIGMA reconciliation. AUTO routing recognizes actionable research prompts; routing and compiler output do not authorize execution.

## Governed tool execution

ToolBroker is the authority-preserving execution broker for registered tools. The initial terminal backends are `local | ssh | docker`; bounded file/code adapters are also registered by the runtime composition.

A ToolExecution state machine records durable lifecycle and reconciliation facts. Consequential calls consume governed capability/lease authority. Adapter readiness is not effect proof, and a requested cancellation is not evidence that an external effect was physically undone.

If CAPT cannot prove whether consequential dispatch/effect occurred, it does not blindly redispatch. The state becomes reconciliation-required/indeterminate as appropriate.

## Authored-skill context

Authored skills are model context, not runtime authority.

- `pinned_external` packs bind immutable external repository/release/commit/tree/content identities;
- `managed_local` packs are imported into CAPT state, digest-bound, selected deterministically, and reverified before dispatch.

Explicit pinned selection outranks contextual managed-local selection. Skill context cannot grant tools, permissions, approvals, provider secrets, verification, or policy overrides.

## Provider layer

The convergence provider spine includes Ollama plus local/authenticated OpenAI-compatible execution, endpoint provenance, resource ceilings, bounded prewarm, and coherent global/session provider selection. The generic direct native MLX placeholder remains unregistered; configured MLX/MTPLX services use the OpenAI-compatible adapter, not a direct native `mlx_lm` adapter.

## Native macOS layer

`CAPTNativeMac` is a real executable target, not merely a Swift contract package. It remains a thin RuntimeService client with typed projections, governed approvals, selected-skill visibility, encrypted session-cache persistence, and session-isolated async configuration updates. Governed Settings and Skills controls bind execution scope and selected context into approval. Native chat renders model-answer text separately from the expandable execution receipt; neither rendering establishes verification or completion.

## Security layer

SecurityGate/Security Closure Cockpit is a fail-closed projection over the 47-control catalog. It does not self-authorize release and does not convert general test success into control evidence.

Exact-source authorization has been demonstrated for specific historical SHAs, including `2199c036…` and the ToolBroker PR #126 head `b21ed6e…`. Those receipts do not automatically transfer to later commits. See [`SECURITY.md`](SECURITY.md) and [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md).

## Truth classes

```text
SOURCE_PRESENT
PACKAGED
OPERATOR_REACHABLE
EXECUTED
EVIDENCE_RECORDED
VERIFIED
CLAIM_ACCEPTED
TASK_COMPLETED
MISSION_COMPLETED
RELEASE_PROVEN
```

They are not interchangeable.

See [`CURRENT_STATE.md`](CURRENT_STATE.md) for the current merged-source / exact-evidence split.
