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

Workers AI models requiring paid billing are denied under `free_only`, including current GLM-5.3/GLM-5.3-Flash, DeepSeek V4 Flash/Pro, Kimi K2.6/K2.7 Code, and GLM-5.2. Having credentials or prepaid credits does not create economic authority.

Cloudflare Sandbox/Containers remain `free_tier_eligible=false` by default. Localhost bridge testing is admissible because it incurs no provider usage; remote Sandbox execution remains blocked until $0 eligibility is independently proven or explicit human paid authority exists.

## Free-Native Execution Strategy

CAPT routes free-admissible cloud work to typed native surfaces before considering arbitrary compute: coordination -> Workers, durable delegation -> Queues, shared bounded state -> D1, browser work -> Browser Run, and eligible inference -> Workers AI. `arbitrary_compute` has no free-native fallback and is denied rather than silently routed to Sandbox/Containers.

`CloudflareFreeTierRouter` performs deterministic surface selection and per-surface budget checks. `CloudflareUsageLedger` persists operation-scoped reservations transactionally so concurrent Bots cannot oversubscribe the same daily free allocation. Reservation identity binds operation ID, work class, estimate, and date; the same operation with a different estimate is an integrity violation.

Provider dispatch follows `reserve -> dispatch -> classify -> commit | release | indeterminate`. A reservation is released only when CAPT can prove dispatch never started. Proven provider completion commits usage. Lost/ambiguous responses keep the reservation locked for reconciliation; uncertainty never becomes permission to retry.

Typed native executors currently exist for Workers coordination, Queue delegation, D1 read/write, Browser Run, and Workers AI. Provider-reported actual usage is evidence. If reported usage exceeds the CAPT-authorized estimate, the operation becomes a specific accounting indeterminacy rather than widening economic authority after the fact.
