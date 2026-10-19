# CAPT OpenRouter model-availability preflight R1 — 2026-10-18

## Scope

A CAPT ProviderDriver **non-inference GET** before any `POST /chat/completions` or `POST /images` on the exact official OpenRouter origin. No prompt, memory data, private file, or tool arguments travel through the metadata lookup.

Source: `capt_runtime/provider_model_preflight.py`, called by `capt_runtime/drivers/provider.py`. Does **not** change CAPT approval, provider/model binding, model context-capacity policy, or inference budget. No provider alias substitution.

## Motivation and grounded evidence

From Oct 4–18 forensic ledger: two OpenRouter HTTP 404 runs used model IDs absent from the then-current local catalog; two HTTP 402s; image generations with unknown external outcome. A missing/stale local provider list is **not proof of why the provider returned 404**. Before a billable request, verify actual OpenRouter metadata without relying exclusively on old local config. The model-info endpoint is documented by OpenRouter as `GET /api/v1/model/:author/:slug`, and its image-specific model set as `GET /api/v1/images/models`.

## Gate

- Only triggers when provider identity is `openrouter` and configured base URL equals `https://openrouter.ai/api/v1`. Does not touch Ollama, MLX, llama.cpp or separately approved proxies.
- Exact model author/slug regex prohibits path traversal and ambiguous URL injection. Never redirects bearer credentials (reuses CAPT's `http_client.open_url` no-redirect transport).
- Requires configured provider credential locally, used for this provider's metadata GET; no secret is emitted in diagnostic results.
- Reads a bounded JSON response, requiring a model record. Image jobs must appear in the Image API adapter list and advertise image output.
- HTTP 404 or missing image entry → `PROVIDER_MODEL_UNAVAILABLE`. HTTP 401/402/403 → `PROVIDER_ACCOUNT_UNAVAILABLE`. Indeterminate GET failures → `PROVIDER_MODEL_PREFLIGHT_UNAVAILABLE`. All are **pre_dispatch**.
- No inferred availability from web page alone. A successful GET does NOT guarantee a subsequent inference request will succeed, a model has available capacity, or the key has sufficient spending allowance.

## Tests / status

`pytest -q tests/capt_runtime/test_provider_model_preflight.py tests/capt_runtime/test_provider_driver.py tests/capt_runtime/test_http_client_redirects.py`: **46 passed** in the isolated Core worktree, using only deterministic fake HTTP metadata and inference fixtures. No paid model run submitted. Provider metadata availability has not yet been smoke-tested through the configured live CAPT route.

## Risks and promotion gates

- A metadata outage will reject potentially valid inference, intentionally fail-closed to avoid unknown paid retries. Consider carefully bounded same-key positive cache with expiry after field evidence; never silently default to an alternate model.
- A model can exist in metadata while a regional/provider endpoint is unhealthy. Endpoint suitability and supported reasoning/tool parameters need separate capability receipts.
- Historical lost runs remain **reconciliation_required**; do not auto-replay.
- The preflight response is ephemeral; only sanitized failure codes and HTTP statuses are eligible for CAPT's immutable diagnostic projection.
- RuntimeService must be restarted and checked after merge before declaring this live. Even after promotion, billable smoke inference requires separate explicit approval.
