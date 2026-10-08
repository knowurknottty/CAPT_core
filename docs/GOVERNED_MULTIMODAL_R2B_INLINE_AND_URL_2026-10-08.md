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
