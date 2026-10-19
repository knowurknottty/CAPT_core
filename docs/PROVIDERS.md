# CAPT Providers

Provider registration, provider execution, native presentation, and release proof are separate states.

## Merged provider spine

Current `main` supports governed execution through:

- Ollama native generation;
- configured local OpenAI-compatible endpoints such as MTPLX, LM Studio, vLLM, and llama.cpp-style servers where their API surface matches the adapter contract;
- authenticated OpenAI-compatible remote/provider paths where credentials are configured;
- Hermes as a compatibility execution path rather than CAPT authority.

Selected local OpenAI-compatible models have bounded prewarm support so known-cold residency can be handled before the first user workload without creating Mission/Task/DriverRun authority.

## Provider/model coherence

PR #118 is closed unmerged; its provider/model-coherence semantics were reconciled into merged PR #117:

- activating a provider persists a coherent global provider/model tuple;
- legacy provider registries backfill current defaults without overwriting persisted operator configuration;
- a restored chat may keep its session provider/model while New Chat re-reads the global default;
- if global selection differs from the current chat, native UI keeps the provider action available instead of pretending the chat already switched.

This prevents an impossible state such as globally displaying MTPLX while `models.json` still binds the same model to Ollama.

Later merged native/TUI authority controls bind provider-network policy and filesystem/shell scope into model approval. The semantic operator-control API binds provider/model/workspace/prompt-intelligence configuration by revision and digest, rejecting stale submissions. Prompt compiler provider selection is separate from the execution model default; compiler success does not establish execution-provider quality.

## OpenRouter availability preflight (source at `c956c45e`)

For a model execution already authorized through **the exact official OpenRouter provider endpoint**, `ProviderDriver` first performs a bounded, authenticated **catalog GET**: text models use `/api/v1/model/:author/:slug`; image models use `/api/v1/images/models` and must advertise image output. The lookup sends **no prompt or model context**, but it **does make a network request** using the configured provider credential. It does not run for unrelated Ollama/local/proxy endpoints. See [`provider_model_preflight.py`](../capt_runtime/provider_model_preflight.py) and [`drivers/provider.py`](../capt_runtime/drivers/provider.py).

If the metadata lookup rejects the model (404 or absent image entry), CAPT reports `PROVIDER_MODEL_UNAVAILABLE`; credential/account responses (401/402/403) map to `PROVIDER_ACCOUNT_UNAVAILABLE`; indeterminate failures map to `PROVIDER_MODEL_PREFLIGHT_UNAVAILABLE`. These occur **before inference submission**, so do not blindly retry on an unknown account state or switch providers outside the exact authorized request. **Catalog presence is not a guarantee of subsequent capacity, pricing, modality support beyond the checked route, successful generation, or public-release proof.** At this checked revision, the **text** metadata parser accepts a returned record with an `id` string without asserting it equals the requested ID; the metadata URL is exact, but a matching response identity is **not independently verified** by that code path. The [RRDS partial review](missions/OMEGA_RRDS_C956C45E_PARTIAL.md) tracks this as an implementation/test follow-up.

Selected deterministic tests at `c956c45e` passed; a live official-endpoint smoke check and billable inference were **not** executed for this documentation mission. See [current-HEAD delta](CURRENT_HEAD_DELTA.md).

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
