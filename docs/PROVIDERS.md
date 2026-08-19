# CAPT Providers

Provider **registration/discovery**, provider **execution**, and provider **release proof** are separate states.

## Merged `main`

The shared operator layer contains provider configuration/adapters and honest capability classification. Supported discovery/health/model-list behavior depends on transport/provider.

| Provider family | Merged registration | Health/model-list foundation | Governed generation on `main` |
|---|---:|---:|---:|
| OpenRouter / OpenAI-compatible | yes | yes where configured | no |
| Ollama | yes | native discovery/health/model list | no |
| LM Studio | yes | OpenAI-compatible discovery/health/model list | no |
| vLLM | yes | OpenAI-compatible health/model list | no |
| llama.cpp server | yes | OpenAI-compatible discovery/health/model list | no |
| MLX / mlx_lm | registered foundation | limited/not operational in merged adapter | no |
| Hermes compatibility | registered/bounded compatibility surface | separate subprocess path | bounded historical/current local evidence, not general provider parity |

Use:

```zsh
capt-ui capabilities
capt-ui providers
capt-ui models
```

A healthy provider entry is **not** evidence that CAPT completed a governed inference mission through it.

## Active PR #47 ProviderDriver

The active cumulative branch adds a bounded, read-only provider execution driver with:

- Ollama native `POST /api/generate`;
- OpenAI-compatible `POST /chat/completions`;
- explicit provider/model/endpoint provenance;
- prompt and response digests;
- secret exclusion from returned diagnostics/artifacts;
- dispatch-boundary tracking;
- cancellation recorded truthfully as a request when the underlying urllib call cannot be aborted;
- reconciliation for pre-dispatch, response-complete, and externally-unknown states.

Controlled local HTTP servers exercise the real request/response protocol shape in tests. That establishes transport/lifecycle behavior, **not** live-provider release acceptance.

## Hermes LOCAL-002 workspace metadata

The operator supplied `HERMES_LOCAL_002_COMPLETE` metadata for `evidence/hermes-local-002-r6` / `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04` with reported 98/0/0 focused and 174/0/2 broader tests and npm environment details. Terra could not retrieve that branch, commit, or `reports/local-evidence/HERMES_AGENT_TUI_WORKSPACE_TESTS_AND_STATE_MAP_8F97AE9_2026-08-17.md` from the current GitHub remote/API.

Accordingly, LOCAL-002 is **currently unverified metadata, not provider evidence**. Historical v0.5 Hermes proof remains separate. The missing LOCAL-002 record cannot close destructive rollback, general live-provider acceptance, installed-runtime acceptance, or any PR #47 proof boundary. See [`CURRENT_STATE.md`](CURRENT_STATE.md) and [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md).

## TUI integration

PR #47 connects provider/model selection to the upgraded TUI run surface and carries prompt-enhancement, response-mode, requested-context-budget, and human-verification preferences into the governed command path.

## Secrets

Merged provider configuration stores secret **references** rather than raw tokens where supported. The active ProviderDriver must not persist authorization headers or raw API keys into evidence/artifacts.

## Release gate

Do not claim `GOVERNED_EXECUTION_PROVEN` for a provider until exact-head, installed-runtime, intended-provider evidence exists and the result has survived the normal CAPT evidence/verification boundary.