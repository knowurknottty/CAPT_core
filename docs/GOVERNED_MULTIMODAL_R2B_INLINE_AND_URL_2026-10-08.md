# CAPT governed multimodal R2B — inline document/video + image URL results

**Implementation status:** R2B adds specific governed, source-backed transport
variants. It does **not** certify the entire multimodal model ecosystem.

## Provider documentation checked (October 8, 2026)

- Google Gemini [File input methods](https://ai.google.dev/gemini-api/docs/file-input-methods.md):
  type `document` in Gemini Interactions `/v1beta/interactions` with
  `data` base64 and `mime_type: application/pdf`. Files API recommended
  for reuse/large inputs, separate upload step and file URI reference.
- Google Gemini [Video understanding](https://ai.google.dev/gemini-api/docs/video-understanding):
  type `video` with inline base64 and `mime_type: video/mp4` for
  smaller clips, or file URI from the Files API for larger content.
- Google [Files API](https://ai.google.dev/gemini-api/docs/files):
  two-phase resumable file upload; the returned upload session URL and
  file URI must not be confused with a model-consumption receipt.
- Google [Veo](https://ai.google.dev/gemini-api/docs/veo): generation is
  an asynchronous operation requiring polling and a separate asset
  download. The original R2A already implements an approved job boundary.

## R2B additions

1. Two new explicitly configured operations:
   `document_input` (PDF only) and `video_input` (MP4 only).
   These are not guessed from file extensions. The route must explicitly
   declare `gemini_interactions` transport, `json_text` response, an
   exact provider/model, and the corresponding `document`/`video`
   provider capability.
2. HumanApproval continues to bind the exact staged file path,
   original file SHA-256 and size, selected provider/model, network
   policy, immutable route fingerprint and cost ceiling. PDF signature
   `%PDF-` and MP4 `ftyp` are checked before approval.
3. Approved media requests construct typed Gemini Interactions content:
   an initial text prompt and a base64 `document` or `video` block with
   the matched MIME type. Digests are checked again after approval,
   before provider submission. Only the governed RuntimeService crosses
   the network boundary.
4. Synchronous Gemini text responses support documented
   `outputs: [{type: text, text: ...}]` and a bounded `output_text`
   convenience shape, with fallback to actual model `steps` text only.
   No user-input echo is admitted as model evidence. Nonterminal
   interactions **cannot be mistaken for completed results**.
5. `image_generate` can now declare `json_url` instead of `json_base64`
   **only** when the adapter declares explicit download origins. The
   service uses no redirects, requires an allowlisted asset origin,
   forbids cross-origin bearer forwarding, validates image MIME/signature,
   hashes the downloaded bytes and stores the result as an unverified
   local artifact. A failed second-stage fetch stays indeterminate; the
   generation POST is never replayed automatically.

The inline content remains capped at **12 MiB total, maximum eight
files**, preserving R2A memory/network/cost admission gates even where
upstream provider limits are higher. R2B does not pretend this is a
large-file upload API.

## Local acceptance

The tests exercise:
- Mocked Gemini-typed inline PDF and video with actual bytes;
- refusal before HumanApproval, single send after approval, no double-send;
- MIME magic checks, strict wire adapter matching and inline size refusal;
- an **authenticated Unix socket → actual local HTTP fixture** PDF
  path, with an unchanged second-dispatch count;
- Gemini response parsing and nonterminal result denial;
- allowlisted CDN image URLs and denied SSRF/private/unrelated hosts,
  redirection prevention by the existing transport, image magic checks,
  and explicit cross-origin token non-disclosure;
- Swift per-route file-type admission for PDF vs MP4.

No billable model inference or media generation was executed in these tests.

## Still release-gated

1. **Real remote provider acceptance** for each enabled model/route (including
   credential scopes, response variations, cost and provenance).
2. **Google Files API large uploads and provider file IDs:** resumable
   session admission, streamed bytes, upload URI/result identity,
   processing status, TTL/deletion and restart-safe request state.
   Must be an explicitly approved multi-step workflow; cannot simply
   replace an inline 12 MiB payload with an ungoverned URL.
3. Direct non-PDF documents and arbitrary archives need ingestion/parsing or
   provider-specific file-reference semantics, not silent type coercion.
4. Async Gemini Interactions/background video understanding, as distinct
   from async **video generation**, needs separate durable interaction IDs.
5. More generation vendors, URL JSON variants, signed-asset CDN families,
   audio responses and oversized media require separate tested adapters.
6. Physical invoice reconciliation is still not available: route ceiling
   admission is not a guarantee about provider final billing.

**Release interpretation:** R2B adds real governed runtime pathways and
local no-cost integration tests; production provider capability requires
independent live tests, never represented as complete by this document.


## Final signed R2B acceptance (2026-10-08)

- Committed executable source:
  `d2ee83d21a407a225b5559b7ad89cf9eb8e95243`,
  rebased onto CAPT Core PR #169 (`f5aef2f`) for physical provider-call
  accounting and council diagnostic changes.
- Combined full Core regression after rebase:
  **2,049 passed, 70 skipped, 13 deselected**.
  Local log: `~/capt-node-workspace/media-r2b-rebased-python.log`.
  The final code-only request-format adjustment for image URL output was
  subsequently verified by **12 passing R2B focused tests**.
- Native Swift suite after rebase: **164 passed, 9 skipped,
  zero failures**. Local log:
  `~/capt-node-workspace/media-r2b-rebased-swift.log`.
- Authenticated Unix-socket integration exercised
  local HTTP Gemini-shaped PDF consumption, explicit HumanApproval,
  direct file bytes, and zero repeat provider requests.
- A pre-upgrade checkpoint was accepted:
  `cp-cmd-9ae7c10f66158ae5`. There were no nonterminal DriverRuns.
- Resident RuntimeService source marker matches executable revision.
  Runtime remained **HEALTHY**, distribution **0.5.0**,
  checkpoint compatibility **0.1.0**, EventStore integrity `ok`.
  Read-only media catalog is still empty because no operator-approved
  media routes have been enabled.
- The signed CAPT.app at `~/Applications/CAPT.app` was verified
  strictly signed and byte-identical to the clean staged build.
  Executable SHA-256:
  `bb1c61f48417df019bb7415f5d4fe779fb0822320af0ac6659ff540713ce05b9`.
- TIA inspected the installed app and opened **Media I/O**.
  **Attach files** was available, and the no-routes configured notice
  remained visible. One installed app process; observed **0% CPU at idle**.
- Live provider registry contains OpenRouter with vision capability and
  a separate image-configured provider, but no registered Gemini provider,
  and no `media-routes.json`. The implementation does not invent
  a missing credential, endpoint, supported model, capability, or price.
- No real billable media or inference requests were sent. Consequently
  remote-provider acceptance and physical invoice correctness remain
  **unverified**, despite the complete local/runtime acceptance tests.
