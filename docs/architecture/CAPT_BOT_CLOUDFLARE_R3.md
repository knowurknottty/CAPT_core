# CAPT Bot Cloudflare Execution Plane R3

## Goal

R3 adds Cloudflare as an optional governed execution backend without moving CAPT authority, cognition, evidence, or verification into Cloudflare.

The integration target is Cloudflare's supported Sandbox Bridge HTTP API. CAPT remains the control plane; the bridge is a remote execution transport backed by Workers, Durable Objects, and Containers.

## Boundary

`ToolRequest -> ToolBroker -> CloudflareTerminalToolAdapter -> CloudflareSandboxBackend -> Sandbox Bridge`

The bridge receives only the already-admitted argv, cwd, timeout, and sandbox operation. Capability grants, Bot policy, approval state, secrets provenance, WORLD RECEIPT, and ClaimGuard remain CAPT-owned.

R3 does not permit a Bot to choose Cloudflare merely because Cloudflare is configured. Locality policy and the normal capability/ToolBroker admission path remain prerequisites.
## Security invariants

1. `backendId=cloudflare` is explicit and contract-validated.
2. A ToolRequest `targetIdentity` names a CAPT Cloudflare profile, never a raw URL or token.
3. Profiles store only an environment-variable reference for the bridge API key.
4. Production bridge URLs must use HTTPS; localhost HTTP is allowed only for local development.
5. Remote filesystem scope is confined to profile-approved roots, initially `/workspace` by default.
6. R3 uses ephemeral sandboxes by default and attempts destruction after every execution.
7. Transport failure after dispatch is indeterminate, not success/failure fabrication.
8. Cleanup failure is surfaced in the ToolResult and side-effect identity.
9. Bridge credentials are never emitted to ToolResult, logs, receipts, or Bot state.
10. Cloudflare execution never grants additional network/filesystem/credential authority by itself.
## Verified Free-Tier Envelope — 2026-09-08

CAPT treats Cloudflare's public Free-plan ceilings as provider limits, not spending permission. Default internal admission reserves 10% headroom and blocks before provider exhaustion: Workers 90,000 requests/day with 10 ms CPU/request hard provider ceiling; Queues 9,000 operations/day; Browser Run 540 seconds/day; Workers AI 9,000 neurons/day; D1 4.5M rows read/day and 90,000 rows written/day.

Provider ceilings verified on 2026-09-08 are Workers 100,000 requests/day, Queues 10,000 operations/day with 24-hour Free retention, Browser Run 600 seconds/day, Workers AI 10,000 neurons/day, and D1 5M rows read plus 100,000 rows written/day. These values are policy inputs and must be reverified before future release snapshots.

Workers AI model billing admission is provider-metadata-bound, not name-list-bound. Before neuron reservation, CAPT requires a fresh Cloudflare Model Search snapshot, verifies the requested model is present, evaluates its `require_workers_paid` property, and rejects stale/unknown/paid-required status under `free_only`. The immutable snapshot carries a fetch timestamp and SHA-256 source digest; that digest is included in the reservation identity and returned inference provenance. Having credentials, a Workers Paid plan, or prepaid credits does not create economic authority.

Cloudflare Sandbox/Containers remain `free_tier_eligible=false` by default. Localhost bridge testing is admissible because it incurs no provider usage; remote Sandbox execution remains blocked until $0 eligibility is independently proven or explicit human paid authority exists.

## Free-Native Execution Strategy

CAPT routes free-admissible cloud work to typed native surfaces before considering arbitrary compute: coordination -> Workers, durable delegation -> Queues, shared bounded state -> D1, browser work -> Browser Run, and eligible inference -> Workers AI. `arbitrary_compute` has no free-native fallback and is denied rather than silently routed to Sandbox/Containers.

`CloudflareFreeTierRouter` performs deterministic surface selection and per-surface budget checks. `CloudflareUsageLedger` persists operation-scoped reservations transactionally so concurrent Bots cannot oversubscribe the same daily free allocation. Reservation identity binds operation ID, work class, estimate, and date; the same operation with a different estimate is an integrity violation.

Provider dispatch follows `reserve -> dispatch -> classify -> commit | release | indeterminate`. A reservation is released only when CAPT can prove dispatch never started. Proven provider completion commits usage. Lost/ambiguous responses keep the reservation locked for reconciliation; uncertainty never becomes permission to retry.

Typed native executors currently exist for Workers coordination, Queue delegation, D1 read/write, Browser Run, and Workers AI. Provider-reported actual usage is evidence. If reported usage exceeds the CAPT-authorized estimate, the operation becomes a specific accounting indeterminacy rather than widening economic authority after the fact.

## Existing-Resource Native API Bridge

The free-native execution bundle can be constructed only from an explicit `CloudflareNativeAPIProfile`. The profile contains the Cloudflare account identity, Worker endpoint/alias, and environment-variable names, never Queue/D1 provider IDs, API-token values, or Worker-secret values. Non-empty raw Queue/D1 ID maps are rejected as `CLOUDFLARE_NATIVE_RAW_RESOURCE_IDS_FORBIDDEN`. The bridge resolves secrets at call time and does not serialize them into results, receipts, or profile state.

Cloudflare account API authority and Worker invocation authority are separate credential domains. Queue, D1, Browser Rendering, and Workers AI calls use the configured account API token; coordination Worker calls use a distinct Worker bearer-secret reference.

The bridge is existing-resource-only. Queue, D1, and coordination-Worker targets are resolved immediately before dispatch from CAPT EventStore `CloudflareResourceBinding` state; configuration cannot supply provider IDs as authority. Browser Rendering and Workers AI use their fixed account endpoints and remain subject to their separate free-tier/catalog gates. The bridge contains no create/delete/deploy API methods. Browser actions are a closed vocabulary: `content`, `scrape`, `screenshot`, and `pdf`. Queue effect identity is CAPT-owned (`capt:<operationId>`) because Cloudflare Queue push does not provide a durable provider message ID in the push response.

D1 provider metadata supplies actual `rows_read` and `rows_written` evidence. Browser Run and Workers AI currently account conservatively at the pre-authorized CAPT estimate when the REST response does not expose a reliable free-quota usage counter. These estimates are reservations/ceilings, not claims of provider-measured consumption.

## Free-Native Hardening Closure

Quota admission is serialized at the SQLite transaction boundary with `BEGIN IMMEDIATE`, not merely by an in-process lock. Independent runtime/ledger connections therefore cannot reserve the same remaining free-tier budget concurrently.

The reservation bucket date is derived from the planner's timezone-aware UTC clock. A caller-supplied date is advisory only when it exactly matches that trusted date; mismatches are rejected as `CLOUDFLARE_QUOTA_DAY_UNTRUSTED`. Bots cannot move usage into a future quota bucket.

Existing-resource API failures that are provably pre-dispatch—missing secret references, unconfigured Queue/D1 resources, or invalid Worker routes—raise `CloudflareDispatchNotStarted`, allowing the reservation to be released. Transport or provider-outcome ambiguity after dispatch remains locked and becomes `CloudflareNativeIndeterminate`.

Browser/Workers-AI metering carries an explicit `usageBasis`: `provider_reported` or `reserved_ceiling`. CAPT never relabels its estimate as provider measurement. Browser `content` and `scrape` results receive SHA-256-bound artifact identities. Binary `pdf` and `screenshot` responses are captured only when a runtime-owned private artifact spool is present; absent spool state fails before secret resolution or provider dispatch.


## Workers AI Catalog Authority Closure

The account-scoped Model Search endpoint is read-only control-plane discovery. `CloudflareNativeAPIBridge.ai_model_catalog()` uses authenticated GET requests only, validates pagination, excludes deprecated models, and converts the complete result into `CloudflareAIModelCatalogSnapshot`. Partial, malformed, empty, stale, clock-inconsistent, or model-missing catalogs fail closed before quota reservation or inference dispatch.

The free-only admission order is `discover catalog -> validate provenance/freshness -> classify model billing -> transactional quota recheck/reservation -> inference dispatch`. The SQLite recheck receives the same immutable catalog snapshot and timestamp; concurrency protection therefore cannot weaken the billing gate. A reservation digest binds the catalog source digest as well as operation, work class, estimate, and trusted UTC quota day.

Live read-only validation on 2026-09-09 parsed the current Wrangler/Cloudflare catalog successfully: 65 models total and 7 marked `require_workers_paid`, matching the current provider pricing list. No inference was invoked during this validation.


## Read-Only Resource Inventory and Adoption Boundary

Cloudflare resource discovery is informational, not authority. `CloudflareNativeAPIBridge.resource_inventory()` performs authenticated GET-only discovery for D1 databases, Queues, and Worker scripts. D1 pagination must be complete and all provider rows must resolve to typed kind + provider ID + name identities before a snapshot is accepted. The snapshot binds account ID, timezone-aware fetch time, canonical resource identities, and a SHA-256 source digest.

Every discovered `CloudflareResourceCandidate` is immutable with `adopted=false` and `adoptionAuthority=human_required`. Name lookup is convenience only: duplicate names are `CLOUDFLARE_RESOURCE_NAME_AMBIGUOUS`, and a provider ID/name disagreement is `CLOUDFLARE_RESOURCE_ID_NAME_MISMATCH`. The bridge exposes no resource-adoption, resource-create, deploy, update, or delete method. Discovery therefore cannot silently convert an old CAPT-looking Cloudflare resource into an execution target.

Live read-only Wrangler discovery on 2026-09-09 observed 8 D1 databases with typed UUID/name identity and 0 Queues. Wrangler 4.90.0 does not expose an account-wide Worker-script list command in its top-level CLI, so Worker inventory was not live-observed through Wrangler and is explicitly not represented as empty. The direct Worker list endpoint remains API-contract and test verified. No discovered resource has been adopted by this tranche.


## Human Resource Adoption Closure

Discovery never becomes execution authority by itself. `CloudflareResourceAdoptionProposal` binds one exact inventory snapshot, account, typed resource kind, provider ID, provider name, CAPT alias, and proposal digest. Worker-script adoption additionally binds the exact approved HTTPS Worker endpoint; Queue and D1 proposals may not carry an endpoint.

A proposal is converted into an existing `HumanApprovalRequest` with `operation=CloudflareResourceAdoption`, `requestedCapability=cloudflare.resource.adopt`, `remainingUses=1`, and the exact adoption binding in scope. Only a human actor can approve it. The irreversible bind path is an atomic EventStore command: the approval stream receives `CloudflareResourceAdoptionApprovalConsumed` while a `cloudflare_resource_binding-*` stream receives `CloudflareResourceBindingCreated`. A crash cannot consume the one-use approval without creating the binding, or create a binding without consuming the approval.

`CloudflareResourceBindingRegistry` resolves only active durable bindings and revalidates each binding SHA-256 before returning it. Queue and D1 provider IDs come from this registry, never profile maps. Coordination Worker dispatch requires both the adopted Worker-script alias and an exact endpoint match before secret lookup or network dispatch. Missing, ambiguous, corrupt, or endpoint-mismatched bindings fail pre-dispatch and therefore cannot consume Cloudflare quota. Full event-ledger replay reconstructs both the consumed approval and the resulting binding.

No live Cloudflare resource was adopted while implementing this closure. The eight previously observed D1 databases remain unadopted discovery candidates, and no Queue or Worker was created or deployed.


## Browser Binary Evidence Closure

Browser Run `screenshot` and `pdf` use a separate bounded binary response path rather than the JSON response decoder. Screenshot requests explicitly select `encoding=binary`; PDF consumes the raw PDF response. Provider content type is part of the evidence contract: screenshots accept only PNG/JPEG/WebP media types and PDF accepts only `application/pdf`. A mismatched or otherwise unclassified response occurs after dispatch and is therefore indeterminate; the Browser quota reservation remains locked for reconciliation.

`CloudflareBinaryArtifactSpool` is runtime-owned at `<ledger>.cloudflare-artifacts`, with a private `0700` directory and `0600` artifact/metadata files where supported. Binary artifacts are capped at 32 MiB, receive an opaque `cloudflare-artifact://` identity, SHA-256 digest, byte count, media type, action, and operation binding. Reads are limited to 64 KiB per request and reject wrong-operation access. Each read revalidates file size, metadata/token identity, and content SHA-256 before returning base64-encoded bytes, so same-size local corruption is detected.

`CloudflareBrowserResult` preserves the binary manifest rather than collapsing it to an untyped reference. Runtime composition creates the spool only when the native Cloudflare profile is enabled and injects the same instance into the native API bridge. `content` and `scrape` semantics are unchanged. No live Browser Run request was made while implementing or verifying this closure.

## R4 Workflows orchestration extension

Cloudflare Workflows is added in `CAPT_BOT_CLOUDFLARE_WORKFLOWS_R4.md` as a free-native **durable orchestration** surface only. It does not make `ARBITRARY_COMPUTE` routable and does not enable Sandbox/Containers. Workflow discovery/adoption uses the existing human-bound resource provenance path; instance start/status/event/step-evidence use typed operations, CAPT-owned deterministic instance identity, quota reservation, and reconciliation-before-retry semantics. CAPT/EventStore remains authoritative for mission/task completion.
