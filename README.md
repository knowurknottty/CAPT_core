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
| Execution history is difficult to inspect or replay. | CTP journals record append-only transactions, receipts, and recovery state. |
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
        +--> CTP Runtime       transactions, receipts, recovery
        +--> KHSB              in-process coordination
        +--> Foundry           proof, ClaimGuard, skills, bubbles
        +--> Governance        audited consequential actions
```

The supported integration surface is `capt_solo.api`. Internal modules may evolve without forcing callers to depend on unstable paths.

## What is included today

- **Memory Engine** — local SQLite storage with provenance, confidence, metadata, backups, import/export, and integrity checks.
- **CTP Runtime** — append-only journals with receipts, idempotency, correlation IDs, audit history, and crash recovery.
- **KHSB** — in-process publish/subscribe and request/reply messaging.
- **Skill Foundry** — explicit validation, review, approval, publication, deprecation, and revocation states.
- **Proof Engine** — evidence objects and requirement-based aggregation.
- **Capability Registry** — candidate, validated, proven, verified, degraded, deprecated, revoked, and experimental states.
- **ClaimGuard** — prevents unsupported completion claims and applies scoped degradation language.
- **Knowledge Bubble Runtime** — portable governed packages with quarantine-first import and manifest-before-payload validation.
- **Workflow Proof Engine** — composed workflows carry independent proof rather than inheriting trust from their components.
- **Governance Layer** — consequential actions are transaction-bounded, attributed, and recorded.
- **Verification Tooling** — installer, diagnostics, health checks, runtime validation, and automated tests.

## Security posture

The base runtime requires no API keys and performs no required network egress. State is stored locally in SQLite files and append-only CTP journals.

Important boundaries:

- local plaintext storage is **not** encryption at rest
- the current runtime is **not** a multi-user authorization service
- append-only audit history is **not yet cryptographically signed**
- imported Knowledge Bubbles are quarantined and validated before approval
- migrations are backup-gated and abort on failed integrity checks
- unsafe command patterns, secret patterns, and disallowed permissions block skill validation

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
capt_solo/         runtime implementation
architecture/      architecture contracts and validation assets
skills/            shipped skill definitions
mcp_servers/       local MCP integrations
schemas/           machine-readable schemas
scripts/           release and validation utilities
docs/              architecture, security, API, data model, migrations, guides
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

## Naming

- **CAPT Core** is the cognitive infrastructure architecture.
- **CAPT Solo** is the local-first reference implementation in this repository.

The implementation package retains the `capt_solo` namespace for compatibility.

## Project status

CAPT Core is under active public-release hardening. The repository is suitable for local evaluation and development, but consumers should review the documented limitations and verify the runtime in their own environment.

## Support CAPT

CAPT Core and CAPT Solo are being developed independently and released as open-source infrastructure. GitHub Sponsors will be enabled soon. Direct contributions are also welcome:

- Solana: `7kgPboqCUY9vUaTSFs1opvfEv86UD1e31ckAPHqgdQuV`
- Bitcoin: `bc1q82dsstmrh9qzpp8gsa8hwzr8t5caj6n0w2w94j`
- Ethereum / EVM: `0xB4E04b51191fB52C5Bae5C2dC4D6457a431d6825`

Please verify the destination address before sending. Cryptocurrency contributions are generally irreversible.

## License

Open source. See [LICENSE](LICENSE) for the exact terms.
