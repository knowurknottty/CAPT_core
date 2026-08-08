# CAPT Core v0.6 — Productization Source of Truth

**Status:** canonical planning document for v0.6 productization
**Baseline:** `main` at `a621814925948af9fe245889736043930d9c9b51`
**Release criterion:** normal-human usability, not architecture completeness alone

## Governing release question

CAPT is not ready for broad public release merely because the architecture is implemented, tested, installable, or release-proven.

The governing question is:

> Could a normal technically capable human pick up this repository, understand what CAPT is, install it, achieve a meaningful first success, and use the primary workflows effectively without direct guidance from the author?

For the current v0.5 experience, the answer is **no**.

v0.6 is therefore a **productization release**. Its primary purpose is not to add another large architecture layer. Its purpose is to make the existing architecture understandable, discoverable, usable, demonstrable, and supportable.

## Current assessment

| Dimension | Assessment |
|---|---|
| Architecture | Very strong and coherent |
| Implementation breadth | Very strong and substantial |
| Verification/release evidence | Strong |
| Documentation accuracy | Strong after v0.5 audit |
| Human onboarding | Weak |
| Developer experience | Weak-to-moderate |
| Product identity | Insufficiently obvious |
| Operator usability | Insufficiently polished |
| Demoability | Weak relative to capability breadth |

The primary gap is **cohesion and user experience**, not foundational capability.

## Product thesis

The simplest useful public explanation is:

> A model is transient and replaceable. CAPT owns the durable memory, governed state, evidence, authority, execution history, context policy, and recovery around it.

Or more compactly:

> **The model becomes stateless. CAPT becomes stateful.**

Every public surface should reinforce this thesis.

## Release-blocking hanging points

### P0 — Canonical onboarding and first success

#### 1. No canonical `Start Here`

A new user does not have one authoritative path from clone/install to meaningful CAPT usage.

Required outcome:
- one obvious `START_HERE.md` or equivalent top-level path;
- prerequisites;
- install;
- launch;
- first memory action;
- first governed runtime action;
- checkpoint/restart demonstration;
- evidence inspection;
- clear next steps.

Acceptance criterion:

> A technically capable user unfamiliar with CAPT can complete the path without author assistance.

#### 2. No five-minute win

Installation currently does not immediately demonstrate CAPT's value.

Required outcome:
- a deterministic quickstart that reaches visible success in minutes;
- commands must be copy/paste safe;
- no undocumented state or author-specific environment assumptions.

#### 3. No single mental model

The user encounters too many components before understanding the system.

Required outcome:
- one canonical architecture diagram;
- one short explanation of the control flow;
- all deeper subsystem docs reference the same diagram and terminology.

Canonical simplified shape:

```text
Human / Application
       |
       v
CAPT Runtime Harness
       |
       +--> Governance / Authority
       +--> Memory / Context
       +--> EventStore / Recovery
       +--> Evidence / Verification
       +--> Bounded Drivers
                |
                v
         Replaceable Models
```

### P0 — Product identity and workflow clarity

#### 4. Product identity is not obvious enough

A newcomer should not have to decide whether CAPT is primarily a memory library, SDK, runtime, agent, desktop app, framework, plugin, or research architecture.

Required outcome:
- one primary category and one-sentence definition;
- secondary surfaces presented as parts of the product, not competing identities.

Recommended public category:

> Local-first governed runtime and continuity substrate for AI agents.

#### 5. Too many nouns before value

Current terminology is architecturally correct but cognitively expensive.

Examples include CAPT Core, CAPT Solo, Runtime Harness, EventStore, CTP, KHSB, Foundry, ClaimGuard, ContextPack, Memory Governor, DriverHost, Capability Registry, Knowledge Bubbles, and more.

Required outcome:
- progressive disclosure;
- user workflows first;
- subsystem names introduced only when needed;
- glossary for architecture readers.

#### 6. No canonical end-to-end workflows

Users need task-oriented workflows rather than module inventories.

At minimum document and demonstrate:

```text
Install -> Start -> Health -> Use -> Inspect -> Checkpoint -> Stop -> Resume
```

```text
Mission -> Approval -> Execution -> Evidence -> Verification -> Claim
```

```text
Remember -> Retrieve -> ContextPack -> Model -> Persist
```

### P0 — Demonstrability

#### 7. Missing flagship demos

The repository should ship at least five small end-to-end demonstrations:

1. **Durable memory** — store, retrieve, restart, retrieve again.
2. **Governed execution** — request, approve/deny, execute only after approval.
3. **Checkpoint/recovery** — stop process, restart, resume without repeating completed work.
4. **Evidence/verification** — inspect artifact evidence, VerificationResult, ClaimGuard outcome, and ledger trail.
5. **Cross-model continuity** — Model A performs work, CAPT checkpoints, Model B resumes from authoritative CAPT state.

The fifth demo is the strongest expression of CAPT's architectural thesis and should become the flagship v0.6 proof.

#### 8. CAPT's proof system is hidden from users

Evidence is one of the most differentiated parts of CAPT, but a user does not naturally see it.

Required outcome:
- one command or UI path that answers “why does CAPT say this is complete?”;
- display ledger events, evidence, verification, claim decision, and relevant receipts in a human-readable view.

### P0 — Surface coherence

#### 9. Public versus internal versus experimental surfaces remain cognitively expensive

The distinction is documented but still requires expertise.

Required outcome:
- explicit capability matrix using categories such as:
  - Public API
  - Operator-facing
  - Internal runtime
  - Experimental
  - Historical
  - Future
- no feature should appear equivalent merely because it imports successfully.

#### 10. No authoritative capability matrix for users

Required outcome:

| Feature | Implemented | Tested | Installed | Operator-facing | Real-process proven | Notes |
|---|---:|---:|---:|---:|---:|---|

This should be generated or mechanically checked where practical.

### P1 — Installation and platform usability

#### 11. Installation/support matrix is incomplete

Required outcome:
- macOS support;
- Linux support;
- Windows status;
- supported Python versions;
- local-model runtime compatibility;
- hosted-provider compatibility;
- explicit Unsupported / Experimental labels.

#### 12. Harness startup is too manual

The current `capt harness` lifecycle requires users to understand ledger paths, socket paths, token files, and service lifecycle details too early.

Required outcome:
- sensible defaults;
- automatic local state-directory allocation;
- one command to start a normal local runtime;
- advanced flags remain available.

Ideal shape:

```zsh
capt start
capt status
capt stop
```

with `capt harness ...` remaining available as an expert/debug surface.

#### 13. No polished troubleshooting path

Required outcome:
- `capt doctor` becomes a first-class support surface;
- common failures mapped to remediation;
- runtime won't start;
- stale socket;
- invalid token/session;
- missing driver;
- model unavailable;
- memory integrity error;
- checkpoint/recovery error;
- approval blocked;
- optional dependency degraded.

### P1 — Model/provider usability

#### 14. Driver configuration is not normal-human friendly

Model integration should not require understanding DriverHost internals.

Required guides/configuration for at least the intended supported set:
- LM Studio;
- Ollama;
- llama.cpp;
- MLX / mlx_lm;
- vLLM;
- OpenRouter;
- Hermes compatibility.

Each guide should say:
- prerequisites;
- discovery/configuration;
- context limit;
- credentials if applicable;
- health check;
- first governed call;
- limitations.

#### 15. Model discovery/configuration is not unified

Required outcome:
- a model/provider configuration abstraction;
- discoverability via CLI;
- example:

```zsh
capt models list
capt models add ...
capt models test ...
capt models use ...
```

Exact command design may differ, but the workflow must be obvious.

### P1 — Desktop/operator experience

#### 16. Desktop is not yet the obvious default experience

The architecture already has desktop/runtime client work, but the repository remains library/CLI-first from a normal-user perspective.

Required decision:
- either make desktop the recommended end-user surface;
- or explicitly state that v0.6 remains developer-first and make the CLI excellent.

Do not leave both surfaces appearing equally primary without guidance.

#### 17. No polished operator dashboard for authoritative state

A usable operator experience should expose:
- runtime health;
- active mission;
- task state;
- approval queue;
- active model/driver;
- memory/context status;
- checkpoint status;
- evidence/verification status;
- event timeline;
- cancel/stop/resume controls.

Authority must remain in RuntimeService; UI is projection/control only.

### P1 — Documentation information architecture

#### 18. Whitepaper should not be the onboarding path

The whitepaper is valuable for architecture/research audiences but should come after first success.

Recommended hierarchy:

```text
README
  -> Start Here
  -> Quickstart
  -> Demos
  -> User Guide
  -> Integration Guide
  -> Troubleshooting
  -> Architecture
  -> API Reference
  -> Whitepaper
  -> Release Evidence
```

#### 19. Persona-specific entry points are missing

At minimum:
- “I want to evaluate CAPT”
- “I want to use CAPT locally”
- “I want to integrate CAPT into Python”
- “I want to add a model/provider”
- “I want to extend CAPT”
- “I want to audit CAPT's claims/security”

### P1 — Public credibility / release packaging

#### 20. Release artifact consumption is not polished

Technical wheel proof exists, but normal users should not need release-evidence knowledge to install the software.

Required outcome:
- canonical installation mechanism;
- versioned releases/tags;
- release notes;
- checksums/signature direction;
- compatibility matrix;
- known limitations.

#### 21. Private vulnerability reporting needs a clear channel

Current security documentation says to report privately but must provide an actual supported mechanism before broader release.

### P2 — Engineering hardening that should accompany productization

These are important but should not displace the P0 usability work:

- modernize Python packaging/license metadata;
- restore meaningful scoped or changed-line coverage enforcement;
- selectively port still-relevant adversarial OpenHarness tests from historical PR work;
- independently validate the rewritten Hermes compatibility package;
- improve ContextPack observability;
- add stronger release attestations/signing where appropriate;
- optional encrypted backup/export;
- stronger process isolation for external drivers;
- additional retrieval adapters;
- policy-driven memory retention/consolidation/archival.

## v0.6 non-goals

Unless required by the usability work, v0.6 should avoid:

- inventing another runtime;
- replacing RuntimeService authority;
- making Hermes canonical;
- large speculative architecture expansions;
- distributed KHSB merely for feature count;
- multi-user enterprise architecture before the single-user product is usable;
- adding more nouns without a demonstrated user workflow.

## v0.6 release gate

v0.6 is ready for broad public release when an independent technically capable person can, using only public repository materials:

1. understand CAPT's purpose within five minutes;
2. install it without author-specific knowledge;
3. run a health check;
4. configure or select at least one supported model path;
5. execute one governed mission;
6. understand and respond to an approval request;
7. inspect memory/context behavior;
8. checkpoint and stop the runtime;
9. restart and resume without repeated completed work;
10. inspect the evidence/verification chain;
11. diagnose at least common failures using documented tools;
12. identify accurately what is public, internal, experimental, and unsupported.

The test should be performed by someone who has not participated in CAPT development.

## Preferred flagship acceptance demonstration

The v0.6 release should culminate in a cross-model continuity proof:

```text
Model A
  -> governed mission
  -> real work
  -> evidence persisted
  -> CAPT checkpoint
  -> Model A removed

Model B
  -> attach to same CAPT runtime state
  -> recover bounded ContextPack
  -> inspect prior completed work
  -> continue without repeating it
  -> create new evidence
  -> verification
  -> ClaimGuard
  -> inspect complete provenance chain
```

This demonstration must prove that continuity belongs to CAPT rather than to either model's transcript.

## Source-of-truth rule

This document is the canonical v0.6 productization plan unless explicitly superseded by a later committed document.

Future agents and contributors should retrieve this file from the repository rather than relying on chat history or remembered project state.

Changes to priorities should be made through reviewed Git commits so the plan remains inspectable and reproducible.
