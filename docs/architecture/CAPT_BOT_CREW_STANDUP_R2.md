# CAPT Bot Crew + Standup R2

## Goal

R2 turns the R1 Bot substrate into an inspectable lab crew without creating a second execution or authority plane.

## Delegate Assignment

A persistent `crew` Bot, or an already-active `delegate` Bot acting within its inherited delegation envelope, may create work for a registered `delegate` Bot only through a durable Delegate Assignment. The assignment binds:

- parent Bot identity
- delegate Bot identity
- Mission identity
- optional Task identity
- spawn depth
- creation and expiry timestamps
- lifecycle state

The assignment is coordination state only. It never grants filesystem, network, provider, credential, tool, or capability authority.

## Invariants

1. Parent and delegate Bots must already exist.
2. Target must be `delegate`; a delegate parent must itself have exactly one active, unexpired parent assignment in the same Mission.
3. Parent collaboration policy must permit delegation.
4. Delegate Mission binding must equal the assignment Mission.
5. A Task-scoped assignment must reference an existing Task belonging to the same Mission.
6. Assignment depth must equal the parent depth + 1 and must not widen any ancestor's effective `maxSpawnDepth` ceiling.
7. A delegate identity may not hold two simultaneous active assignments in the same Mission.
8. `expiresAt` must be later than `createdAt`; creation actor/time are bound to the admitting command.
9. Expired/revoked/completed assignments are terminal; revocation/expiry require human, governance, or system authority.
10. Assignment replay must reconstruct identical authoritative state, while capability grants remain a separate prerequisite for consequential execution.

## Lifecycle

`active -> completed | revoked | expired`

Completion records coordination completion only; it does not prove mission/task completion. Existing evidence, verification, and ClaimGuard paths remain authoritative for completion claims.

## Standup projection

`build_lab_standup()` is a read-only deterministic projection over current EventStore aggregate snapshots. It surfaces:

- persistent crew
- active delegate assignments
- human tasks
- human requests
- human-only blockers
- ready work
- active work
- verifying work
- waiting-on-agent work
- completed board items
The projection contains no secrets, leases, raw credentials, or hidden authority. It is an operator/UX surface derived from authoritative state, never a writer.

## Explicit non-goals

R2 does not implement Bot chat UI, scheduled standups, browser/cloud workers, call-scoped delegates, autonomous capability creation, automatic skill activation, or completion claims. Those remain downstream tranches.
