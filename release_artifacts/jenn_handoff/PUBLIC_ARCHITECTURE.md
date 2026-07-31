# CAPT Core v0.5 Public Architecture

- **Status:** Current public conceptual architecture
- **Decision:** ADR-0008
- **Internal catalogue:** `architecture/registry.yaml`

CAPT is the local-first verification substrate beneath AI systems. Its job is to
make claims, context, tool results, and actions inspectable, reproducible,
invalidatable, and recoverable.

## Layered Map

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Adapters: CLI · CI · IDE · MCP · A2A · Hermes · model/tool providers │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│ Services: Memory · Workspace · Knowledge · Foundry · KHSB            │
│           Lifecycle · Procedures · domain engines                    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│ CAPT Verification Kernel                                             │
│ Identity & Scope │ Evidence │ Verification │ Context │ Transactions  │
│ Governance                                                          │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│ Storage and Crypto Ports                                             │
│ record store · ledger · canonical codec · hashing · optional signing │
│ clock · policy store                                                 │
└──────────────────────────────────────────────────────────────────────┘
```

## Six Pillars

### Identity & Scope

Identifies what is being evaluated and the boundary in which a result applies.
Current implementations include project identity, workspace binding, VSI
repository state, actor fields, namespaces, and verification scope.

### Evidence

Records what was observed, where it came from, how confident the observation is,
and whether it remains applicable. The canonical record for new public evidence
workflows is `capt_solo.evidence.EvidenceRecord`. Specialized Foundry,
Verification, Knowledge, and Continuity records remain compatible in v0.5.

### Verification

Runs checks and evaluates their applicability to a concrete state. Verified
State Identity binds results to Git state, dependency state, runtime identity,
environment, command, and scope. Evidence invalidation explains why a prior
result no longer applies.

### Context

Projects relevant evidence, memory, assumptions, invariants, and receipts into a
deterministic exchange artifact. ContextPack v1 uses canonical JSON, digests,
explicit assumptions, protected facts, AntiToken validation, and derived
handoffs. Context is a projection; it is not its own source of truth.

### Transactions

Records consequential operations with intent, idempotency, lifecycle, receipts,
and recovery. CTP provides the current local append-only transaction journal.

### Governance

Applies consent, capabilities, proof requirements, invalidation, policy,
quarantine, audit, and release gates. Governance prevents optional or
unverified behavior from silently becoming trusted.

## Existing Implementation Mapping

| Public concept | Current implementation |
|---|---|
| subject and state identity | VSI, project context, memory identity, content digests |
| evidence | Evidence Engine, provider adapters, Foundry proof evidence |
| checks and evaluation | VerificationEngine, validation harnesses, proof requirements |
| deterministic context | ContextPack v1, existing context builder, AntiToken |
| operation receipts | CTP Receipt, continuity receipt chains, governance receipts |
| applicability change | VSI diff, evidence invalidation, capability degradation |
| local stores | SQLite, JSON, JSONL, content-addressed hashes |
| adapters | installed CLI, Hermes plugin, workspace and research adapters |

## Public Versus Internal Architecture

The six pillars are the public mental model. They describe the minimum concepts
an adopter must understand.

The L0-L11 constitutional layer model assigns permanent ownership and dependency
direction. `architecture/registry.yaml` inventories current, planned, external,
and research subsystems. Neither is removed.

Experimental engines and biological/cognitive modules may demonstrate CAPT
principles. They do not become verification-kernel dependencies merely because
they ship in the same distribution.

## Protocol Boundaries

MCP and A2A remain external protocols. A future adapter may translate CAPT
evidence, ContextPacks, or attestations into protocol resources or artifacts,
but transport objects do not become canonical CAPT records.

CRP is deferred. v0.5 only preserves versioning, digests, provenance, authority,
causal links, and namespaced extension points that reduce future migration cost.

## Invariants

1. Consequential assertions remain inspectable.
2. Verification is bound to state and policy.
3. Unknown, partial, stale, conflicted, and invalidated are explicit.
4. Context references authority; it does not manufacture it.
5. Consequential actions produce receipts.
6. Users retain local ownership, export, deletion, and exit.
7. Optional capabilities fail independently.
8. Schemas and compatibility rules are versioned.
9. Claims about CAPT require reproducible evidence.
10. Current authority documents describe one present tense.
