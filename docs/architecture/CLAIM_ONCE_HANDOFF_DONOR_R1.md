# Claim-once handoff primitive — donor adaptation R1

**Status:** source-tested optional CAPT Core primitive. No production route, UI action, model tool, or automatic memory write created.

**Donor:** `akitaonrails/ai-memory` (MIT), `b18f22a7c2f3068575c70d37f13d167fed3476bb`, specifically its typed, owner-attributed, claim-once cross-harness handoff **contract**. This is an independent CAPT adaptation, not a Rust translation or source copy.

**Source:** `capt_runtime/memory/claim_once_handoff.py`. An internal SQLite-WAL record contains only `handoff_id`, issuer/target, source SHA-256 digest, creation/expiry state and single claim key. It does *not* admit a memory, copy a prompt body, authorize a CAPT action, or supersede RuntimeService's EventStore. Restrict SQLite file path with owner-only OS permissions.

## Guarantees tested

- An existing ID never changes owner or source digest.
- A claim is serialized under `BEGIN IMMEDIATE`: among concurrent *different claim keys*, only one succeeds.
- The same authenticated claimant replaying the same idempotency key receives `replayed=True` without a second claim.
- Wrong principal, digest mismatch, revoked, expired and already claimed requests refuse without consuming an open handoff.
- Claims and replays survive closing and reopening the database; owner-only mode enforced on its local SQLite file.
- Revocation is limited to the stored issuer and only before successful claim.

## Crucial integration requirements (not satisfied in R1)

- The module accepts `principal` and `issuer` as validated strings, **not authenticated identities**. These MUST come from trusted RuntimeService operator/session authentication and scope policy, never a ChatGPT OAuth client ID or a user-supplied tool argument.
- A source digest is a *pointer integrity check*, not evidence admission or approval. RuntimeService must resolve and recheck the referenced memory against consent, stale/revoked state, provenance, and per-recipient policy at retrieval time.
- All admission/revocation/claim status that can change consequential action must be projected into the authoritative CAPT EventStore; the optional handoff database alone does not satisfy this requirement.
- Only expose claim to pre-authorized destinations and preserve operator-level handoff ownership across agent implementations. A model seeing handoff metadata never acquires shell/filesystem/network rights.
- No automatic source deletion, copying private data to cloud providers, background model call, or authorization inheritance.
- Durability is local SQLite, **not replicated cross-device mesh**. Distributed claim-once across Puter or multiple CAPT Nodes requires a single authoritative coordinator and atomic cross-device compare-and-swap.
- Deleting an existing source must invalidate the associated handoff even if its digest is unchanged; provide external revocation callback or an admission recheck before handoff delivery.

## Tests and limitations

`tests/capt_runtime/test_claim_once_handoff.py` uses ephemeral SQLite stores under pytest temporary directories and 20 cases, including concurrency, restart/replay, unauthorized claim, revoked, expiry, digest mismatch, file permission, and no transcript-body column.

Not yet integrated with real OperatorControl, CAPT continuations or HMC/ENGRAM. No production promotion until authorized identity is proven, EventStore ownership is documented, and end-to-end test runs with two independent sessions. The memory donor design notes remain in bioCAPT Theta PR #6.

## Suggested next step

Implement an event-sourced CAPT `handoff.offer` / `handoff.claim` projection behind RuntimeService's existing authenticated operator/session boundary, then expose only sanitized, scope-approved context pointers to CAPT Bot, Hermes, and Codex. Never let the handoff store itself mint authority.
