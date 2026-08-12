# CAPT Providers

CAPT separates **provider registration** from **provider execution**. A
registered provider template does **not** imply operational model execution.

## Registered providers

| Provider | Kind | Transport | Discovery | Health | Model list | Model execution |
|---|---|---|---|---|---|---|
| OpenRouter | cloud | openai_compatible | – | ✅ | ✅ | ❌ (P1) |
| Ollama | local | ollama (`/api/tags`) | ✅ | ✅ | ✅ | ❌ (P1) |
| LM Studio | local | openai_compatible | ✅ | ✅ | ✅ | ❌ (P1) |
| vLLM | hybrid | openai_compatible | – | ✅ | ✅ | ❌ (P1) |
| llama.cpp-server | local | openai_compatible | ✅ | ✅ | ✅ | ❌ (P1) |
| MLX / mlx_lm | local | native | ❌ | ❌ | ❌ | ❌ |
| Hermes | local | subprocess | ⚠️ | ❌ | ❌ | bounded-when-governed |

Support level reflects reality: `REGISTERED_ONLY` → `HEALTH_PROBE` →
`HEALTH_AND_MODEL_LIST`. **No provider currently claims `MODEL_EXECUTION_IMPLEMENTED`
or `GOVERNED_EXECUTION_PROVEN`** — that is a published release gate, not hidden
capability.

View the authoritative matrix:

```bash
capt-ui capabilities
```

## Provider/model selection

```bash
capt-ui providers      # list providers + health
capt-ui models         # list models for a provider
capt-ui verbosity      # CaveCAPT verbosity (presentational)
```

## Governed execution (release gate)

Real governed model execution — CAPT mission → governance → provider/model →
real generation → artifact/evidence → verification → persisted result — is a
v0.6 flagship release gate. It is **NOT YET PROVEN** and must not be
represented as such. The continuity demo uses synthetic model IDs and does not
prove cross-model continuity. See `capt_ui/ACCEPTANCE_STATUS.md`.
