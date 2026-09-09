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

The free-native execution bundle can be constructed only from an explicit `CloudflareNativeAPIProfile`. The profile contains account/resource identifiers and environment-variable names, never API-token or Worker-secret values. The bridge resolves secrets at call time and does not serialize them into results, receipts, or profile state.

Cloudflare account API authority and Worker invocation authority are separate credential domains. Queue, D1, Browser Rendering, and Workers AI calls use the configured account API token; coordination Worker calls use a distinct Worker bearer-secret reference.

The bridge is existing-resource-only. It can address configured Queue IDs and D1 database IDs and the fixed account endpoints for Browser Rendering and Workers AI; it contains no create/delete/deploy API methods. Browser actions are a closed vocabulary: `content`, `scrape`, `screenshot`, and `pdf`. Queue effect identity is CAPT-owned (`capt:<operationId>`) because Cloudflare Queue push does not provide a durable provider message ID in the push response.

D1 provider metadata supplies actual `rows_read` and `rows_written` evidence. Browser Run and Workers AI currently account conservatively at the pre-authorized CAPT estimate when the REST response does not expose a reliable free-quota usage counter. These estimates are reservations/ceilings, not claims of provider-measured consumption.

## Free-Native Hardening Closure

Quota admission is serialized at the SQLite transaction boundary with `BEGIN IMMEDIATE`, not merely by an in-process lock. Independent runtime/ledger connections therefore cannot reserve the same remaining free-tier budget concurrently.

The reservation bucket date is derived from the planner's timezone-aware UTC clock. A caller-supplied date is advisory only when it exactly matches that trusted date; mismatches are rejected as `CLOUDFLARE_QUOTA_DAY_UNTRUSTED`. Bots cannot move usage into a future quota bucket.

Existing-resource API failures that are provably pre-dispatch—missing secret references, unconfigured Queue/D1 resources, or invalid Worker routes—raise `CloudflareDispatchNotStarted`, allowing the reservation to be released. Transport or provider-outcome ambiguity after dispatch remains locked and becomes `CloudflareNativeIndeterminate`.

Browser/Workers-AI metering carries an explicit `usageBasis`: `provider_reported` or `reserved_ceiling`. CAPT never relabels its estimate as provider measurement. Browser `content` and `scrape` results receive SHA-256-bound artifact identities. `pdf` and `screenshot` are intentionally blocked before dispatch until binary artifact capture/evidence spooling is implemented.


## Workers AI Catalog Authority Closure

The account-scoped Model Search endpoint is read-only control-plane discovery. `CloudflareNativeAPIBridge.ai_model_catalog()` uses authenticated GET requests only, validates pagination, excludes deprecated models, and converts the complete result into `CloudflareAIModelCatalogSnapshot`. Partial, malformed, empty, stale, clock-inconsistent, or model-missing catalogs fail closed before quota reservation or inference dispatch.

The free-only admission order is `discover catalog -> validate provenance/freshness -> classify model billing -> transactional quota recheck/reservation -> inference dispatch`. The SQLite recheck receives the same immutable catalog snapshot and timestamp; concurrency protection therefore cannot weaken the billing gate. A reservation digest binds the catalog source digest as well as operation, work class, estimate, and trusted UTC quota day.

Live read-only validation on 2026-09-09 parsed the current Wrangler/Cloudflare catalog successfully: 65 models total and 7 marked `require_workers_paid`, matching the current provider pricing list. No inference was invoked during this validation.
