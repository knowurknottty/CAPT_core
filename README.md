# CAPT Core

**Local-first governed runtime and continuity substrate for AI agents.**

> **The model becomes stateless. CAPT becomes stateful.**

A model is a transient, replaceable inference component. CAPT owns the durable
memory, governed state, evidence, authority, execution history, context policy,
and recovery around it. This is the one identity CAPT has: a local-first
governed runtime and continuity substrate for AI agents.

## Start here

**New to CAPT? Read [`START_HERE.md`](START_HERE.md) and follow it — it is the
only walkthrough you need.** It takes about five minutes: install, verify,
store memory, start the runtime, inspect evidence, checkpoint, stop, restart,
resume.

For the mental model, see [`docs/MENTAL_MODEL.md`](docs/MENTAL_MODEL.md) — the
whole system fits on one screen.

## Quick start

```zsh
git clone https://github.com/knowurknottty/CAPT_core.git capt-core
cd capt-core
./install.sh
./verify.sh
```

Then confirm the CLI:

```zsh
capt --version
```

Start the governed runtime with defaults and use it:

```zsh
capt start        # starts the runtime with a default state dir (~/.capt)
capt status       # runtime health and version
capt evidence     # human-readable proof / verification view
capt checkpoint   # save authoritative state
capt resume       # resume after restart
capt stop         # stop the runtime
```

Durable memory, no model required:

```zsh
capt memory store "CAPT keeps durable state outside the model."
capt memory search "durable"
```

`capt start/status/stop/checkpoint/resume` are the recommended normal-human
entry points. The full expert surface remains available as
`capt harness start/health/capabilities/stop` for advanced and debug use.

Diagnose the environment any time:

```zsh
capt doctor
```

## What is proven in v0.5

CAPT Core v0.5 is release-proven for local evaluation and development within the documented boundaries.

The current release includes:

- a local SQLite-backed Memory Engine exposed through `capt_solo.api`;
- an authoritative EventStore for ordered runtime events and replay;
- CTP operational transaction and recovery journals;
- an internal Memory Governor and bounded ContextPack rotation policy;
- KHSB in-process coordination;
- proof, capability lifecycle, ClaimGuard, Skill Foundry, workflow-proof, and Knowledge Bubble subsystems;
- an authenticated local harness service with checkpoint, restart, idempotency, and bounded driver execution;
- installed-wheel, local real-process, and hosted-CI evidence under [`release_evidence/v0.5`](release_evidence/v0.5).

The currently proven Hermes-facing action is **bounded read-only inspection**. General unrestricted model-driven repository engineering is not claimed.

## Quick start

```zsh
git clone https://github.com/knowurknottty/CAPT_core.git capt-core
cd capt-core
./install.sh
./verify.sh
```

For deeper diagnostics:

```zsh
./doctor.sh
python3 verify_runtime.py
python3 -m pytest tests/ -q
```

After installation, inspect the standalone harness:

```zsh
capt harness start
capt harness health
capt harness capabilities
capt harness stop
```

Use `capt harness command --help` to inspect the governed command surface available in the installed version.

## Why CAPT exists

Most AI systems attach memory, tool state, and execution history to a temporary model session. That makes continuity fragile and makes it difficult to distinguish a convincing answer from a verified system state.

CAPT moves durable responsibility outside the model:

| Concern | CAPT owner |
|---|---|
| Persistent local knowledge | CAPT Solo Memory Engine |
| Authoritative runtime event history | EventStore |
| Operational transaction and recovery journal | CTP |
| Context budgeting and rotation | Runtime Memory Governor |
| In-process coordination | KHSB |
| Evidence and verification state | Proof and verification subsystems |
| Claim discipline | ClaimGuard |
| Consequential runtime execution | CAPT Runtime Harness |
| Final authority | Human operator |

This makes models replaceable inference components rather than the system of record.

## Two supported public surfaces

CAPT has two integration paths. For normal users, the `capt` CLI is the primary
surface. For developers, the `capt_solo.api` Python API and the `capt harness`
expert CLI are the integration surfaces.

### `capt` CLI (recommended, v0.6)

`capt start/status/stop/checkpoint/resume/evidence/doctor` plus
`capt memory ...` are the normal-human surface. See
[`START_HERE.md`](START_HERE.md) and [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).

### CAPT Solo API

Use `capt_solo.api` for supported in-process integrations such as memory, CTP, KHSB, and proof-governed domain services.

```python
from capt_solo.api import MemoryEngine

memory = MemoryEngine()
memory.store(
    "CAPT keeps durable state outside the model.",
    namespace="project",
    provenance="user",
)
```

### CAPT Runtime Harness (expert)

Use the installed `capt harness` CLI for governed runtime lifecycle and bounded execution at the full detail level (explicit socket/token/ledger paths). The harness owns authenticated service access, command dispatch, checkpointing, restart continuity, idempotency, EventStore persistence, and driver boundaries.

`capt start/status/stop` are thin convenience wrappers over this harness that
allocate default local state. Authority remains in RuntimeService.

Hermes and other external callers are compatibility clients. They do not become
the CAPT runtime.

## Architecture at a glance

```text
Application or local caller
        |
        +--> capt_solo.api
        |       +--> Memory Engine
        |       +--> CTP
        |       +--> KHSB
        |       +--> Foundry / Proof / ClaimGuard
        |
        +--> capt harness CLI
                +--> authenticated RuntimeService
                +--> EventStore
                +--> Memory Governor / ContextPack
                +--> DriverHost
                +--> checkpoint and recovery
                +--> bounded external drivers
```

### Authority boundaries

- **EventStore** owns the authoritative ordered runtime event ledger.
- **CTP** records operational transactions, receipts, and recovery state; it is not the authoritative runtime ledger.
- **KHSB** is in-process only; it is not durable or cross-process.
- **CAPT Solo Memory Engine** and the **Runtime Memory Governor** are separate subsystems.
- Packaging or importability does not automatically make a subsystem operator-facing.
- Local external-model evidence is distinct from deterministic hosted-CI evidence.

## Security posture

The base runtime requires no cloud service, external database, Docker deployment, or provider credential. Optional external model drivers may require their own credentials and network access.

Current boundaries:

- local persistent state is plaintext unless protected by host or filesystem encryption;
- the runtime assumes one trusted local operating-system user;
- it is not a multi-user authorization service;
- audit records are not yet cryptographically signed;
- imported Knowledge Bubbles are quarantined and validated before approval;
- unsafe migrations and failed integrity checks stop rather than silently proceeding;
- hosted security CI reports `DEGRADED_OPTIONAL_DEPENDENCY` when the private optional anti-token-extraction dependency cannot be verified.

Read [Security Boundaries](docs/SECURITY.md) before storing sensitive data or integrating CAPT into a higher-trust environment.

## Repository layout

```text
START_HERE.md     **start here** — the only walkthrough you need
capt_cli.py       the `capt` command-line interface (normal + expert surface)
capt_solo/        CAPT Solo API, memory, CTP, KHSB, and proof-governed services
capt_runtime/     standalone governed runtime, EventStore, memory policy, drivers
contracts/        canonical schemas and generated language bindings
desktop/          local runtime service and desktop client surfaces
docs/             user guide, mental model, matrix, demos, troubleshooting, architecture
release_evidence/ versioned manifests, matrices, and release proof records
tests/            automated test suite
```

Find things by task, not by title:

| I want to... | Read this |
|---|---|
| Do the five-minute walkthrough | [`START_HERE.md`](START_HERE.md) |
| Understand the whole system in one screen | [`docs/MENTAL_MODEL.md`](docs/MENTAL_MODEL.md) |
| Run realistic workflows | [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) |
| Run demos | [`docs/DEMOS.md`](docs/DEMOS.md) |
| Know what actually exists | [`docs/CAPABILITY_MATRIX.md`](docs/CAPABILITY_MATRIX.md) |
| Fix a problem | [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) |
| Add/use a model | [`docs/MODEL_PROVIDERS.md`](docs/MODEL_PROVIDERS.md) |
| Inspect the proof | [`docs/RELEASE_EVIDENCE.md`](docs/RELEASE_EVIDENCE.md) |
| Deep architecture | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (after first success) |
| Integrate in Python | [`docs/API.md`](docs/API.md) |

## Documentation

User path (start here):

- [Start Here](START_HERE.md)
- [Mental Model](docs/MENTAL_MODEL.md)
- [User Guide](docs/USER_GUIDE.md)
- [Demos](docs/DEMOS.md)
- [Capability Matrix](docs/CAPABILITY_MATRIX.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Model Providers](docs/MODEL_PROVIDERS.md)

Deep path (after first success):

- [Whitepaper](docs/WHITEPAPER.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Design rationale](docs/DESIGN.md)
- [Security boundaries](docs/SECURITY.md)
- [API reference](docs/API.md)
- [Runtime and integration guide](docs/PLUGIN_GUIDE.md)
- [Roadmap](docs/ROADMAP.md)
- [v0.6 source of truth](docs/V0_6_PRODUCTIZATION_SOURCE_OF_TRUTH.md)
- [Release evidence](docs/RELEASE_EVIDENCE.md)

## Naming

- **CAPT Core** — the architecture and project.
- **CAPT Solo** — the local-first reference implementation and supported API package.
- **CAPT Runtime Harness** — the governed lifecycle and execution service shipped with CAPT Solo.
- **Hermes compatibility skill** — an external client integration, archived separately from the canonical runtime.

## Current limitations and next work

The main non-blocking follow-up work is:

- modernizing packaging license metadata;
- restoring a meaningful scoped coverage policy;
- deciding whether selected adversarial OpenHarness tests should be ported to the canonical driver implementation;
- rewriting and independently validating the external Hermes compatibility skill against the v0.5 harness;
- adding stronger cryptographic and multi-user controls only as separately implemented and proven features.

## Support CAPT

CAPT Core is independently developed open-source infrastructure.

- Solana: `7kgPboqCUY9vUaTSFs1opvfEv86UD1e31ckAPHqgdQuV`
- Bitcoin: `bc1q82dsstmrh9qzpp8gsa8hwzr8t5caj6n0w2w94j`
- Ethereum / EVM: `0xB4E04b51191fB52C5Bae5C2dC4D6457a431d6825`

Verify destination addresses before sending. Cryptocurrency contributions are generally irreversible.

## License

CAPT Core is available under the MIT License. See [LICENSE](LICENSE).
