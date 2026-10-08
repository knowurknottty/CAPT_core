# Governed multimodal R2C — large-file upload and reference consumption

## Purpose and sources

R2B accepted bounded inline PDFs and MP4s. R2C implements a **distinct
large-file** path using Gemini Files API, with two independent authority
boundaries. Source references:

- https://ai.google.dev/api/files — resumable start, upload+finalize,
  provider File metadata and state;
- https://ai.google.dev/gemini-api/docs/files — reuse uploaded file URI,
  process-state polling and retention;
- https://ai.google.dev/gemini-api/docs/video-understanding — typed video
  file URI in Interactions;
- https://ai.google.dev/gemini-api/docs/document-processing — typed PDF
  file URI and 48-hour Files API retention.

These references describe Google APIs; the current CAPT Core adapters
intentionally implement an explicit subset, **not all vendors**.

## Governance and implementation

1. **Local intake**: existing native arbitrary-file picker copies the file
   to private local staging with a SHA-256 and 0600 permissions. Uploaded
   input is limited to one supported file per approval, maximum 2 GiB,
   hard bound to the original size/hash and MIME signature.
2. **First HumanApproval (upload)**: the operator selects an enabled
   `file_upload` route with transport `gemini_resumable` and response
   `file_receipt`. The runtime freezes provider, model, endpoint,
   network authority, local staged-file SHA-256/size/MIME and an upload
   cost ceiling of **$0**. No upload occurs before approval and separate
   Run.
3. **Upload**: after consumption of the one-use approval, CAPT commits
   a DriverRun and a durable idempotency admission before contacting
   Google. The Files API returns a one-time resumable session URL;
   the runtime refuses cross-origin/redirected sessions and streams
   the file in bounded blocks without loading 2 GiB into RAM.
   The session URL is never written to the chat or result ledger.
   The provider returns a file name/URI/state; CAPT validates the host,
   resource path and MIME and stores the opaque file identity in an
   encrypted idempotency receipt.
4. **Processing state**: `poll_media_job` GETs the exact admitted
   `files/<id>` status using the frozen route. It cannot upload or
   invoke a model. File states are `file_processing` or `file_active`;
   provider-reported failure is rejected. Receipts include a conservative
   47-hour validity horizon rather than claiming indefinite retention.
5. **Second HumanApproval (model consumption)**: a separate route,
   `file_reference_input` over `gemini_interactions`, accepts ONLY a
   verified, *active* original upload DriverRun. It must match the same
   provider and model, the allowed MIME, and unexpired original upload
   receipt. The second approval freezes uploaded file ID, URI, original
   SHA-256 and expiry plus prompt, endpoint and explicit model-cost bound.
   This is a separate one-use paid-model authority; the upload alone
   never implies permission to read.
6. **Reference inference**: with the second HumanApproval, the actual
   `/v1beta/interactions` request contains typed `document`, `video`,
   `audio` or `image` blocks with provider-issued `uri` and
   `mime_type`. No local raw-byte retransmission or arbitrary user-supplied
   URI is accepted. All model text remains **unverified** until reviewed.
7. **Reconnect and duplicate control**: after a socket loss, the native
   session persists both upload and reference DriverRun IDs. Read-only
   `media_job_status` and the original approval are reattached.
   Lost responses after upload start are **indeterminate**, never
   automatic retry (which could duplicate uploads or costs).
8. **Native UI**: Media I/O exposes **Check uploaded file processing**
   and **Prepare separate file-consumption approval** after the file
   reaches active state. The reference route must be explicitly chosen
   and the model cost authorized before its own Run.

## Operator configuration blocker

This machine had neither a registered direct Gemini provider nor
`~/.capt/ui/media-routes.json` when R2C work started.
The existing OpenRouter registration does **not** authorize Gemini
Files API access or prove support for provider file IDs.

R2C includes example **disabled** Gemini entries for an operator to
validate, rather than enabling billable endpoints or guessing a price.
Use Keychain account `gemini-ai-studio` under service
`capt-provider` and configure `key_ref: keychain:gemini-ai-studio`
(no raw key in configuration). The operator must verify that model
`gemini-3.8-flash` is accessible with their credentials and set the
current model-reference price ceiling before enabling the consumer route.
The upload itself is configured at $0 because Google's Files API
documented upload is free; **inference is not**.

The disabled sample can be found in
`docs/examples/gemini-media-r2c-disabled.json`. It is NOT a promise of
capability until the model, credential, pricing and live endpoint pass
acceptance. No paid model call is authorized by merely installing R2C.

## Not yet supported

- True server-side resumable **chunk offsets across reconnects**. This
  version starts and streams in one authenticated request; after an
  interrupted finalize, status is indeterminate. No automatic resume or
  second upload is attempted, because the transient signed upload URL
  must not escape the governed process. A separate explicit upload
  resume/session authorization is required.
- Arbitrary file types beyond currently explicitly supported image,
  audio, MP4 and PDF MIME/signatures; multi-file references and mixed
  media prompts; provider file deletion; file ownership verification.
- Automatic background processing polls, re-upload after TTL and
  cross-provider portable file IDs. File consumption cannot cross
  providers or silently change model/endpoint.
- Real paid Google model acceptance, invoice reconciliation and media
  cost enforcement beyond the operator-bound admission ceiling.
- Unsupported nonstandard audio/video generation responses and API
  families remain separately gated.

## Tests / installation

R2C acceptance must include real local HTTP streaming, HumanApproval
denial, 13 MiB PDF crossing the former inline limit, file-state
polling, independent reference approval, no duplicate dispatch after
failure/restart, unsafe URL rejection, Swift native-session roundtrip,
and the full Python/Swift regression gates. Installed/live acceptance
requires a separate signed-build and RuntimeService verification.


## Final R2C source and installed acceptance — 2026-10-08

- Executable CAPT Core source:
  `bfcfd4b67449b8bf0325952dc7bb7c89b7b88ea3`, committed
  to `origin/main`.
- Full source Python regression: **2,060 passed, 70 skipped,
  13 deselected**. Log:
  `~/capt-node-workspace/media-r2c-final-full-python.log`.
- Native Swift suite: **165 passed, 9 skipped, 0 failed**. Log:
  `~/capt-node-workspace/media-r2c-swift-v2.log`.
- Authenticated Unix-socket integration exercised **two separate
  HumanApprovals**, local HTTP resumable start, streamed 13 MiB PDF
  upload/finalize, processing-state GET, and reference-based model
  consumption. A second same-identity dispatch performed **zero extra
  POSTs**. All external endpoints were local fixtures, not billed.
- Production transport exercised local streaming of an independently
  bounded 15 MiB file with an explicit byte count, no bearer forwarding
  to the upload-session URL, and exact-origin upload URL validation.
- Resident daemon checkpoint `cp-cmd-d2b3108aaacdeb97` accepted at
  EventStore head 23503 with **zero nonterminal DriverRuns**.
- RuntimeService restarted from this exact source, **HEALTHY**,
  EventStore integrity `ok`, CAPT distribution 0.5.0; compatibility
  `runtimeVersion=0.1.0` is **not** the package version.
- Apple-signed CAPT.app at `~/Applications/CAPT.app` is verified
  byte-identical to the staged build. Installed executable SHA256:
  `c9fdc081ae6902bdeaaf54bdc2e5838418e572be678827475f1b4666f517c2ba`.
  A rollback of the original app is retained under
  `~/capt-node-workspace/worktree-archive/CAPT.app-pre-media-r2c-bfcfd4b`.
- TIA activated installed Chat, identified Attach files and Media I/O,
  opened the workbench, and verified its truthful **no enabled routes**
  notice. One installed app instance returned to 0% CPU at idle.
- Safely scaffolded a **disabled** Gemini provider and two **disabled**
  media routes in the user's `~/.capt/ui` directory; existing entries
  were preserved, edits were atomically written with mode 0600 and
  backups stored under `~/.capt/ui/config-backups/20261008-media-r2c`.
  `load_media_routes` validates the configuration with **0 enabled
  routes** and no credential refs exposed to the runtime catalog.
- Keychain lookup of account `gemini-ai-studio` under service
  `capt-provider` did not find a credential. No model pricing,
  credentials, or provider capabilities were fabricated.
- No paid provider inference, no real Google file upload, no
  video/image/audio generation, and no HumanApproval decisions on
  the live user ledger were made. **Live Gemini acceptance remains gated**
  on a securely connected key, verified model support, explicit
  model-cost ceiling and one intentionally approved smoke test.
