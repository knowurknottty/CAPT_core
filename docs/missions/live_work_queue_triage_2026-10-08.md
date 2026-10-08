# Live CAPT mission triage — 2026-10-08

Read-only snapshot: 2026-10-08T06:21:37+00:00.
Authoritative list_aggregates plus each aggregate get_state (not a truncated projection page). No state changes.

## Actual stored inventory

- Missions: 388. Stored states: {'draft': 24, 'executing': 53, 'authorized': 310, 'completed': 1}.
- Tasks: 455. Stored states: {'pending': 24, 'running': 2, 'suspended': 128, 'awaiting_verification': 236, 'failed': 35, 'cancelled': 9, 'succeeded': 21}.
- DriverRuns: 433. Stored states: {'completed': 295, 'cancelled': 5, 'lost': 126, 'failed': 7}.
- HumanApprovals: 551. Stored states: {'consumed': 425, 'requested': 42, 'approved': 62, 'denied': 22}; derived-stale (not terminal): 59.

## Interpretation

- Mission executing is persisted state, NOT a verified live worker.
- Task or DriverRun running is a stored marker, NOT an external heartbeat.
- Awaiting verification requires actual provider result plus human review.
- Suspended or lost needs durable reconciliation and existing idempotency lineage before retry.
- Full ledger must remain immutable.

## Unfinished mission shortlist

### m-capt-issues-20260924-live
- Stored mission state: executing; task states: {'running': 1}; run states: {}.
- Verify liveness: check CAPT Node / provider worker before declaring it active or shutting runtime down.

### m-muse-plugin-audit-r1-p1
- Stored mission state: executing; task states: {'suspended': 1, 'awaiting_verification': 2}; run states: {'lost': 1, 'completed': 2}.
- Recover: inspect lost/suspended DriverRun evidence and idempotency receipt. Fresh dispatch requires separate authority.
- Review: inspect completed provider output and evidence before explicit human accept/reject.

### m-capt-donor-convergence-r1
- Stored mission state: executing; task states: {'awaiting_verification': 1, 'suspended': 1}; run states: {'completed': 1, 'lost': 1}.
- Recover: inspect lost/suspended DriverRun evidence and idempotency receipt. Fresh dispatch requires separate authority.
- Review: inspect completed provider output and evidence before explicit human accept/reject.

### m-capt-donor-convergence-r1-20260924
- Stored mission state: authorized; task states: {'failed': 3, 'suspended': 12, 'awaiting_verification': 2}; run states: {'failed': 3, 'lost': 10, 'completed': 4}.
- Recover: inspect lost/suspended DriverRun evidence and idempotency receipt. Fresh dispatch requires separate authority.
- Review: inspect completed provider output and evidence before explicit human accept/reject.
- Diagnose: inspect failed attempt before considering repair and retry.

### m-human-manual-marketing-images-r2
- Stored mission state: authorized; task states: {'suspended': 5, 'awaiting_verification': 5}; run states: {'lost': 5, 'completed': 5}.
- Recover: inspect lost/suspended DriverRun evidence and idempotency receipt. Fresh dispatch requires separate authority.
- Review: inspect completed provider output and evidence before explicit human accept/reject.

### m-human-manual-marketing-images-r1
- Stored mission state: authorized; task states: {'suspended': 10}; run states: {'lost': 10}.
- Recover: inspect lost/suspended DriverRun evidence and idempotency receipt. Fresh dispatch requires separate authority.

## Safe cleanup boundaries

- Do not delete or rewrite EventStore or claim history.
- Do not auto-decide HumanApproval or accept unverified provider output.
- Do not mass-retry lost model calls, potentially spending twice.
- Do not force-restart RuntimeService with outstanding running markers.
- Do not invent success or completion events.

## Next engineering gates

1. Per-DriverRun reconciliation with proof-backed reattach/retry UX.
2. Human verification inbox bound to actual execution receipts.
3. Mission closeout operation that proves its success criteria.
4. Continue to show derived task triage separately from persisted mission state.

## Native app remediation status

- Missions: human-first Needs action default, explicit stored-versus-derived status, search, task-state counters, lost-run warnings, read-only task and DriverRun inspector, full history retained.
- Evidence: correct Accepted claims terminology (distinct from independent verification), searchable claims, no automatic promotion.
- Ledger: searchable bounded recent event window, optional decision/result filtering, routine transport hiding without altering immutable history.
- Version identity: CAPT distribution 0.5.0 is separate from checkpoint/runtime compatibility identifier 0.1.0; report both. Do not silently bump the latter or invalidate existing checkpoint manifests.
- 143 Swift tests passed, 9 skipped; full Python tests: 1,965 passed, 70 skipped, 13 deselected.
- RuntimeService was not forcibly restarted while nonterminal DriverRun state remained; source-installed version fields require a safe restart to appear in live identity.
