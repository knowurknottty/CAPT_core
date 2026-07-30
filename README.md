# CAPT Core

**Secure, auditable, model-agnostic cognitive infrastructure.**

CAPT Core separates persistent cognition from transient inference. Models, vendors,
and runtimes can change without taking memory, governance, provenance, recovery,
or human authority with them.

This repository contains **CAPT Solo**, the local-first reference implementation of
CAPT Core for individual developers. It integrates with Hermes while keeping the
runtime self-hostable and inspectable.

## Why CAPT Core exists

Most AI products are built around a model. CAPT Core treats the model as one
replaceable component inside a larger governed system.

The durable parts of the system are kept outside the model:

- persistent memory
- context and state management
- transactional execution
- capability lifecycles
- evidence and proof
- claim verification
- tool governance
- recovery and audit history
- human authority and revocation

## Current public release

The public runtime currently includes the v0.4 proof-governed architecture plus
v0.4.1 hardening work.

Core capabilities include:

- **Memory Engine** — local SQLite storage with namespaces, tags, provenance,
  confidence, metadata, export/import, backups, and an adapter seam for semantic
  search.
- **CTP Runtime** — append-only transaction journals with receipts, idempotency,
  correlation IDs, audit history, and crash recovery.
- **KHSB** — in-process publish/subscribe and request/reply messaging with timeout
  and acknowledgement behavior.
- **Skill Foundry** — procedure-to-skill lifecycle with a 12-stage validation
  harness, review, approval, publication, deprecation, and revocation states.
- **Proof Engine** — evidence objects and requirement-based aggregation. A
  capability is not reported verified without sufficient proof.
- **Capability Registry** — explicit candidate, validated, proven, verified,
  degraded, deprecated, revoked, and experimental states.
- **ClaimGuard** — prevents unsupported completion claims and applies scoped
  degradation language.
- **Knowledge Bubble Runtime** — portable governed packages with quarantine-first
  import and manifest-before-payload validation.
- **Workflow Proof Engine** — composed workflows carry independent proof rather
  than inheriting trust from their components.
- **Governance Layer** — consequential actions are CTP-bounded, attributed to a
  named actor, and recorded in an append-only audit trail.
- **Hermes Integration** — stable public tools and beginner-friendly skills.
- **Verification Tooling** — installer, diagnostics, health checks, runtime
  validation, and automated tests.

## Architecture at a glance

```text
Hermes or local caller
        |
        v
capt_solo.api                  stable public boundary
        |
        +--> Memory Engine     persistent local knowledge
        +--> CTP Runtime       deterministic transactions and recovery
        +--> KHSB              in-process coordination
        +--> Foundry           proof, registry, ClaimGuard, skills, bubbles
        +--> Governance        audited consequential actions
```

The sanctioned integration surface is `capt_solo.api`. Internal implementations
may evolve without forcing callers to depend on unstable module paths.

## Design principles

- Local-first
- Self-hostable
- Model and vendor independent
- No required cloud service
- No required external database
- No Docker requirement
- Deterministic and recoverable execution
- Human-readable portable state
- Evidence before verification
- Explicit authority and lifecycle boundaries
- Backward-compatible migrations

## Security posture

The base runtime requires no API keys and performs no network egress. State is
stored locally in SQLite and append-only CTP journals.

Important boundaries:

- local plaintext storage is **not** encryption at rest
- the current single-user runtime is **not** a multi-user authorization system
- append-only audit history is **not yet cryptographically signed**
- imported Knowledge Bubbles are quarantined and validated before approval
- migrations are backup-gated and abort on failed integrity checks
- unsafe command patterns, secret patterns, and disallowed permissions block skill
  validation

Read [docs/SECURITY.md](docs/SECURITY.md) before storing sensitive data or
integrating CAPT Core into a higher-trust environment.

## Quick start

```bash
git clone https://github.com/knowurknottty/CAPT_core.git capt-core
cd capt-core
./install.sh
./verify.sh
```

Additional diagnostics:

```bash
./doctor.sh
python verify_runtime.py
```

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

## Documentation

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
- **CAPT Solo** is the local-first reference implementation contained in this
  repository.

The implementation package retains the `capt_solo` namespace for compatibility.

## Project status

CAPT Core is under active public-release hardening. The repository is usable for
local evaluation and development, but consumers should review the documented
security limitations and verify the runtime in their own environment.

## License

Open source. See [LICENSE](LICENSE) for the exact terms.
