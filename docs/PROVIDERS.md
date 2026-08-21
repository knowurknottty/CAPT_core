# CAPT Providers

Provider registration, provider execution, native presentation, and release proof are separate states.

## Terminal convergence provider spine

The convergence line supports governed execution through:

- Ollama native generation;
- configured local OpenAI-compatible endpoints such as MTPLX, LM Studio, vLLM, and llama.cpp-style servers where their API surface matches the adapter contract;
- authenticated OpenAI-compatible remote/provider paths where credentials are configured;
- Hermes as a compatibility execution path rather than CAPT authority.

Selected local OpenAI-compatible models have bounded prewarm support so known-cold residency can be handled before the first user workload without creating Mission/Task/DriverRun authority.

## Provider/model coherence

PR #118 is closed unmerged; its provider/model-coherence semantics are reconciled onto the terminal candidate:

- activating a provider persists a coherent global provider/model tuple;
- legacy provider registries backfill current defaults without overwriting persisted operator configuration;
- a restored chat may keep its session provider/model while New Chat re-reads the global default;
- if global selection differs from the current chat, native UI keeps the provider action available instead of pretending the chat already switched.

This prevents an impossible state such as globally displaying MTPLX while `models.json` still binds the same model to Ollama.

## MLX naming boundary

The dormant generic native `MLX / mlx_lm` placeholder had no real model-list, health, or execution adapter and is therefore retired/unregistered by default. It must not be displayed as a working second MLX server.

A **materially configured** local OpenAI-compatible MLX/MTPLX service is a different, supported provider path. A future direct native `mlx_lm` adapter must earn its own registration and verification.

## Operator commands

```zsh
capt-ui capabilities
capt-ui providers
capt-ui models
```

A healthy provider entry is not proof that a governed inference mission completed through it.

## Secrets

Provider configuration stores secret references rather than raw tokens where supported. Provider diagnostics/provenance must not persist authorization headers or raw API keys. Credentialless OpenAI-compatible execution is admitted only for explicitly local loopback endpoints under the local-provider contract.

## Proof boundary

Controlled loopback-provider tests establish transport/governance/idempotency behavior. Live intended-provider runs establish a different evidence class. Neither automatically closes release-security controls or model-quality claims.
