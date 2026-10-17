# CAPT media routes: OpenRouter foundation (2026-10-17)

## Operator route inventory

The seed script at scripts/seed_verified_media_routes.py installs exactly
two provider-backed media routes in ~/.capt/ui/media-routes.json. Existing
entries are preserved, including disabled Gemini Files examples.
There is NO automatic provider dispatch from the installer.

Adapter openrouter-ming-design-r1: provider openrouter-image,
model inclusionai/ming-image-0.1-design, image_generate,
POST https://openrouter.ai/api/v1/images,
declared cost ceiling $0.00.

Adapter openrouter-deepseek-v41-vision-r1: provider openrouter,
model deepseek/deepseek-v4.1-flash, image_input,
POST https://openrouter.ai/api/v1/chat/completions,
declared cost ceiling $0.05.

IMPORTANT: Declared maximum price is a CAPT authorization boundary, not
independent proof of upstream provider billing. OpenRouter publicly
advertised Ming Design as free at verification time; pricing and
availability may change. Do not assume unlimited free service.

Both routes require an enabled matching registered model/capability,
existing credential reference, allowed network policy, newly issued
one-use HumanApproval, and an explicit Run action. Local quarantine
validates input MIME signatures and digests. Generated media and model
text are untrusted until human verification.

## Operator installation and lifecycle

From the CAPT Core repository, run a dry-run first:
python3 -m scripts.seed_verified_media_routes --ui-root ~/.capt/ui

Only after the preflight succeeds, apply:
python3 -m scripts.seed_verified_media_routes --ui-root ~/.capt/ui --apply

Expected: VALIDATED_DRY_RUN before APPLIED or ALREADY_CONFIGURED.
No model dispatch is performed.

The installer refuses changed adapter identities, absent models,
origin mismatches, missing modality, invalid existing configuration,
symlinks, and concurrent changes. A private timestamped backup is
created before changing the route file.

RuntimeService reads route configuration at startup; a separate
governed controlled reload is required before its media_route_catalog
changes. The script never restarts the daemon.

## Unconfigured media operations

Gemini Files upload and file-reference consumption: gemini-direct
provider not registered, so preserve the existing disabled placeholders.
Audio generation and transcription: no registered capability + exact
transport verified yet. Video generation/polling: no fully verified
registered provider with exact async endpoints. Reference-image
editing/layer extraction is NOT supported by this prompt-only Ming model.

These are deliberate feature gates, not an assertion that media
capabilities do not exist anywhere.

## Validation

Offline model-request fixtures and media runtime socket tests are
distinct from production HTTP delivery. Live usage requires a fresh,
exact HumanApproval and deliberate spend decision. No user media
is uploaded while installing routes.
