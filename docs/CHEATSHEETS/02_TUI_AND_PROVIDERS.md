# 02 — TUI and Provider Operations

## The TUI is a client, never runtime authority

Implementation: `capt_ui/surfaces/tui/app.py` (`CaptTUI`). It uses `capt_ui.operator.runtime.Operator`, which connects to the authenticated RuntimeService socket. The TUI does not write EventStore records itself, issue leases, decide claims, or retain provider lifecycle truth.

Launch:

```zsh
capt tui
```

Controls present now:

| Control | What it does |
|---|---|
| Provider select (`p`) | Focuses provider selection. Provider change immediately invalidates incompatible model state. |
| Model filter (`/`) | Focuses text filter for the scoped model inventory. |
| Model select (`m`) | Focuses provider-scoped model selection. |
| Prompt (`F6`) | Focuses the governed task objective editor. Printable keys remain prompt input while it is focused. |
| RUN (`Ctrl+Enter`) | Invokes `run_approved_hermes_inspection` with provider/model/objective/target root from one current selection state. The historical operation name routes to ProviderDriver when `provider` is present. |
| CHECKPOINT (`c`) | Sends `checkpoint_runtime` to RuntimeService. |
| Current Run | Shows the current receipt’s provider/model, status, mission and DriverRun correlation IDs. |
| Output | Displays an untrusted provider observation summary or a safe error result. |
| `r` / `F5` | Refreshes authoritative projections. |
| `F7` | Focuses the Logs projection. |
| `v` | Cycles local CaveCAPT verbosity. |
| `Ctrl+Q` | Quits. |

The selector and prompt are not proof of execution. Proof is the resulting DriverRun/evidence/verification state.

### Current interaction contract

- `Tab` / `Shift+Tab` use Textual’s focus traversal. `Enter` / `Space` activate focused controls using native widget behavior.
- Provider is the scope boundary for the model list. Provider switches clear a stale model filter and invalidate a model that does not belong to the new provider.
- Model refreshes are generation-guarded. An obsolete refresh cannot write options after the active provider changed.
- RUN uses a Textual worker so the interface remains responsive while RuntimeService performs bounded work. Every worker exit path releases the busy state and re-enables RUN.
- Current Run identifies the receipt from the operator action. Evidence/verification are labeled as latest authoritative projections and must be correlated by DriverRun ID, never presumed current merely because they are visible.
- The console contains no direct provider dispatch, EventStore writes, secret value, or lifecycle authority.

## `capt-ui` command surface

```zsh
capt-ui status
capt-ui dashboard
capt-ui providers
capt-ui providers --test ollama
capt-ui providers --activate ollama
capt-ui providers --key-ref openrouter env:OPENROUTER_API_KEY
capt-ui capabilities
capt-ui models
capt-ui models --set ollama/qwen3.6-fable-fusion:latest
capt-ui verbosity
capt-ui memory
capt-ui onramp
```

`capt-ui` provides operator configuration and read projections. It is not a direct model executor.

## Provider records

Implementation: `capt_ui/operator/providers.py`.

Provider fields persisted to `<state-root>/ui/providers.json`:

```text
id, name, kind, transport, base_url, key_ref, context_limit,
enabled, selected, health, latency_ms, last_success_at, models, capabilities
```

Security validation:

- `key_ref` is empty or a reference only: `env:VARIABLE` or `keychain:ACCOUNT`.
- raw key strings are rejected.
- `base_url` must be absolute `http`/`https` with a hostname.
- URL user/password, query, and fragment are rejected.
- failed `update()` validation occurs on a copy before mutation/persistence.
- loading persisted provider records validates before use.

Current default templates include OpenRouter, Ollama, LM Studio, MLX, vLLM, llama.cpp, and Hermes. The current governed provider driver supports the requested `ollama` and `openrouter` execution path. A registered UI template must not be read as governed execution support.

## Secrets

Implementation: `capt_ui/operator/secrets.py`; transport resolution occurs inside RuntimeService immediately before provider host construction.

Recommended zsh session setup:

```zsh
export OPENROUTER_API_KEY="$(tr -d '\r\n' < ~/noexcuses/fake.env)"
capt-ui providers --key-ref openrouter env:OPENROUTER_API_KEY
```

Never do any of these:

```text
capt-ui providers --key-ref openrouter sk-...
https://sk-...@provider.example/v1
capt run --api-key sk-...
```

The key is not written to provider JSON, EventStore, artifact output, provider provenance, command receipt, or documentation.

## Ollama

Provider record defaults to `http://localhost:11434/v1`; execution uses native `POST /api/generate` at base URL with `/v1` removed. The TUI calls the supported health/model-list adapter dynamically. If offline/unreachable, the model picker presents no usable model and output/notification identifies provider unavailability rather than crashing.

The runtime accepts any selected live local model name subject to provider availability and existing governed capability constraints. The model list is intentionally dynamic.

## OpenRouter

Provider record defaults to `https://openrouter.ai/api/v1`; execution uses `POST /chat/completions` with a Bearer token supplied only in process memory. The configured primary text model is:

```text
deepseek/deepseek-v4-flash-0731
```

`capt_ui/operator/openrouter_models.py` contains the operator-approved label catalog. Only labels with an unambiguous verified ID and text compatibility are returned by `available_text_models()`. Current resolved selection:

```text
DeepSeek V4 Flash 0731 → deepseek/deepseek-v4-flash-0731
```

All other approved labels remain cataloged but unresolved rather than guessed. Audio/image labels are excluded from the text task selector.

## Provider failure matrix

| Condition | Expected safe behavior |
|---|---|
| Ollama daemon absent | adapter health red / unavailable model selection; no TUI crash |
| local model absent | provider error/empty selection; no fabricated model result |
| OpenRouter key reference missing | RuntimeService rejects before dispatch as `PROVIDER_CREDENTIAL_UNAVAILABLE` |
| OpenRouter 401 | ProviderDriver reports HTTP failure; external work has been attempted, so lifecycle conservatively records failure state rather than replaying automatically |
| provider timeout/transport error | DriverRun/task recovery path applies; do not retry by resubmitting same uncertain work |
| malformed endpoint/raw key config | UI configuration validation rejects before persistence or health probe |
| provider output has no text | ProviderDriver fails; no fake observation is generated |

## Provenance emitted by ProviderDriver

`capt_runtime/drivers/provider.py` computes and returns:

```text
provider
model
endpointClass: local | cloud
promptDigest: sha256:...
responseDigest: sha256:...
driverRunId
externalRunId
artifactCandidate: path + artifactDigest
untrusted observation summary
```

Provider response text is written into a CAPT-managed staging artifact. Provider credentials are never written there. The response remains untrusted even though CAPT hashes the artifact.
