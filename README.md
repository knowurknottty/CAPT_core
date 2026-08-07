# CAPT Core

**Local-first, verifiable cognitive infrastructure for AI agents.**

CAPT Core keeps durable memory, governed state, execution receipts, and human authority outside any single model or vendor. The reference runtime, **CAPT Solo**, runs locally and remains inspectable, self-hostable, and model-agnostic.

## Quick start

Clone the repository, install the local runtime, and run the verification harness:

```bash
git clone https://github.com/knowurknottty/CAPT_core.git capt-core
cd capt-core
./install.sh
./verify.sh
```

For deeper diagnostics:

```bash
./doctor.sh
python verify_runtime.py
python -m pytest tests/ -q
```

## Why this matters

Most AI systems bind memory, state, governance, and execution history to a particular model session or vendor runtime. CAPT Core separates **persistent cognition from transient inference**.

That changes the role of the model. Instead of making a model the system of record, CAPT treats it as a replaceable reasoning component inside a larger governed architecture. Models, providers, and runtimes can change without taking durable memory, provenance, recovery state, policy, or human authority with them.

The practical consequences are straightforward:

- **Less vendor lock-in** — durable state remains outside the inference provider.
- **Less context-window waste** — persistent knowledge does not need to be repeatedly reconstructed inside prompts.
- **More inspectable execution** — consequential actions are bounded by transactions and preserved as receipts.
- **Stronger claim discipline** — unsupported completion claims are downgraded instead of accepted at face value.
- **Local control** — the base runtime requires no cloud service, API keys, external database, or Docker deployment.
- **Model portability** — expensive frontier models and smaller local models can operate behind the same stable boundary.

CAPT Core is not an attempt to make inference irrelevant. It is an attempt to put inference in the correct architectural position: powerful, useful, replaceable, and subject to evidence-backed governance.

## Why CAPT Core exists

| Common AI system | CAPT Core |
|---|---|
| Memory and state live inside one model session. | Durable memory and governed state live outside the model. |
| Outputs are accepted because a model says they are complete. | ClaimGuard downgrades unsupported claims and preserves uncertainty. |
| Execution history is difficult to inspect or replay. | EventStore preserves the authoritative immutable event ledger; CTP records operational transaction receipts and recovery state. |
| Switching models or vendors risks losing system continuity. | Models are replaceable components behind a stable local boundary. |

## Three things CAPT Core provides

### 1. Memory and context

CAPT Solo stores persistent knowledge locally with namespaces, tags, provenance, confidence, metadata, export/import, backups, and integrity checks.

### 2. Security and governance

Consequential actions are attributed to named actors, bounded by transactions, and recorded in append-only audit history. Unsafe migrations and validation failures stop rather than silently proceeding.

### 3. Verification and receipts

The runtime produces evidence, receipts, lifecycle records, and replayable transaction journals. Capabilities, skills, and workflows are not reported verified without sufficient evidence.

## Architecture at a glance

```text
Hermes or local caller
        |
        v
capt_solo.api                  stable public boundary
        |
        +--> Memory Engine     persistent local knowledge
        +--> CTP Runtime       operational transactions and recovery receipts
        +--> KHSB              in-process coordination
        +--> Foundry           proof, ClaimGuard, skills, bubbles
        +--> Governance        audited consequential actions

CAPT Runtime
        |
        +--> EventStore        authoritative immutable event ledger
        +--> Memory Governor   governed ContextPack and trigger policy
        +--> DriverHost        bounded external model/runtime execution
```

The supported CAPT Solo integration surface is `capt_solo.api`. Internal modules may evolve without forcing callers to depend on unstable paths. The standalone harness exposes a separate governed command surface through the installed `capt` CLI.

## What is included today

- **Memory Engine** — local SQLite storage with provenance, confidence, metadata, backups, import/export, and integrity checks; available through the CAPT Solo API and memory CLI surfaces.
- **Runtime Memory Governor** — internal runtime trigger policy, token accounting, ContextPack rotation, and dispatch gating.
- **EventStore** — authoritative immutable runtime event ledger with ordered persistence and replay support.
- **CTP Runtime** — operational transaction journals with receipts, idempotency, correlation IDs, and recovery support; it does not replace EventStore ledger authority.
- **KHSB** — in-process publish/subscribe and request/reply messaging; not a durable or cross-process bus.
- **Skill Foundry** — explicit validation, review, approval, publication, deprecation, and revocation states.
- **Proof Engine** — evidence objects and requirement-based aggregation.
- **Capability Registry** — candidate, validated, proven, verified, degraded, deprecated, revoked, and experimental states.
- **ClaimGuard** — prevents unsupported completion claims and applies scoped degradation language.
- **Knowledge Bubble Runtime** — portable governed packages with quarantine-first import and manifest-before-payload validation.
- **Workflow Proof Engine** — composed workflows carry independent proof rather than inheriting trust from their components.
- **Governance Layer** — consequential actions are transaction-bounded, attributed, and recorded.
- **Standalone Harness** — authenticated local service, governed command dispatch, checkpoint/restart continuity, and bounded external drivers.
- **Verification Tooling** — installer, diagnostics, health checks, runtime validation, automated tests, and release evidence manifests.

The currently proven Hermes operator action is bounded read-only inspection. General unrestricted model-driven repository engineering is not claimed.

## Security posture

The base runtime requires no API keys and performs no required network egress. State is stored locally in SQLite files and local journals.

Important boundaries:

- local plaintext storage is **not** encryption at rest
- the current runtime is **not** a multi-user authorization service
- append-only audit history is **not yet cryptographically signed**
- imported Knowledge Bubbles are quarantined and validated before approval
- migrations are backup-gated and abort on failed integrity checks
- unsafe command patterns, secret patterns, and disallowed permissions block skill validation
- optional external model drivers may require their own provider credentials and network access

Read [docs/SECURITY.md](docs/SECURITY.md) before storing sensitive data or integrating CAPT Core into a higher-trust environment.

## Design principles

- Local-first
- Self-hostable
- Model and vendor independent
- No required cloud service
- No required external database
- No Docker requirement
- Deterministic and recoverable execution
- Evidence before verification
- Explicit authority and lifecycle boundaries
- Human-readable portable state
- Backward-compatible migrations

## Repository layout

```text
capt_solo/         CAPT Solo API, memory, foundry, KHSB, and CTP implementation
capt_runtime/      standalone governed runtime and model-driver boundary
contracts/         canonical schemas and generated language bindings
desktop/           local runtime service and desktop client surfaces
docs/              architecture, security, API, data model, migrations, guides
release_evidence/  versioned release manifests, matrices, and proof records
tests/             automated test suite
install.sh          local installer
doctor.sh           environment diagnostics
verify.sh           one-command health check
verify_runtime.py   structured runtime verification harness
```

## Deep-dive documentation

- [Whitepaper](docs/WHITEPAPER.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Design Rationale](docs/DESIGN.md)
- [Security Boundaries](docs/SECURITY.md)
- [Data Model](docs/DATA_MODEL.md)
- [API](docs/API.md)
- [Migrations](docs/MIGRATIONS.md)
- [Plugin Guide](docs/PLUGIN_GUIDE.md)
- [Skill Guide](docs/SKILL_GUIDE.md)
- [Extending CAPT](docs/EXTENDING.md)
- [Roadmap](docs/ROADMAP.md)
- [v0.5 Release Evidence](release_evidence/v0.5/release-readiness.md)

## Naming

- **CAPT Core** is the cognitive infrastructure architecture.
- **CAPT Solo** is the local-first reference implementation in this repository.
- **CAPT Runtime / standalone harness** is the governed execution and lifecycle service packaged with CAPT Solo.

The implementation package retains the `capt_solo` namespace for compatibility.

## Project status

CAPT Core v0.5 is release-proven for local evaluation and development through the evidence-bounded surfaces documented in [release_evidence/v0.5](release_evidence/v0.5). Consumers should review the stated limitations and verify the runtime in their own environment before higher-trust use.

## Support CAPT

CAPT Core and CAPT Solo are being developed independently and released as open-source infrastructure. GitHub Sponsors will be enabled soon. Direct contributions are also welcome:

- Solana: `7kgPboqCUY9vUaTSFs1opvfEv86UD1e31ckAPHqgdQuV`
- Bitcoin: `bc1q82dsstmrh9qzpp8gsa8hwzr8t5caj6n0w2w94j`
- Ethereum / EVM: `0xB4E04b51191fB52C5Bae5C2dC4D6457a431d6825`

Please verify the destination address before sending. Cryptocurrency contributions are generally irreversible.

## License

Open source under the MIT License. See [LICENSE](LICENSE) for the exact terms.
