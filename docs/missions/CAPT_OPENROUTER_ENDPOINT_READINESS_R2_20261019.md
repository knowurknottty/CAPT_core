# OpenRouter inference endpoint readiness R2 — 2026-10-19

## Observed gap

After the exact-model catalog check had been merged, CAPT still recorded one OpenRouter HTTP 404 after an inference request began and one response-body timeout. The 404 DriverRun `dr-model-849ed07577c32f93bf5b8582` remains `lost` / `reconciliation_required`, and `dr-model-723d8eabc48da8b23c5facc1` remains `lost` / `reconciliation_required` after a response-body timeout. A distinct Qwen run `dr-model-b131712cb06ad77bba3ad50e` completed and persisted output. This does not establish whether a missing route caused the HTTP 404.

The original model metadata GET confirms that an author/slug is listed but not that any inference endpoints exist. OpenRouter documents a separate endpoint list: `GET https://openrouter.ai/api/v1/models/:author/:slug/endpoints`.

## Repair

For the exact official OpenRouter text-model path only:
1. First check metadata for the **exact authorized model ID**, as before.
2. Before provider inference POST, execute a second **read-only, authenticated** GET for the exact model's endpoint list.
3. Reject HTTP 404 or an empty endpoint list as `PROVIDER_ENDPOINT_UNAVAILABLE` at the `pre_dispatch` phase, with no inference boundary crossed. Reject mismatched model identity and malformed metadata with `PROVIDER_MODEL_PREFLIGHT_INVALID`.
4. Preserve existing account/credit and metadata-outage typed failures. Only allowlisted statuses and error codes become persisted CAPT diagnostics.
5. Never alter the approval-bound model, select another provider, retry a lost request, or send prompts, agent tool arguments, MemoryStore content, or context packs in either metadata GET.

**Acceptance evidence:** 63 selected deterministic local provider, HTTP redirection and sanitized diagnostic tests pass. Fixtures include metadata success with routing endpoints, empty endpoints, 404, invalid schemas, mismatched model identity, timeout, and proof that rejected cases never reach the inference POST.

## Deliberate limits

- Endpoint-list presence is evidence that an endpoint is listed, **not** proof the provider is healthy at dispatch time, supports the exact tool/response schema or has capacity.
- The second metadata GET introduces additional latency and a fail-closed dependency on provider metadata service availability. No caching is implemented because an unbounded stale positive cache could conceal an endpoint withdrawal.
- This change is source-only until CI, merge, and controlled RuntimeService deployment; no paid inference was invoked during testing.
- The historical 404 and timeout remain externally indeterminate until independent provider/billing reconciliation. No automatic retry.

Official documentation: https://openrouter.ai/docs/api/api-reference/endpoints/list-endpoints
