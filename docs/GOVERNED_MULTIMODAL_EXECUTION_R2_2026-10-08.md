# Governed multimodal R2A — executable media runtime, 2026-10-08

## Implementation/authority boundary

The previous R1 picker and native quarantine persist as originally shipped.
R2A introduces a distinct authenticated **Media I/O** workbench in the Swift
chat and corresponding RuntimeService command/query operations.

This release implements:
- exact model/provider/operation/media-route selection from an operator-owned
  registry; no model-name guessing or silent provider fallback;
- read-only `media_route_catalog` query (empty until explicitly configured);
- `prepare_media_approval` command: resolves exact route, validates file
  confinement/regularity, recomputes SHA-256, checks MIME family and signature,
  bounds inline bytes (12 MiB total, 8 files), budget and network authority,
  freezes a full adapter fingerprint and persists a one-use HumanApproval;
- existing `submit_approval_decision` human approval, with explicit native
  **Approve exact media request** and separate **Run approved media** actions;
- `submit_approved_media`: re-verifies input digests, consumes the one-use
  approval and creates a durable DriverRun BEFORE HTTP, records the
  `request_started` boundary and a separate encrypted idempotency job
  receipt. Duplicate execution never silently resubmits an uncertain call;
- image understanding via OpenAI-compatible `chat/completions` content blocks:
  **actual** digest-bound image bytes transmitted as base64 data URI;
- speech transcription using multipart audio-file bytes;
- synchronous image generation using bounded base64 response bytes
  (PNG/JPEG/WebP detection) and audio generation using MP3 binary;
- asynchronous video generation: once-only POST, durable external
  operation ID, operator-driven status polling, explicit approved asset
  download. The production video downloader streams up to the exact
  adapter/approval asset-size ceiling, hashes bytes, verifies MP4
  header, writes private staged artifacts, and forbids redirects;
- signed audio/video asset URLs are never copied into the chat.
  Download origin must match an exact explicit provider allowlist;
  bearer keys are not sent to unrelated CDN/asset origins;
- `media_job_status` read-only query: committed state, operation ID,
  unverified result artifact digest/path or text, never a model resubmit;
- generated media previews in native Chat use the existing R1 local
  path + SHA-256 checks and user-invoked Quick Look. Vision/transcription
  results are shown as unverified assistant text, not certified claims.

## Native workflow

1. Select Attach files; CAPT stages arbitrary regular files locally.
   R2A explicitly supports **images** and **audio** as provider inputs.
   Documents, arbitrary binaries and video inputs remain quarantined
   local-only until an adapter and authority path are implemented.
2. Choose **Media I/O** in Chat. CAPT displays only routes explicitly
   configured for the exact model, operation and provider.
3. Type the objective; select a compatible route and cost ceiling.
   **Prepare governed media approval** creates a real HumanApproval
   and binds a full contract hash and file content digests. No provider
   call occurs.
4. Inspect the approval; press **Approve exact media request**.
   No provider call occurs at this step either.
5. Press **Run approved media** to cross the external boundary once.
   The result is stored as an unverified media artifact or as the
   accepted external operation ID.
6. For asynchronous video, **Poll existing video job** then
   **Download approved video artifact**. Both use the original bound
   provider, model and external operation ID.
7. After a socket failure/relaunch, use **Refresh status**. Neither
   the poll nor the status query can start a new video generation.
   After an indeterminate POST, do not automatically retry.

The approval request ID and DriverRun ID survive the encrypted native
chat session cache. Provider outcomes are stored in EventStore's
encrypted idempotency records; DriverRun admission/boundary and approval
events are recorded in the canonical event ledger. Media outcomes
remain *unverified candidates* until independent human verification.

## Explicit provider route configuration

R2A does **not** turn on remote media providers automatically. To enable
one, the operator must first configure the provider/model in
`~/.capt/ui/providers.json`, with its supported `capabilities`,
secure `key_ref` and exact `base_url`. Then define an exact route in
`~/.capt/ui/media-routes.json`:

```json
{
  "schemaVersion": "1.0.0",
  "routes": [{
    "enabled": true,
    "adapterId": "local-image-generation",
    "provider": "local-media-example",
    "model": "local-image-model",
    "operation": "image_generate",
    "origin": "http://127.0.0.1:9000",
    "transport": "json",
    "submitPath": "/v1/images",
    "responseType": "json_base64",
    "mediaTypes": ["image/png"],
    "authStyle": "none",
    "maximumPriceUSD": 0.0,
    "maxAssetBytes": 67108864
  }]
}
```

This is an **illustrative route**, not a claim that a server on port 9000
exists. The matching provider registry entry must be local, enabled,
declare capability `image`, and advertise model `local-image-model`
at exactly the same origin; no credentials are persisted in the route.

For Google Veo-style remote video endpoints, a separately configured
provider should declare `video` capability, exact model identifier,
`x-goog-api-key` auth, a model-specific
`/v1beta/models/<model>:predictLongRunning` submit path,
`/v1beta/{job_id}` poll path, result path, and allowlisted video-file
download origin. Costs **must be explicitly researched and bounded by
the operator**; the runtime refuses routes whose configured cost ceiling
exceeds the HumanApproval limit. Use only endpoints corroborated against
the live provider documentation. Do not blindly paste an example into
production settings.

Route metadata is validated at RuntimeService startup, immutable for
that runtime instance, and matched to the registered provider/model.
A malformed optional route file disables ALL media routes with
`MEDIA_CONFIGURATION_INVALID`, rather than crashing Core.

## Explicitly unproven / blocked from unrestricted public release

- Real billable OpenRouter/Google/other provider calls have **not**
  been executed. HTTP mocks and a local fake provider passed.
- The operator-declared route price ceiling is an **admission check**,
  not physical enforcement of the external provider's final invoice.
  Dynamic token/second pricing, charge reconciliation, and provider
  billing disputes remain unimplemented.
- Arbitrary documents, raw video uploads, multi-image sequence video
  understanding, large >12 MiB inline uploads, provider file-ID
  workflows and asynchronous audio outputs need additional adapters.
- Vendor variants returning image URLs rather than inline base64,
  alternate signed-asset schemes, video reference-frame inputs and
  unusual voice/format parameters need endpoint-specific driver code.
- Video result polling is explicit human-driven, not a schedule/service
  worker. Long operations survive restarts by operation ID, but there
  is no automatic background polling.
- Media receipt storage does not independently attest correctness,
  safety, consent, provenance ownership or ClaimGuard verification.
- No cross-provider/model live smoke has yet been done. R2A is a
  governed foundation and a live-capability acceptance gate, **not**
  proof that all provider/media combinations work.

## Testing evidence

The offline tests cover HumanApproval denial, one dispatch after approval,
same-ID duplicate prevention, post-dispatch timeout, reloaded operation ID,
multipart audio input, true base64 image input, media signature mismatches,
route tampering, video polling, SSRF download refusal, streamed binary
download, and authenticated RuntimeService socket + native model tests.

See local CI logs in `~/capt-node-workspace/media-r2-*.log`. No paid media
inference was triggered by the regression suite.
