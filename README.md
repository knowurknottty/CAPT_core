# CAPT Core

**Local-first governed runtime, continuity substrate, and operator layer for AI systems.**

> **The model becomes replaceable. CAPT keeps the state, authority, evidence, memory, and recovery.**

CAPT moves the responsibilities that should not live inside a transient model session into a durable local runtime: authoritative state, memory, execution history, governance, evidence, verification, capability control, context policy, checkpoint/recovery, and operator control.

The model is an inference component. **CAPT is the system of record around it.**

---

## Current repository status

CAPT Core is presently between the proven standalone v0.5 package release and the next integrated product/runtime release.

- **Package metadata remains `0.5.0`.** That is the latest numbered package release represented by `pyproject.toml`.
- **`main` is substantially newer than the original v0.5 release.** The v0.6 productization work is merged: simplified onboarding, shared operator layer, provider/model management foundations, CaveCAPT verbosity, Textual TUI MVP, Tk operator MVP, and the native SwiftUI client contract.
- **The next integration lane is active but not yet shipped.** Discovery governance, hardened governed execution lifecycle, prompt/cognitive provenance, the upgraded TUI run surface, Cohort coordination, and the fail-closed security gate are being reconciled through the current PR stack.
- **A branch or PR implementation is not described here as shipped merely because the code exists.** This README separates merged behavior from active integration work and from release proof.

### Active integration stack

| PR | Area | Current classification |
|---|---|---|
| #44 | Discovery Governor + bounded local scanner | Implemented and locally verified; not yet merged |
| #46 | Governed Hermes/Ouroboros execution lifecycle | Hardened lifecycle and recovery semantics; not yet merged |
| #47 | Prompt assembly, cognitive provenance, TUI upgrade, provider-run integration | **Near-complete integration slice; not yet merged** |
| #48 | Bounded Cohort coordination | Coordination contracts verified; durable runtime integration remains later work |
| #49 | Fail-closed security infrastructure gate | Draft; intentionally blocked until exact-head evidence and remaining controls close |

This stack is cumulative. Later PRs build on earlier integration branches rather than redefining CAPT authority.

---

## Start here

For the canonical walkthrough, use [`START_HERE.md`](START_HERE.md).

For the current normal-human install, including the Textual TUI:

```zsh
git clone https://github.com/knowurknottty/CAPT_core.git
cd CAPT_core
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[ui]'
```

Verify the environment and start CAPT:

```zsh
capt --version
capt doctor
capt start
capt status
```

Exercise durable state:

```zsh
capt memory store "CAPT keeps durable state outside the model."
capt memory search "durable state"
capt evidence
capt checkpoint
```

Launch the current merged TUI:

```zsh
capt-ui dashboard
```

Then stop and resume without repeating completed work:

```zsh
capt stop
capt resume
capt status
```

The expert harness surface remains available through `capt harness ...` when explicit socket/token/ledger control is required.

---

## What is merged on `main`

### Governed runtime and continuity

The current default branch contains the core runtime architecture that makes CAPT more than a prompt wrapper:

- authoritative ordered **EventStore** history with integrity checking;
- authenticated local RuntimeService IPC;
- mission/task/runtime aggregates and governed state transitions;
- capability grants and bounded leases;
- DriverHost and execution-driver boundaries;
- checkpoint, restart, replay, idempotency, and no-repeat recovery;
- CAPT Solo durable Memory Engine;
- Runtime Memory Governor and ContextPack policy;
- CTP operational transaction/recovery journaling;
- KHSB in-process coordination;
- evidence and verification machinery;
- ClaimGuard;
- proof/workflow/Foundry/Knowledge Bubble components;
- bounded Hermes compatibility execution, with the strongest historical release proof centered on controlled inspection rather than unrestricted autonomous repository mutation.

### Normal operator surfaces

`main` also contains the productization layer that was not present in the original v0.5 experience:

| Surface / capability | Merged status |
|---|---|
| `capt` normal CLI | **SHIPPED** |
| `capt start/status/stop/checkpoint/resume/evidence/doctor` | **SHIPPED** |
| durable memory store/search from CLI | **SHIPPED / PROVEN** |
| shared `capt_ui.operator` facade | **SHIPPED** |
| Textual TUI | **SHIPPED MVP** |
| human approve/deny through TUI | **SHIPPED MVP** |
| provider registration/configuration | **SHIPPED** |
| provider health/model discovery where supported | **SHIPPED** |
| model selection/favorites/override foundations | **SHIPPED** |
| CaveCAPT Minimal/Normal/Detailed/Diagnostic presentation modes | **SHIPPED** |
| first-run operator onboarding flow | **SHIPPED** |
| Tk desktop operator | **OPERATOR MVP / reference fallback** |
| native SwiftUI surface | **CLIENT CONTRACT / LIBRARY ONLY** |
| real cross-model process-boundary continuity | **NOT YET RELEASE-PROVEN** |

The UI is deliberately thin. **CLI, TUI, and desktop surfaces do not become alternate runtimes.** Consequential mutations continue to route into RuntimeService.

---

## TUI: merged MVP and the nearly-complete upgrade

### What the merged TUI already does

The Textual TUI on `main` is a keyboard-first operator console over the same shared Operator facade used by the other surfaces.

It exposes:

- runtime health and integrity;
- mission/task state;
- memory/context state;
- evidence, verification, and ClaimGuard views;
- configured providers and models;
- human approval queue;
- logs/operator event feed;
- checkpoint/resume/cancel controls;
- CaveCAPT verbosity;
- governed approve/deny without direct EventStore or SQLite mutation.

The earlier bootstrap defect that prevented `capt-ui` from finding the token created by `capt start` has been fixed on `main`; both now resolve the canonical `runtime.sock` + `runtime.token` layout.

### What the active TUI integration adds

PR #47 upgrades the TUI from a monitoring/control MVP toward the intended CAPT operator cockpit. The code currently adds:

- provider and model selection directly in the governed run surface;
- **response modes:** `MAX`, `SPOCK`, `CAVE CAPT`, `MIN`;
- **requested context budgets:** 32K through 256K in 32K increments;
- **prompt enhancement engines:** `OFF`, `AUTO`, `OMNI`, `META`, `FORGE`, `SIGMA`;
- inspectable prompt enhancement instead of invisible prompt rewriting;
- clarification when the input is too underspecified to optimize safely;
- explicit **ENHANCE → REVIEW → APPROVE → RUN** operator flow when human verification is required;
- persisted non-secret prompt preferences;
- requested-versus-effective context provenance;
- prompt-assembly digest display on the current run;
- model-visible cognitive provenance carried through the governed execution path.

The enhancement layer is intentionally presentation-side and deterministic. It can propose a better execution prompt, but it cannot mint capability, bypass approval, write authoritative state, or declare work complete.

### Provider execution in the active integration lane

The active PR #47 lineage also contains a bounded `ProviderDriver` for actual inference transport:

- Ollama via its native `/api/generate` endpoint;
- OpenAI-compatible chat-completions transport for compatible remote/local providers;
- provider/model/endpoint provenance and prompt/response digests;
- secret exclusion from artifacts and returned diagnostics;
- explicit dispatch-boundary tracking;
- truthful cancellation semantics that do not pretend an underlying HTTP request was aborted when it was not;
- reconciliation for pre-dispatch, response-complete, and externally-unknown states.

**Important proof boundary:** the current provider-driver tests exercise the real HTTP protocol path against controlled local test servers. That proves transport shape, lifecycle behavior, provenance, and secret handling; it is **not yet the same thing as an exact-head live-provider release acceptance run**. The repository does not claim that final gate prematurely.

---

## Why CAPT exists

Most AI applications still make the model session responsible for too much:

- remembering what happened;
- reconstructing context;
- deciding what evidence matters;
- keeping execution state;
- determining whether a tool action is authorized;
- evaluating its own output;
- recovering after restart;
- deciding whether work is complete.

Those are poor places to rely on a probabilistic, context-bounded inference component.

CAPT externalizes them:

| Responsibility | CAPT owner |
|---|---|
| Persistent local knowledge | CAPT Solo Memory Engine |
| Authoritative runtime history | EventStore |
| Runtime transitions | RuntimeService |
| Operational transaction/recovery journal | CTP |
| Context budgeting / rotation | Runtime Memory Governor + ContextPack |
| In-process coordination | KHSB |
| Capability and lease enforcement | Runtime governance |
| External execution | bounded Drivers / DriverHost |
| Evidence | evidence subsystem |
| Verification | verification subsystem |
| Claim support discipline | ClaimGuard |
| Presentation and operator controls | `capt`, `capt-ui`, desktop clients |
| Final authority | human operator / explicitly authorized runtime policy |

This makes a model replaceable without making the mission, memory, evidence trail, or runtime identity disposable.

---

## Architecture at a glance

```text
                    Human / Application / Agent Host
                               |
             +-----------------+------------------+
             |                                    |
          capt CLI                           capt-ui / desktop
             |                                    |
             +---------- shared Operator ---------+
                               |
                     authenticated local IPC
                               |
                        RuntimeService
                               |
       +-----------------------+-----------------------+
       |                       |                       |
   EventStore              Governance              Memory
 authoritative          grants / leases /       Memory Engine
 event history          approvals / policy      + ContextPack
       |                       |                       |
       +--------------- governed execution ------------+
                               |
                           DriverHost
                               |
              +----------------+----------------+
              |                                 |
          Hermes driver                 ProviderDriver*
                                              |
                                  Ollama / compatible API

* ProviderDriver is currently in the active integration lineage, not merged
  release behavior on main.
```

### Authority boundaries

Several distinctions are architectural, not cosmetic:

- **EventStore** owns authoritative runtime event history.
- **CTP** is an operational transaction/recovery journal, not a replacement ledger.
- **KHSB** is currently in-process and non-durable.
- **CAPT Solo Memory Engine** and **Runtime Memory Governor** are separate subsystems.
- **Evidence is not verification.**
- **Verification is not claim acceptance.**
- **Claim acceptance is not task completion.**
- **Task completion is not mission completion.**
- A driver result is untrusted until admitted through CAPT boundaries.
- A UI action is a request to the runtime, not authority owned by the UI.
- A provider being registered or discoverable does not prove governed provider execution.
- A synthetic continuity demo does not prove real Model-A → restart → Model-B continuity.

---

## Provider and model status

The merged provider layer deliberately separates **registration**, **discovery**, **health**, **model listing**, and **execution proof**.

Current `main` foundation includes configuration/support paths for:

- OpenRouter;
- Ollama;
- LM Studio;
- vLLM;
- llama.cpp-compatible servers;
- MLX / `mlx_lm` registration foundation;
- Hermes compatibility.

On merged `main`, several HTTP-based providers support health/model-list operations, while MLX remains registered-only and the full real-provider governed-execution/cross-model release gate remains open.

The active integration lineage advances this with the bounded ProviderDriver described above. Until exact-head live-provider acceptance is recorded, the README keeps **implemented transport** and **release-proven provider execution** as different claims.

See [`docs/PROVIDERS.md`](docs/PROVIDERS.md), [`docs/FUNCTIONALITY_MATRIX.md`](docs/FUNCTIONALITY_MATRIX.md), and [`capt_ui/ACCEPTANCE_STATUS.md`](capt_ui/ACCEPTANCE_STATUS.md).

---

## Cohorts and multi-perspective cognition

PR #48 introduces the first bounded CAPT-native Cohort coordination slice.

It currently defines and verifies:

- typed contribution outcomes;
- bounded participant rosters;
- deliberation epochs;
- stale-result admission rules;
- participant cursors over authoritative global sequence;
- round-local Silence Quorum;
- required-participant positive quorum;
- material dissent/escalation from any admitted participant;
- cognitive-debt and escalation projection;
- duplicate/future-round rejection;
- final-round quorum versus bounded-incomplete discrimination.

It does **not** yet claim durable Cohort persistence/reconstruction, restart-safe participant cursors, the evidence-admission bridge, governed participant scheduling, or installed-runtime/TUI Cohort dogfooding. Cohorts remain coordination over CAPT authority, not a parallel runtime.

---

## Discovery and governed execution hardening

The active v0.7-era integration stack also includes:

### Discovery Governor / SEAL — PR #44

A bounded, read-only local scanner and discovery policy that can inspect source presence without granting itself capability or mutating authoritative runtime state.

### Ouroboros lifecycle reconciliation — PR #46

Hardens long-running governed execution around:

- durable command idempotency;
- dispatch-boundary accounting;
- consumed capability leases;
- lost/indeterminate execution recovery;
- suspension instead of unsafe redispatch;
- truthful projection of verification state;
- governed cancellation paths.

The central rule is conservative: **when CAPT cannot prove whether external dispatch occurred, it does not silently replay the work.**

---

## Security posture

CAPT is local-first, but local-first does not automatically mean high-assurance.

Merged/current boundaries include:

- authenticated local socket/token access;
- single trusted local OS-user threat model;
- secret references rather than raw provider tokens in UI provider configuration;
- secret scrubbing from provider diagnostics/evidence paths;
- integrity checks and fail-closed behavior in multiple runtime paths;
- imported Knowledge Bubble validation/quarantine boundaries.

Current limitations include:

- persistent runtime/memory state is not yet comprehensively encrypted at rest by CAPT itself;
- the system is not currently a multi-tenant authorization platform;
- audit integrity is not yet backed by independently trusted signed checkpoint roots;
- production IPC bounded-frame migration is part of the active security closure work;
- complete provider token/cost/request/output ceilings remain security-hardening work;
- adversarial prompt/context/provider injection assurance is not yet a complete release gate.

PR #49 turns the pre-launch security checklist into executable fail-closed infrastructure. It is intentionally **BLOCKED**, not cosmetically green, until each applicable control has exact-head evidence.

Read [`docs/SECURITY.md`](docs/SECURITY.md) before placing sensitive material or higher-trust workloads into CAPT.

---

## Repository layout

```text
START_HERE.md       canonical first-success walkthrough
capt_cli.py         normal + expert `capt` CLI
capt_solo/          local API, memory, CTP, KHSB, proof-governed services
capt_runtime/       authoritative runtime, EventStore, governance, drivers
capt_ui/            shared operator layer, TUI, desktop/operator surfaces
contracts/          canonical schemas + generated bindings
desktop/            runtime IPC service and desktop integration code
docs/               user docs, architecture, security, design, release state
release_evidence/   versioned proof/evidence records
tests/              runtime, UI, contract, integration, adversarial tests
```

---

## Documentation map

| I want to... | Read this |
|---|---|
| Get CAPT running | [`START_HERE.md`](START_HERE.md) |
| Install the current operator surfaces | [`docs/INSTALLATION.md`](docs/INSTALLATION.md) |
| Understand CAPT in one screen | [`docs/MENTAL_MODEL.md`](docs/MENTAL_MODEL.md) |
| Use the TUI | [`docs/TUI.md`](docs/TUI.md) |
| See exactly what is shipped/proven/gated | [`docs/FUNCTIONALITY_MATRIX.md`](docs/FUNCTIONALITY_MATRIX.md) |
| Configure providers | [`docs/PROVIDERS.md`](docs/PROVIDERS.md) |
| Inspect UI acceptance boundaries | [`capt_ui/ACCEPTANCE_STATUS.md`](capt_ui/ACCEPTANCE_STATUS.md) |
| Run realistic workflows | [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) |
| Run demos | [`docs/DEMOS.md`](docs/DEMOS.md) |
| Troubleshoot | [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) |
| Understand architecture deeply | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Review the whitepaper | [`docs/WHITEPAPER.md`](docs/WHITEPAPER.md) |
| Review security boundaries | [`docs/SECURITY.md`](docs/SECURITY.md) |
| Integrate in Python | [`docs/API.md`](docs/API.md) |
| Inspect release proof | [`docs/RELEASE_EVIDENCE.md`](docs/RELEASE_EVIDENCE.md) |
| See productization source-of-truth | [`docs/V0_6_PRODUCTIZATION_SOURCE_OF_TRUTH.md`](docs/V0_6_PRODUCTIZATION_SOURCE_OF_TRUTH.md) |

---

## Naming

- **CAPT Core** — the architecture and canonical project.
- **CAPT Solo** — the local-first reference implementation/API package.
- **CAPT Runtime Harness** — governed lifecycle and execution service.
- **CAPT Operator layer** — shared projection/control facade consumed by CLI/TUI/desktop.
- **CaveCAPT** — shared presentation verbosity modes; never a governance bypass.
- **Hermes compatibility** — an external execution/client integration; Hermes does not become CAPT authority.
- **Cohort** — bounded multi-perspective coordination over CAPT state; not an alternate runtime.

---

## Release semantics

CAPT intentionally uses stricter language than “the code exists.”

A useful progression is:

```text
implemented
    -> locally tested
    -> integrated
    -> exact-head verified
    -> installed-runtime verified
    -> live external dependency/provider verified (when applicable)
    -> release-proven
```

The current repository contains work at several of those stages simultaneously. This README calls out the stage instead of collapsing them into one green checkbox.

---

## Support CAPT

CAPT Core is independently developed open-source infrastructure.

- Solana: `7kgPboqCUY9vUaTSFs1opvfEv86UD1e31ckAPHqgdQuV`
- Bitcoin: `bc1q82dsstmrh9qzpp8gsa8hwzr8t5caj6n0w2w94j`
- Ethereum / EVM: `0xB4E04b51191fB52C5Bae5C2dC4D6457a431d6825`

Verify destination addresses before sending. Cryptocurrency transfers are generally irreversible.

## License

CAPT Core is available under the MIT License. See [`LICENSE`](LICENSE).
