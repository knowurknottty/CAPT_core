# CAPT Core v0.5 — Architecture Evolution and Public Release Review

- **Status:** Architecture decision proposal; not a release approval
- **Reviewed tree:** `ac849a4a2f7d92fd9592c3a6513a88dfd80ca92b`
- **Date:** 2026-07-29
- **Scope:** CAPT Core public architecture, product narrative, APIs, plugins,
  interoperability, developer experience, and five-year direction
- **Constraint:** Architectural convergence only. No new large subsystem is
  proposed for the v0.5 release.

## Executive Summary

CAPT has unusually strong raw material for foundational trustworthy-AI
infrastructure. It already contains working implementations of state-bound
verification, governed evidence, deterministic context packaging, append-only
transactions, provenance-aware memory, explicit invalidation, local recovery,
capability proof, and policy-gated execution. Those mechanisms address real
problems that model, agent, tool, and orchestration protocols generally leave to
each application.

CAPT is not yet presented or packaged as one coherent platform.

The largest weakness is not missing capability. It is semantic fragmentation:

- the same concepts are represented by multiple incompatible `Evidence`,
  `MemoryRecord`, `Checkpoint`, `Receipt`, identity, and verification types;
- the public architecture describes 70 subsystems across 12 layers, while the
  product can be explained by six durable primitives;
- authority and release documents describe older SHAs, versions, test counts,
  missing modules, and superseded release states;
- `capt_solo.api` claims to be the only sanctioned public API but does not expose
  Evidence, VSI, ContextPack, Verification, Governance, or most of Foundry;
- the wheel built from the reviewed release candidate omits
  `capt_solo.evidence`, `capt_solo.verification`, and `capt_solo.ontology`, even
  though the public story depends on them;
- the README leads with a cognitive runtime and a list of subsystems rather than
  the problem CAPT uniquely solves.

The recommended convergence is:

> CAPT is the local-first verification substrate for AI systems. It binds claims,
> context, tool results, and actions to evidence, state, policy, and receipts so
> they can be inspected, reproduced, and recovered across models and runtimes.

The smallest architecture capable of supporting that promise has six pillars:

1. **Identity & Scope** — what is being evaluated, in which state and authority
   boundary.
2. **Evidence** — what was observed, where it came from, and whether it still
   applies.
3. **Verification** — which policy was evaluated against which evidence and
   state, with what result.
4. **Context** — deterministic, portable projections of relevant records for a
   model, human, or tool.
5. **Transactions** — consequential operations with intent, lifecycle,
   idempotency, receipts, and recovery.
6. **Governance** — consent, capabilities, policy, invalidation, audit, and
   release gates.

Memory, Workspace, Knowledge, Foundry, KHSB, lifecycle, engines, learning, and
protocol integrations remain valuable. They become services, reference
implementations, or plugins built on the six pillars rather than additional
foundational primitives.

### Bottom line

CAPT is technically closer to foundational infrastructure than its current
public surface suggests. Its mechanisms are strong; its conceptual and packaging
boundaries are not. The correct v0.5 move is to freeze feature expansion, repair
the distribution and documentation truth, publish a minimal set of stable
contracts, and make one end-to-end verification story undeniable.

## Evidence Base

This review distinguishes inspected facts from architectural proposals.

| Evidence | Current fact | Consequence |
|---|---|---|
| `capt_solo/contextpack/` | Deterministic ContextPack v1 exists with canonical JSON, digests, protected facts, assumptions, validation, and handoff | Context is already a portable verified projection, not merely a prompt string |
| `capt_solo/evidence/` | Evidence records, invalidation, reuse, proof graph, workspace isolation, promotion, checkpoints, and self-modification governance exist | Evidence is a platform capability, not a Foundry implementation detail |
| `capt_solo/verification/` | VSI binds verification to repository state, scope, dependencies, runtime, environment, and command | CAPT has the nucleus of artifact-agnostic state-bound verification |
| `capt_solo/ctp/` and `continuity/receipts.py` | Local append-only operation and receipt chains exist | Consequential actions can produce recoverable audit records |
| `capt_solo/foundry/` | Proof requirements, capability lifecycles, ClaimGuard, workflow proof, validation, and governance exist | Verification policies already apply beyond code tests |
| `capt_solo/memory/` | Local persistence, provenance, confidence, retrieval, replay, consent, sync abstractions, and multiple memory views exist | Memory should be a record store and retrieval service, not the definition of CAPT |
| `architecture/registry.yaml` | 70 canonical subsystem entries, including 22 marked Research and five Concept | The registry is useful as an implementation catalogue but too large as the public mental model |
| `capt_solo/api.py` | Public facade exposes mostly memory, lifecycle, CTP, and KHSB | The declared “only sanctioned import path” excludes CAPT's strongest differentiators |
| `pyproject.toml` and built wheel | Evidence, Verification, and Ontology packages are not declared or shipped | Current `0.5.0` artifacts cannot support the public architecture claim |
| live state documents | `CURRENT_STATE.md`, `CHECKPOINT.md`, `TASK_QUEUE.md`, and `RELEASE_STATE.md` refer to older branches, SHAs, versions, and completed work as pending | The self-describing workspace currently fails semantic integrity despite structural validation passing |

## How Strong Is CAPT Today?

### What is genuinely strong

- **State-bound verification:** VSI correctly rejects the idea that verification
  expires merely because a conversation continues. It binds results to concrete
  state and invalidation.
- **Evidence lifecycle:** evidence can be current, partial, superseded,
  invalidated, quarantined, expired, unverified, or conflicted. This is much
  stronger than a boolean “verified” flag.
- **Deterministic context:** ContextPack v1 has a versioned schema, canonical
  representation, protected-fact gate, explicit assumptions, and replayable
  handoff.
- **Local sovereignty:** SQLite, JSON/JSONL, explicit export, local state roots,
  and disabled-by-default networking give CAPT a credible local-first baseline.
- **Governed action:** CTP, consent, capability declarations, ClaimGuard, and
  governance receipts create boundaries around consequential operations.
- **Failure honesty:** unknown, stale, invalidated, unsupported, and degraded are
  first-class outcomes rather than hidden fallbacks.
- **Testing discipline:** the last frozen executable candidate recorded 669
  passing tests, 46 runtime checks, and 15 registry checks.

### What prevents foundational adoption

- There is no single canonical record envelope shared by Evidence, Verification,
  ContextPack, CTP, Foundry, Knowledge, and checkpoints.
- “Verification” currently means several different things depending on package:
  test execution, evidence status, knowledge corroboration, proof requirements,
  continuity policy, or claim language.
- The documentation corpus preserves implementation history at the expense of a
  current fifteen-minute explanation.
- Stable public APIs are package-accidental rather than deliberately tiered.
- The build artifact excludes central advertised packages.
- Model/protocol neutrality is a philosophy, not yet demonstrated by small,
  conformance-tested adapters.
- The release still lacks a sealed repository-wide security report.

## Public Product Narrative

### One sentence

CAPT makes AI work inspectable, reproducible, and recoverable by binding every
claim, context, tool result, and action to evidence, state, policy, and receipts.

### One paragraph

CAPT is a model-agnostic, local-first verification substrate for AI applications.
It sits beneath models, agents, tools, and workflows and records what was known,
what state was evaluated, what evidence supported a result, what policy was
applied, and what action occurred. CAPT produces deterministic context packages
and portable verification receipts that can be inspected, replayed, invalidated,
exported, or independently checked without requiring a cloud service or a
particular model provider.

### One page

AI systems can call tools, exchange messages, retrieve memories, and produce
artifacts. Most cannot answer five operational questions consistently:

1. What exact state produced this result?
2. What evidence supports the claim?
3. Which assumptions or uncertainties remain?
4. Which policy authorized the action?
5. Can another runtime verify or recover it?

CAPT provides the missing substrate. Evidence records preserve origin and
applicability. Verified State Identity binds checks to concrete state.
ContextPack creates deterministic, portable working context. CTP records
consequential actions and recovery state. Governance applies consent,
capabilities, invalidation, and release policy. The same contracts can serve a
CLI, CI pipeline, IDE, MCP host, A2A agent, local model, research workflow, or
robotics controller.

CAPT does not replace the model, agent framework, vector database, or orchestration
system. It makes their work verifiable.

### One website

The first public website should be a single evidence-led page:

1. **Hero**
   - Headline: “Trustworthy AI needs more than a model.”
   - Subhead: “CAPT binds AI work to evidence, state, policy, and receipts—locally,
     deterministically, and across runtimes.”
   - Primary action: “Verify a result in five minutes”
   - Secondary action: “Read the architecture”
2. **The five questions**
   - Show one unverified agent result and the five unanswered questions above.
3. **One concrete flow**
   - Input artifact → evidence → verification policy → ContextPack → action
     receipt → invalidation/replay.
4. **Six pillars**
   - One sentence and one inspectable JSON example per pillar.
5. **Works underneath your stack**
   - Local Python, CLI/CI, MCP, A2A, IDEs, and model providers as adapters.
   - Avoid provider-logo theater until each adapter is tested.
6. **Proof, not adjectives**
   - Reproducible test commands, release SHA, artifact hashes, package contents,
     security status, and conformance fixtures.
7. **Adopt one piece**
   - Evidence only, Verification only, ContextPack only, or full runtime.
8. **Boundaries**
   - What CAPT does not do: train models, host prompts, hide reasoning, or require
     cloud state.
9. **Governance**
   - Local-first promise, compatibility policy, security reporting, and ADRs.

The website should not lead with “cognitive operating system,” 70 subsystems, or
biological module names. Those are implementation history and research context,
not the first public value proposition.

## Simplified Architectural Map

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Adapters: CLI · CI · IDE · MCP · A2A · Hermes · model/tool providers │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│ Services: Memory · Workspace · Knowledge · Foundry · Coordination    │
│           Procedures · Lifecycle · domain engines                    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│ CAPT Verification Kernel                                             │
│ Identity & Scope │ Evidence │ Verification │ Context │ Transactions  │
│ Governance                                                          │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│ Storage & Crypto Ports: record store · ledger · canonical codec      │
│ hashing · signing (optional) · clock · policy store                  │
└──────────────────────────────────────────────────────────────────────┘
```

### Layer responsibilities

**Kernel** defines portable records and deterministic decisions. It has no
provider SDK, UI, framework, network, or domain engine dependency.

**Services** use kernel contracts to provide persistence, retrieval, workflow,
coordination, and domain behavior. They are independently adoptable.

**Adapters** translate external protocols and runtimes into kernel records. An
adapter never becomes the canonical CAPT data model.

**Ports** isolate persistence, canonicalization, hashing, time, and optional
signing so implementations can evolve without breaking records.

## Foundational Principles

The existing invariants are directionally strong. For a public platform, they
should be compressed into timeless principles:

1. **Every consequential assertion is inspectable.** A result identifies its
   subject, evidence, policy, state, and producer.
2. **Verification is state-bound.** A result remains applicable only while its
   subject state and policy remain equivalent.
3. **Uncertainty and invalidation are data.** Unknown, stale, conflicted,
   partial, and revoked are explicit outcomes.
4. **Context is a projection, not authority.** A context package references
   source records and cannot define its own truth.
5. **Actions produce receipts.** Consequential operations declare authority,
   intent, lifecycle, idempotency, and recovery state.
6. **Local ownership is the default.** Users can inspect, export, delete, fork,
   and leave without a network or service account.
7. **Optional capabilities fail independently.** Provider, protocol, model, and
   plugin failures cannot silently corrupt the kernel.
8. **Compatibility is contractual.** Schemas, canonicalization, migrations, and
   conformance fixtures are versioned before implementation expands.
9. **Trust is minimized through verification.** Claims about CAPT itself are
   backed by reproducible evidence.
10. **Architecture has one present tense.** Historical evidence is preserved,
    but current authority documents cannot contradict the shipped artifact.

These principles should become the public constitution. Biological analogies
and internal layer numbering can remain in research and design documents.

## Conceptual Duplication and Convergence Decisions

### Evidence

Current representations include:

- `capt_solo.evidence.core.EvidenceRecord`
- `capt_solo.knowledge.evidence.EvidenceRecord`
- `capt_solo.foundry.proof.Evidence`
- `capt_solo.verification.record.VerificationEvidence`
- `capt_solo.continuity.runtime.ContinuityEvidence`
- `capt_solo.evidence.providers.OperationalEvidence`
- `capt_solo.memory.interfaces.SourceEvidence`

**Decision:** `capt_solo.evidence.EvidenceRecord` becomes the canonical evidence
record. Other types become typed views, adapters, or deprecated compatibility
wrappers. They must not independently define status, provenance, identity, or
validity semantics.

### Verification and proof

VSI, Evidence reuse, Foundry ProofEngine, ClaimGuard, Knowledge verification,
continuity evaluation, and release gates all implement parts of one pipeline.

**Decision:** distinguish four terms:

- **check** — one observation-producing verifier execution;
- **evidence** — the resulting observation and provenance;
- **evaluation** — applying a policy to evidence for a subject state;
- **attestation** — the portable result of that evaluation.

“Proof” remains acceptable product language for an evidence aggregate, but the
public schema should use the four precise terms above.

### Identity

Current identity includes repository/project identity, memory identity, agent
identity, record IDs, VSI state identity, session IDs, and role identities.

**Decision:** define:

- `SubjectRef`: the thing being evaluated;
- `ActorRef`: the human, agent, tool, or organization responsible;
- `StateRef`: the immutable or content-addressed state of the subject;
- `ScopeRef`: the boundary within which the result applies.

VSI becomes one `StateRef` implementation for Git worktrees, not the universal
meaning of identity.

### Checkpoints

`evidence.checkpoint.MissionCheckpoint` and
`lifecycle.sessions.Checkpoint` overlap in mission state, progress, recovery, and
history.

**Decision:** one versioned `CheckpointRecord` envelope with typed payloads:
mission, session, workflow, or operation. Existing checkpoint classes become
views over the envelope until a future breaking release.

### Receipts and ledgers

CTP `Receipt`, `ContinuityReceipt`, `GovernanceReceipt`, verification records,
and ContextPack handoff digests all attest that an event or evaluation occurred.

**Decision:** use one versioned `ReceiptEnvelope` with:

- receipt ID and schema version;
- subject, actor, scope, and policy references;
- input and output digests;
- status and timestamps;
- parent receipt/transaction references;
- evidence and artifact references;
- verifier identity;
- optional signature metadata;
- typed payload.

CTP remains the operation journal. ReceiptEnvelope is the interchange contract.

### Memory and knowledge

Memory is storage/retrieval of records. Knowledge is a governed status or view
over claims and evidence. Neither should define a competing evidence model.

**Decision:** Memory stores records; Knowledge projects accepted claims under a
policy. Evidence and Verification remain upstream.

### Workspace

Workspace combines authority documents, repository state, tasks, checkpoints,
capability declarations, and CLI automation.

**Decision:** Workspace is the reference source adapter for software projects.
It is not a kernel primitive. Other subject adapters can represent documents,
datasets, prompts, robots, or research experiments without pretending to be Git
workspaces.

## Universal Verification Engine

### Goal

Verify any subject for which CAPT can identify state, collect evidence, and
evaluate a policy:

- code and build artifacts;
- memory and knowledge records;
- claims and model outputs;
- documents and research results;
- procedures and workflows;
- tools and agents;
- datasets;
- mission checkpoints;
- future CRP records.

### Minimal contracts

```python
class SubjectAdapter(Protocol):
    def identify(self, subject) -> SubjectRef: ...
    def snapshot(self, subject) -> StateRef: ...

class Verifier(Protocol):
    verifier_id: str
    def check(self, subject: SubjectRef, state: StateRef) -> list[EvidenceRecord]: ...

class PolicyEvaluator(Protocol):
    policy_id: str
    def evaluate(
        self,
        subject: SubjectRef,
        state: StateRef,
        evidence: list[EvidenceRecord],
    ) -> Evaluation: ...

class AttestationStore(Protocol):
    def append(self, attestation: Attestation) -> ReceiptEnvelope: ...
    def verify_integrity(self, receipt_id: str) -> IntegrityResult: ...
```

These are design contracts, not v0.5 implementation requirements.

### Pipeline

```text
subject
  → identify subject and state
  → select policy and verifiers
  → collect evidence
  → validate provenance and applicability
  → evaluate policy
  → emit attestation + receipt
  → project result into ContextPack, CLI, CI, MCP, or A2A artifact
  → invalidate when subject, policy, evidence, or authority changes
```

### Existing-component mapping

| Universal engine concept | Existing CAPT source |
|---|---|
| `SubjectRef` / `StateRef` | VSI, project context, memory identity, record digests |
| `EvidenceRecord` | Evidence Engine plus provider adapters |
| verifier | verification runner, validation harness, evidence providers, bubble checks |
| policy | VerificationPolicy, ProofRequirement, continuity policy, governance rules |
| evaluation | EvidenceDecision, ProofAggregate, ClaimVerdict, continuity result |
| attestation | VerificationRecord, ContextPackValidation, workflow proof |
| receipt/ledger | CTP Receipt, ReceiptChain, GovernanceReceipt |
| projection | ContextPack, handoff, CLI JSON, A2A artifact adapter |
| invalidation | InvalidationEvent, VSI diff, capability degradation |

### Interoperability posture

CAPT should map to established standards without adopting them as its internal
architecture:

- W3C PROV's `Entity`, `Activity`, and `Agent` provide a useful export mapping
  for Subject, Operation/Evaluation, and Actor.
- SLSA provenance and Verification Summary Attestations demonstrate the value of
  binding a signed verification result to an artifact digest, verifier, policy,
  and intended resource.
- MCP provides tools, resources, and prompts but explicitly leaves much consent
  and safety enforcement to hosts. CAPT can provide evidence, policy, receipt,
  and context contracts beneath an MCP host.
- A2A defines opaque agents, tasks, messages, artifacts, and extensions. CAPT can
  emit verification attestations as task artifacts or an extension without
  replacing A2A transport or task lifecycle.

The architectural opportunity is not another transport. It is a portable
verification and provenance layer that MCP, A2A, CI systems, IDEs, and agent
frameworks can all consume.

## Public API Strategy

### Principles

- Package-specific APIs are valid stable entry points.
- `capt_solo.api` remains a compatibility facade, not the only sanctioned import.
- Records are immutable or append-only at interchange boundaries.
- Every schema has a version, canonicalization rule, and fixture.
- Protocols depend on narrow interfaces, not `MemoryEngine` or SQLite internals.
- Optional integrations import lazily and fail independently.

### Proposed stable package surface

```text
capt_solo.identity       SubjectRef, ActorRef, StateRef, ScopeRef
capt_solo.evidence       EvidenceRecord, EvidenceSource, InvalidationEvent
capt_solo.verification   Verifier, Policy, Evaluation, Attestation
capt_solo.contextpack    ContextPack v1 construction and validation
capt_solo.transactions   Transaction, ReceiptEnvelope, Ledger
capt_solo.governance     Consent, Capability, Authority, PolicyDecision
```

For v0.5, do not rename packages or break imports. Publish the current central
packages correctly, document which interfaces are provisional, and introduce
aliases only when backed by an ADR and compatibility tests.

### Independently adoptable profiles

1. **Evidence profile** — records, provenance, status, invalidation, JSON codec.
2. **Verification profile** — Evidence profile + state adapters + policy
   evaluation + attestations.
3. **Context profile** — ContextPack v1 + referenced Evidence profile records.
4. **Transaction profile** — operation lifecycle, receipts, integrity chain.
5. **Workspace profile** — Git/filesystem reference adapter and CLI.
6. **Full runtime profile** — local stores, memory, lifecycle, Foundry, and
   integrations.

Profiles should first be extras and documented import boundaries, not separate
repositories. Split packages only when dependency or release cadence data
justifies it.

## Plugin Strategy

### Core

Core contains only contracts and deterministic reference implementations needed
to identify, evidence, verify, package context, record actions, and enforce
policy locally.

### Official plugins

- Git/workspace and CI verification
- MCP adapter
- A2A attestation/artifact adapter
- Hermes adapter
- SQLite record and ledger store
- Memory/knowledge service
- Foundry and workflow verification
- optional signing/Sigstore or in-toto export

Official means maintained and conformance-tested by CAPT, not imported by core.

### Experimental plugins

- HMC/ENGRAM/DREAM and adaptive learning
- mathematics, physics, and invention engines
- research adapters and biological/cognitive modules
- PULSE and provider-specific model gateways
- LAN or distributed synchronization

These can be excellent CAPT demonstrations without defining the kernel.

### Community plugins

Community plugins implement published protocols and run against a conformance
kit. They declare:

- plugin and contract versions;
- capabilities and side effects;
- persistence and network behavior;
- required authority and consent;
- input/output schemas;
- deterministic and nondeterministic behavior;
- verification requirements;
- failure and recovery semantics.

No plugin is “trusted” because it is installed. Trust follows evidence, policy,
authority, and verification.

## Candidate Removals, Merges, and Moves

| Candidate | Recommendation | Timing |
|---|---|---|
| `knowledge.evidence.EvidenceRecord` | Migrate to canonical Evidence Engine record; retain adapter temporarily | Post-v0.5 |
| `foundry.proof.Evidence` | Make a specialized view over canonical evidence | Post-v0.5 |
| `memory.interfaces.MemoryRecord` vs `memory.types.MemoryRecord` | Select one canonical persisted/interchange record and migrate the other | Before public API stability claim |
| Mission and session checkpoints | Converge on typed CheckpointRecord envelope | Design now; migrate later |
| CTP, continuity, governance receipt shapes | Converge on ReceiptEnvelope while preserving typed payloads | Design now; compatibility layer later |
| `capt_solo.api` as only import path | Remove that documentation rule; keep facade for compatibility | v0.5 docs |
| 70-subsystem map as public architecture | Retain as implementation/research registry; replace public map with six pillars | v0.5 docs |
| Mathematics/Physics/Invention in Core | Move to official experimental/domain plugins unless kernel dependency is proven | Next packaging cycle |
| Learning/research modules in Core | Move behind extras/plugins; core must not depend on them | Next packaging cycle |
| PULSE in base module | Package as optional network plugin | Before claiming zero-network package |
| duplicate root/canonical docs | Generate root pointers and live state from one source; archive stale evidence snapshots | v0.5 docs |
| two changelogs | Select one current changelog; clearly label/archive the historical duplicate | v0.5 docs |

Removal means migration and deprecation, never silent deletion.

## Missing Capabilities, Prioritized

### P0 — blocks a credible public release

1. **Package truth:** ship Evidence, Verification, and Ontology in the wheel or
   remove them from release claims.
2. **Documentation truth:** refresh live state, public API, architecture,
   changelog, test counts, branch/SHA, and release status from the current tree.
3. **Canonical record decision:** declare which Evidence, MemoryRecord,
   Checkpoint, and Receipt types are stable versus compatibility/internal.
4. **Security closure:** finish and seal the repository-wide security scan.
5. **Artifact conformance:** install the final wheel and sdist in clean
   environments and run per-profile import and fixture tests.

### P1 — establishes the verification platform

1. Subject/State/Actor/Scope reference contracts.
2. Generic Verifier and PolicyEvaluator protocols.
3. Versioned Attestation and ReceiptEnvelope schemas.
4. Conformance fixtures and a `capt verify <subject>` CLI contract.
5. Invalidation rules that apply to non-Git subjects and policies.
6. Clear authority and consent semantics at tool/action boundaries.

### P2 — external adoption

1. MCP resource/tool-result adapter with explicit user-authority mapping.
2. A2A task-artifact/extension adapter.
3. W3C PROV export mapping.
4. SLSA/in-toto-compatible artifact attestation export.
5. IDE and CI examples with machine-readable outcomes.
6. Language-neutral JSON Schemas and compatibility test vectors.

### P3 — scale without capture

1. Optional signing and delegated verifier roots.
2. Federated or remote receipt verification without central CAPT accounts.
3. Append-only multi-party transparency and revocation mechanisms.
4. Distributed stores and coordination as replaceable transports.

## Developer Experience Review

### First-clone friction

- README uses `git clone <repo>` rather than a real public URL.
- The package description says “cognitive runtime for individual developers,”
  which hides the verification value.
- Architecture starts with 12 layers and 70 subsystems.
- `docs/API.md` still calls itself v0.1 and omits current public packages.
- status and checkpoint files are stale but labeled authoritative.
- the wheel and source checkout expose different capabilities.
- `capt_solo.api` conflicts with package-level APIs already documented as public.
- install, verification, architecture validation, and workspace validation are
  separate narratives rather than one guided path.

### Fifteen-minute onboarding target

1. Install `capt-solo`.
2. Run one command against a file, repository, model output, or tool result.
3. Inspect Evidence, State, Policy, Evaluation, and Receipt JSON.
4. Modify the subject and see invalidation.
5. Export a ContextPack or attestation.
6. Verify the artifact independently.

The tutorial should make CAPT's value visible before mentioning memory taxonomy,
Foundry internals, or cognitive research.

### Recommended CLI shape

```text
capt inspect <subject>
capt verify <subject> --policy <policy>
capt evidence show <id>
capt context build <subject> --for <consumer>
capt receipt verify <receipt>
capt invalidate explain <attestation>
capt doctor
```

This is directional API design, not authorization to replace the current CLI in
v0.5.

## Ecosystem Strategy

| Ecosystem | CAPT role | Boundary |
|---|---|---|
| IDEs | verify edits, tool results, checkpoints, and generated patches | local adapter; no editor-specific state in kernel |
| MCP | attach evidence/context resources and receipt-producing tool wrappers | MCP remains transport/tool protocol |
| A2A | emit/consume verified task artifacts and capability attestations | A2A remains agent communication protocol |
| GitHub/CI | state adapters, policy checks, release attestations | provider adapters; no GitHub dependency in core |
| Desktop | inspect records, consent, invalidation, and recovery | UI consumes public records; UI not authoritative |
| Robotics | state snapshots, safety policy, action receipts, rollback | real-time/safety execution remains external |
| Research | provenance for datasets, methods, claims, and derived artifacts | map domain records into Subject/Evidence/Policy |
| Future protocols | implement adapters against language-neutral contracts | never redesign kernel around a transport |

## Bridge Toward CRP

CRP should not be implemented in this release. Compatibility becomes inexpensive
if CAPT records already carry:

- schema and canonicalization version;
- subject, actor, state, scope, and authority references;
- evidence and policy references;
- input/output/artifact digests;
- parent/causal receipt links;
- status, uncertainty, invalidation, and recovery metadata;
- extension fields that are namespaced and integrity-covered.

CRP can then define additional record types or transport semantics without
replacing ContextPack, Evidence, Verification, or CTP. The bridge is a stable
record envelope, not speculative CRP runtime code.

## The Next Major Opportunity

Current protocols solve adjacent layers:

- MCP standardizes how applications expose tools, resources, and prompts.
- A2A standardizes communication with opaque agents and task artifacts.
- W3C PROV standardizes interoperable provenance concepts.
- SLSA and in-toto standardize verifiable software supply-chain attestations.

The missing layer is **cross-runtime verification of AI work**.

An AI-generated result can move through a model, tool server, agent, memory
system, CI job, and human approval while losing the state, evidence, assumptions,
policy, and authority that made it acceptable. Each platform emits logs, but logs
are not portable applicability proofs.

CAPT can own this category:

> a portable verification envelope and runtime for claims, contexts, artifacts,
> and actions across AI systems.

That opportunity is larger and clearer than “cognitive operating system.” It
uses CAPT's strongest existing work and gives every future subsystem a simple
test: does it improve the creation, evaluation, portability, or recovery of
verified AI work?

## Release Readiness Scorecard

Scores reflect the reviewed `ac849a4` tree and built `6075d55` artifact evidence,
not future proposals.

| Dimension | Score / 10 | Rationale |
|---|---:|---|
| Architecture | 6.5 | Strong mechanisms; fragmented primitives and oversized public map |
| DX | 4.5 | Working commands, but stale onboarding and source/wheel mismatch |
| Documentation | 4.0 | Extensive and thoughtful, but substantial present-tense drift |
| Verification | 8.0 | VSI, evidence reuse, invalidation, fixtures, and runtime gates are distinctive |
| Security | 6.5 | Good local-first controls and one traversal fix; full scan not sealed |
| Extensibility | 6.0 | Many package seams, but public contracts and plugin tiers are inconsistent |
| Adoption Potential | 6.5 | Real category value hidden by cognitive-runtime framing |
| Standards Readiness | 4.5 | Natural mappings exist; no conformance-tested standards adapters yet |
| Innovation | 8.5 | State-bound verification plus deterministic context and invalidation is compelling |
| Long-term Maintainability | 5.5 | High test volume, but duplicated records and documentation entropy will compound |

**Overall readiness: 6.1 / 10 — technically promising, not yet publicly coherent.**

### Release decision

**NOT READY for broad public release.**

This is not a recommendation for more subsystem development. It is a bounded
release-hardening decision. The minimum path to readiness is:

1. repair wheel contents;
2. reconcile current authority and public docs;
3. declare stable/provisional APIs and record ownership;
4. complete the security report;
5. run exact-SHA install and conformance verification;
6. publish one verification-first tutorial and narrative.

## Five-Year Roadmap by Category

### 1. Verification substrate

CAPT becomes the local reference runtime and schema set for evidence, state-bound
verification, deterministic context, and action receipts.

### 2. Portable verification ecosystem

Language-neutral schemas, conformance fixtures, verifier SDKs, policy packs, and
receipt inspectors allow developers to adopt one CAPT profile without the full
runtime.

### 3. AI interoperability trust layer

MCP, A2A, CI, IDE, model, research, and robotics adapters exchange CAPT
attestations while keeping their own transports and execution models.

### 4. Federated verification infrastructure

Independent verifiers, signed attestations, revocation, transparency, and
multi-party policy evaluation reduce trust in any single vendor—including
Inversion Labs.

### 5. Verification commons

CAPT becomes an open standard and shared vocabulary for answering:

- what happened;
- to which subject and state;
- using which evidence and policy;
- under whose authority;
- with which uncertainty;
- and whether the result still applies.

Success is not CAPT owning every runtime. Success is diverse runtimes producing
and verifying compatible records.

## Architectural Decisions Required

The following decisions need ADRs before implementation:

1. Adopt the six-pillar public architecture while retaining the 70-subsystem
   registry as an implementation/research catalogue.
2. Name `capt_solo.evidence.EvidenceRecord` as the canonical evidence record.
3. Define SubjectRef, ActorRef, StateRef, and ScopeRef.
4. Define Check, Evaluation, Attestation, and ReceiptEnvelope semantics.
5. Reclassify Memory, Workspace, Knowledge, Foundry, KHSB, engines, learning, and
   research as services/adapters/plugins relative to the verification kernel.
6. Replace the “only sanctioned `capt_solo.api` import” rule with tiered stable
   package APIs.
7. Adopt a plugin-tier and conformance policy.

No item above requires building a large subsystem before v0.5.

## Immediate Bounded Roadmap

### Before public release

- Fix distribution-package omissions.
- Replace stale live state and API documentation.
- Add a machine-checked version/package/public-import consistency gate.
- Document stable, provisional, and internal interfaces.
- Complete the active security scan.
- Verify wheel and sdist imports for every advertised profile.
- Create one end-to-end verification tutorial and fixture.

### Immediately after release

- Write the canonical record-envelope ADRs.
- Add generic SubjectAdapter, Verifier, and PolicyEvaluator protocols.
- Converge duplicate evidence and record types through compatibility adapters.
- Produce one MCP and one CI adapter as reference integrations.

### Explicitly defer

- CRP runtime implementation;
- distributed schedulers or hierarchical memory;
- new cognitive modules;
- cloud control planes;
- central accounts or hosted lock-in;
- speculative multi-agent orchestration;
- broad package splitting without adoption evidence.

## Final Assessment

CAPT's architecture becomes inevitable when it stops asking developers to adopt
a cognitive universe and starts solving one painful universal problem:

> AI work is easy to generate and hard to verify.

CAPT already contains most of the mechanisms needed to solve that problem. The
next step is not invention. It is discipline: one record model, one current
architecture, one honest package, one minimal public surface, and one compelling
verification flow.

That is the foundation worth publishing.

## External Standards References

- [Model Context Protocol architecture](https://modelcontextprotocol.io/docs/learn/architecture)
- [MCP server primitives and control model](https://modelcontextprotocol.io/specification/2025-06-18/server/index)
- [Agent2Agent core concepts](https://a2a-protocol.org/latest/topics/key-concepts/)
- [Agent2Agent protocol specification](https://a2a-protocol.org/latest/specification)
- [W3C PROV overview](https://www.w3.org/TR/prov-overview/)
- [W3C PROV-O](https://www.w3.org/TR/prov-o/)
- [SLSA provenance](https://slsa.dev/spec/v1.2/provenance)
- [SLSA Verification Summary Attestation](https://slsa.dev/spec/v1.2/verification_summary)
