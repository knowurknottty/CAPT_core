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

## Hermes local workspace evidence

`HERMES_LOCAL_002_COMPLETE` is recorded on the dedicated evidence branch `evidence/hermes-local-002-r6` at pushed HEAD `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`. The report records 98/0/0 focused tests and 174/0/2 broader tests under the faithful Hermes TUI workspace npm path, with no product/state-map blocker. See [`CURRENT_STATE.md`](CURRENT_STATE.md) and [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md) for the exact boundary and remaining gaps.

That evidence strengthens the Hermes/TUI workspace state map. It does **not** erase the separate need for destructive external-provider/tool-kill rollback proof or general live-provider release acceptance.

## TUI integration

PR #47 connects provider/model selection to the upgraded TUI run surface and carries prompt-enhancement, response-mode, requested-context-budget, and human-verification preferences into the governed command path.

## Secrets

Merged provider configuration stores secret **references** rather than raw tokens where supported. The active ProviderDriver must not persist authorization headers or raw API keys into evidence/artifacts.

## Release gate

Do not claim `GOVERNED_EXECUTION_PROVEN` for a provider until exact-head, installed-runtime, intended-provider evidence exists and the result has survived the normal CAPT evidence/verification boundary.