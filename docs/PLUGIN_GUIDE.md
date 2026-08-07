# CAPT Runtime and Integration Guide

CAPT Core supports two integration paths:

- `capt_solo.api` for in-process CAPT Solo features;
- `capt harness` for governed runtime lifecycle and bounded execution.

Hermes is an external compatibility client. It is not the CAPT runtime and does not own CAPT authority.

## Start with the installed harness

```zsh
capt harness start
capt harness health
capt harness capabilities
capt harness command --help
capt harness stop
```

Use the installed help output as the authority for exact command names and arguments.

## What the harness provides

The standalone harness owns:

- authenticated local RuntimeService access;
- command classification and idempotency;
- EventStore persistence and replay;
- Runtime Memory Governor policy;
- ContextPack construction and rotation;
- TaskResolver and DriverHost;
- checkpoint and restart continuity;
- evidence and VerificationResult persistence;
- ClaimGuard decisions;
- bounded external-driver execution.

## Hermes boundary

The proven Hermes-facing path is:

```text
Hermes -> bounded compatibility layer -> installed capt harness -> CAPT-owned runtime
```

The compatibility layer must not:

- reconstruct CAPT in prompts;
- claim that Hermes owns memory, policy, ledger, or lifecycle authority;
- bypass RuntimeService or DriverHost;
- expose raw internal state as a public contract;
- represent prompt discipline as runtime enforcement;
- claim general repository engineering when only bounded inspection is proven.

The historical Hermes skill has been archived outside CAPT Core because it targets older `capt agent` and plugin commands. It must be rewritten and independently proven against the v0.5 harness before being called release-ready.

## Current Hermes proof

The preserved v0.5 evidence demonstrates a local installed-wheel lifecycle using a real Hermes process, including authenticated service access, mission/task/session creation, bounded driver execution, verification persistence, ClaimGuard decision, checkpointing, restart, idempotent duplicate handling, and no-repeat resume.

Limitations:

- hosted CI does not rerun the external Hermes/provider lifecycle;
- one run encountered a provider HTTP 429 condition;
- the proven operator action is bounded read-only inspection;
- unrestricted model-driven repository mutation is not proven.

## CAPT Solo API integrations

Applications that need memory, CTP, KHSB, or proof-governed domain services should import `capt_solo.api` directly.

```python
from capt_solo.api import MemoryEngine

engine = MemoryEngine()
engine.store(
    "A durable project decision.",
    namespace="project",
    provenance="operator",
)
```

This API path is separate from harness execution.

## Security boundaries

- Do not pass provider secrets through CAPT command payloads unless the specific driver contract requires and protects them.
- Do not log authorization headers or credentials.
- Treat external model output as untrusted until verified.
- Keep the runtime directory restricted to the trusted local account.
- Do not store unnecessary secrets in CAPT memory.
- Distinguish local external-process proof from hosted-CI proof.
- Surface degraded optional dependencies explicitly.

## Building a new compatibility client

A new client should:

1. depend only on installed public surfaces;
2. resolve the exact CAPT version and capabilities;
3. authenticate through the supported local service boundary;
4. request only declared capabilities;
5. preserve CAPT-generated identifiers and receipts;
6. avoid direct database or internal-module mutation;
7. test duplicate commands, restart, stale context, and authorization failure;
8. preserve limitations in user-facing output.

## Verification

Run:

```zsh
./verify.sh
./doctor.sh
python3 verify_runtime.py
python3 -m pytest tests/ -q
```

For release evidence, see [`release_evidence/v0.5`](../release_evidence/v0.5).

## Related documentation

- [Project overview](../README.md)
- [Architecture](ARCHITECTURE.md)
- [API reference](API.md)
- [Security boundaries](SECURITY.md)
- [Roadmap](ROADMAP.md)
