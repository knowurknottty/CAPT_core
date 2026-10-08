# CAPT native file and media management — R1 / R2 contracts

**Current status: R1 local staging + digest-bound artifact preview is
implemented and unit-tested. Live multimodal provider upload/generation
is NOT implemented by this change. Do not market R1 as model vision,
audio listening, video understanding, TTS, or video generation.**

## Native intake R1

The Swift Chat composer has a macOS **Attach files** control. The user can
select multiple regular files of *any extension*, up to 16 staged attachments
per chat and **2 GiB per file**. Selected files are streamed into
`~/.capt/native-media-intake/v1/<session-id>/` or the current configured
state root, with private directory permissions (0700), file permissions
(0600), a content SHA-256, original name, provisional MIME/kind, length,
and a stable attachment ID. Source symlinks and directories are refused.
Input media types can be described as image, video, audio, document,
archive, or unknown/binary, but type guesses from extensions are **never**
authority to execute or upload a file.

Attachment metadata is saved in the **encrypted chat session cache**.
The staged file **bytes** are private-permission local copies and are not
individually encrypted; disk-level FileVault may apply but is not a CAPT
media encryption claim. Never assert they are content-safe just because
a picker accepted them.

Native chips show file type/name/size, let the user remove the staged
copy, and invoke macOS Quick Look to preview types supported by the OS.
The file chooser itself is blocking only while the human selects files;
large file copying/hashing runs off the SwiftUI main thread. Original files
are unchanged.

**Explicit safety gate:** While an attachment is in local quarantine,
Send is disabled and the UI says it has **not been sent to a model**.
The workspace independently rejects attempts to submit a prompt that
would silently omit attached bytes. The runtime media input contract
still has to admit the artifact and freeze the exact model/media route
in HumanApproval before model consumption.

## Existing generated-artifact preview R1

CAPT's existing provider driver has a bounded image-output candidate.
A native message may display **Preview artifact** for an image, audio or
video *candidate* found in a DriverRun receipt, but only if:

1. The candidate path is a regular non-symlink local file inside the
   active project or configured CAPT state root.
2. Its stored SHA-256 matches the streamed file bytes and size bound.
3. MIME family is image/audio/video. No raw arbitrary provider-returned
   URL is opened, fetched or rendered automatically.
4. Human explicitly clicks Preview (Quick Look).

The UI labels these results **unverified generated media**. Digest
consistency proves byte identity, **not** factual correctness,
independent verification, safety, ownership, or release admission.
Video/audio **generation endpoints are not added** by this release;
their preview support only consumes properly staged future candidates.

## Provider adapter metadata contract

`capt_runtime/media_adapter_contract.py` introduces a validator for
provider-advertised, typed endpoint shapes:
- Input: image/audio/video/file.
- Output: image/audio/video generation and speech transcription.
- Transport: chat completions, Responses, JSON, multipart, asynchronous
  job/poll/result.
- Output: base64 JSON, provider asset URL, raw binary, multipart, or job receipt.
- Exact host and relative path declarations; rejects foreign origins,
  credentials in URLs, path traversal and unexpected placeholder names.
- Explicit download host allowlists; returning arbitrary media URLs from
  model output does not grant network access or filesystem write rights.
- Max asset sizes are bounded. The validators make **zero network calls**.

This is a **contract precursor** only. No runtime command advertises
general multimodal generation through this validator yet, and no provider
is implicitly enabled by declaring a model name.

## R2 execution gates (next implementation tranche)

1. CAPT EventStore `MediaIntake` aggregate with source path scoping,
   quarantine, content sniffing, malicious-content detection policy,
   immutable checksum, access-control and TTL/deletion receipts.
2. Model/provider capability registry generated from **actual configured
   model+provider**, endpoint schema, context limit, modality direction,
   pricing and operational readiness. Unknown capability -> disabled,
   not speculative fallback.
3. HumanApproval binds exact content digest, target model, provider
   privacy/network policy, number of files and bytes, token cost ceiling,
   output category and destination root. A model's returned instructions
   are untrusted and cannot extend authority.
4. Typed multimodal execution driver input conversion. Support text +
   image blocks, PDF/document processing, audio upload/transcription,
   video frame/file submissions and provider file-id workflows without
   flattening everything into text. Bound local/offline variants separately.
5. Provider-specific output families: images, synchronous speech/audio,
   and **asynchronous video/image** generation with durable job ID,
   polls, expiration, cancellation, reconnect, and unknown-charge
   reconciliation. Different vendors may use `/images/generations`,
   `/responses`, `/audio/speech`, `/videos`, `/jobs/{job_id}`,
   multipart uploads, separate status URLs, or approved nonstandard paths.
   Do not hard-code a universal endpoint.
6. Validate returned download URLs against the provider-specific asset
   host allowlist and transport TLS policy, block redirect-based SSRF,
   stream downloads into governed local staging, hash and cap sizes,
   persist artifact/evidence receipts, then preview only on user action.
7. Model-specific negative and integration tests: offline local models,
   cloud authorization denies, oversized files, symlinks, input/output
   MIME mismatch, deleted source, malformed job receipts, slow video
   polling, duplicate charge prevention, process restart and model
   capability mismatch.
8. R2 production runtime/desktop integration and hands-on VoiceOver/
   keyboard/drag-and-drop/Quick Look tests before launch certification.

## Release policy

R1 is a functional **local intake and preview** milestone, not a
multi-provider media generation release. It does not request paid
inference, modify HumanApproval, or invoke media services. Keep the
legacy image provider adapter behind its existing authority boundaries.

## R1 installation and test acceptance

- Exact committed native source with asynchronous file picker:
  `1da2b5543a25c09ae29c5deb1bba88fa70bac85e`.
- Core Python full suite prior to the final picker-only change:
  **1,998 passed, 70 skipped, 13 deselected** (82.71 s).
  Log `~/capt-node-workspace/native-media-r1-python-full.log`.
  After endpoint-validator hardening, the exact-focused validation suite
  passed **20 tests**. No post-picker Python regression was required
  because this commit changes only Swift view code.
- Exact-source native Swift suite after the picker correction:
  **159 passed, 9 skipped, 0 failed**.
  Log `~/capt-node-workspace/native-media-nonblocking-test.log`.
- Signed Swift CAPT.app 0.5.0 installed at `~/Applications/CAPT.app`;
  verified strict Apple signing and executable byte equality with the
  clean staged build. Executable SHA256:
  `b6057a1bbedf50a2972fdcee95d2c6885a5b55239c2590dffc40f95e0185216c`.
- TIA activated the installed app, observed an enabled native
  **Attach files** accessibility button, and successfully pressed
  it using the nonblocking macOS panel implementation.
  Full manual file selection was **not** completed through TIA;
  source-level tests stage arbitrary files, preserve SHA-256 and file
  permissions, and verify removal without model dispatch.
- One installed CAPT app process was observed; returned to **0% CPU
  while idle** after the picker interaction. Resident RuntimeService
  stayed HEALTHY, integrity `ok`, EventStore head 23497.
- A temporary picker opened during the TIA test was dismissed.
  No paid model requests, media generation, GitHub issue mutations,
  or HumanApproval decisions were made by this acceptance.

**Disposition:** Native local media intake, preview and typed provider
adapter metadata R1 shipped. Real provider media uploads/async outputs
remain R2 implementation gates, not accepted tests.
