# Model Providers

This page is the normal-user companion to [`PROVIDERS.md`](PROVIDERS.md).

## What works on merged `main`

CAPT already has a unified operator-layer foundation for provider registration, health/model discovery where supported, model selection, favorites/defaults/overrides, local/remote labeling, and secret-reference handling.

The old statement that *no unified provider/model surface exists* is obsolete.

Useful commands include:

```zsh
capt-ui capabilities
capt-ui providers
capt-ui models
```

The exact command help in the installed build is authoritative.

## What is integrating

PR #47 adds bounded inference transport for:

- Ollama native generation;
- OpenAI-compatible chat-completions endpoints.

That means the architecture has moved from configuration-only toward governed provider execution, but the branch is still unmerged and the final live-provider release gate remains open.

## Provider classes

### Ollama

Merged: discovery/health/model-list foundation.

Active integration: native generation at `/api/generate`.

### LM Studio / vLLM / llama.cpp-compatible servers

Merged: OpenAI-compatible registration/health/model-list foundation where configured.

Active integration: the generic OpenAI-compatible ProviderDriver path can target compatible `/chat/completions` endpoints, subject to endpoint/provider compatibility and later acceptance evidence.

### OpenRouter

Merged: provider registration plus health/model-list support where credentials/network allow.

Active integration: OpenAI-compatible generation transport. A controlled protocol test is not a paid/live OpenRouter acceptance run.

### MLX / mlx_lm

Registered as a local/native provider class, but native generation parity is still not a merged supported path. Do not route it through HTTP merely to make the matrix look complete.

### Hermes

Hermes remains a compatibility/execution client path, not CAPT runtime authority. Historical v0.5 evidence proves bounded installed-wheel interaction; newer lifecycle hardening lives in PR #46. The separately supplied LOCAL-002 identifiers (`evidence/hermes-local-002-r6` / `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`) are currently absent from the GitHub remote/API, so `HERMES_LOCAL_002_COMPLETE` and its supplied workspace results are **unverified metadata**, not provider evidence. See `CURRENT_STATE.md`.

## Choosing a model

Selection does not grant capability and does not prove execution. The runtime still controls mission/task authority, approvals, leases, dispatch, evidence, verification, and completion state.

## Current flagship acceptance target

A meaningful cross-model proof is:

```text
Model A -> governed work -> evidence -> checkpoint -> process exit
Model B -> same CAPT state -> no-repeat recovery -> new governed work -> evidence/verification
```

Synthetic model names or provider switching inside one process do not satisfy that target.