# CAPT Hardening Backlog

Weak spots and holes found while integrating CAPT Core with a Hermes host, plus the
enhancement each one wants.

**Provenance discipline** — every item is tagged:

- **[V]** *Verified directly.* Observed against the live runtime or read in source
  during the integration session. A command or file:line is quoted.
- **[R]** *Reported.* Source-grounded with file:line from a read-only analysis pass,
  but **not independently re-verified by the integrator**. Confirm before spending
  time on the fix; treat as a lead, not a fact.

CAPT's own AGENTS.md standard applies throughout:
`source present -> tested -> integrated -> installed -> live dependency proven`.
An item marked [R] has reached *source present* at best.

Baseline: CAPT Core HEAD `a4343e8`, live runtime head `2960`, memory policy v9.

---

## A. Governance reachability — an external host cannot do the thing

### H-1 [V] The capability lifecycle cannot be driven by any external host
**Symptom.** The live `capabilities` query advertises 21 `commandOperations`.
Among all capability acts it lists exactly one: `revoke_capability`. There is no
`issue_grant`, `activate_lease`, `reserve_use`, or `finalize_use`.
**Evidence.** Live `capabilities` query output; `capt_runtime/services.py:588-778`
implements all five with fixed actor kinds (`governance_kernel` / `execution_plane`).
**Why it matters.** The grant -> lease -> reserve -> finalize state machine is CAPT's
central governance primitive, and no host can exercise it. A host can only watch it
and revoke. Any integration promising "governed capability issuance from the host"
is promising something the surface does not offer.
**Enhancement.** Decide and document the intent. Either (a) expose grant/lease
acts over IPC behind an explicit `governance_kernel` actor claim that the envelope
cannot forge, or (b) declare issuance internal-only by design and add a read-only
projection so hosts can *observe* the lifecycle they cannot drive. (b) is smaller
and needs no new authority surface. Do not leave it ambiguous — the ambiguity is the
bug.

### H-2 [V] No read op exposes approvals, missions, or tasks
**Symptom.** Probing the live runtime, the ops `list_approvals`, `approvals`,
`pending_approvals`, `list_missions`, `missions`, `get_missions`, `list_tasks`,
`tasks` all return `unknown op`.
**Evidence.** Direct probe of the live socket; the read surface is
`identity, capabilities, list_aggregates, get_state, get_stream_events,
event_timeline, replay_state_at, claimguard, verification, get_memory_policy,
get_memory_state, mcp_servers, managed_skills`.
**Why it matters.** There are 21 command ops for creating and transitioning this
state and almost no query op for reading it. An operator (or a host UI) can command
but not inspect — which makes the "human review" story hard to deliver, and forces
`get_stream_events` + client-side aggregation as the workaround.
**Enhancement.** Add read projections: pending approvals (with expiry), missions
with state, tasks by mission. This is the highest-value, lowest-risk item in the
backlog: pure read, no new authority.

**DONE** — ops `approvals`, `missions`, `tasks` in `desktop/capt_runtime_service.py`,
advertised in `capabilities`; covered by `tests/capt_runtime/test_read_projections.py`.
Stored `state` is returned verbatim and expiry is DERIVED (`expired`,
`derivedStale`), because the runtime never drives the `expired` transition.
Verified against a snapshot of the live ledger: 161 approvals, of which
**18 are past-due but still stored as `approved`/`requested`** — H-5 demonstrated
at real scale, and invisible to every read surface before this.

### H-3 [V] No read op exposes checkpoints
**Symptom.** `list_checkpoints`, `get_checkpoints`, `checkpoint_timeline`,
`query_checkpoints` all return `unknown op`. Verifying that a checkpoint persisted
required opening `~/.capt/runtime.db` read-only and querying the `checkpoints`
table by hand.
**Evidence.** Direct probe; the table exists (`checkpoint_id, manifest_json,
integrity_digest, global_sequence`) and grew 103 -> 104 across a write.
**Why it matters.** A checkpoint is the recovery handle, and the only way to confirm
one landed is to bypass the runtime and read SQLite — exactly what CAPT's AGENTS.md
forbids for state *access*. Any host that wants to prove a checkpoint succeeded
today has to violate the boundary.
**Enhancement.** Add a read-only checkpoint projection (id, createdAt,
globalSequence, integrityDigest, recoveryState). Manifests stay sealed; ids and
digests are already the documented recovery surface.

**DONE** — op `checkpoints` plus `EventStore.list_checkpoints(limit)`
(`capt_runtime/store.py`). The store reads only its own columns; `createdAt` /
`recoveryState` / `canDispatchConsequential` require the sealed manifest and are
loaded per row, and integrity is RE-VERIFIED via `verify_checkpoint()` rather
than trusted from the stored digest. `detail: false` returns the cheap
column-only form. Verified live: 3 checkpoints listed at seq 2960, recovery
`clean`, integrity verified.

### H-4 [V] `capabilities` advertises more ops than the live service reports
**Symptom.** Source advertises **26** command ops; the live `capabilities` query
returned **21**. Four ops (`steer_deliberation`, `revoke_capability`,
`create_replay_fork`, plus one decorator-handled op) bypass the base `_VALID_OPS`
list because decorator services intercept them first.
**Evidence.** Live output vs `desktop/capt_runtime_service.py:666` and
`desktop/m1_command_service.py:46-70`.
**Why it matters.** The advertised surface and the executable surface disagree. A
host built against the advertisement will discover missing ops only at call time.
This may also mean the running build predates the source — which is itself worth
knowing.
**Enhancement.** Make `capabilities` derive the op list from the live dispatch path
rather than a hardcoded tuple, and have it report the build identity so drift is
visible instead of inferred.

**CORRECTED — this is not a hardcoded-list bug; the running runtime is a STALE
BUILD.** Source advertises 26 command + 17 query ops; the live runtime returned
21 + 13. The difference is exactly the newest ops on each side (`operator_chat_new`,
`operator_execution_config_set`, `operator_prompt_submit`, `operator_proposal_select`,
`submit_provider_result_review`; `operator_control_snapshot`, `operator_session_get`,
`operator_proposal_get`, `operator_execution_state`). No code change is required —
the fix is a runtime restart on current source. The residual work is therefore the
second half only: report a build identity (version/commit) from `capabilities` so
stale-build drift is visible rather than inferred from an op count.

---

## B. Declared-but-undriven state machines

*Pattern: the contract declares a state or event that no code ever produces. Each
one is a latent correctness trap because a reader will assume it works.*

### H-5 [R] Approval expiry is never driven
**Symptom.** `HumanApprovalAggregate.mark_expired` is defined and **never called**.
There is no `HumanApprovalExpired` event type. The `expired` state and the
`approved -> expired` edge are declared but nothing produces them; expiry is only
enforced lazily as a refusal at approve/consume time.
**Evidence.** `capt_runtime/aggregates/human_approval.py:141-146`;
`capt_runtime/services.py:1135-1136`.
**Why it matters.** An approval past its window stays `approved` in the ledger
forever. Reports built on approval state will show stale approvals as live.
**Enhancement.** Either drive expiry (a sweep on read, or a lazily-persisted
transition when a stale approval is observed) or remove `expired` from the contract
and document lazy refusal as the actual semantics. Silence is worse than either.

### H-6 [R] `CapabilityState` declares `reserved` and `expired`; neither is assigned
**Symptom.** The schema declares both; `CapabilityAggregate` never assigns them.
`reserve()` leaves `grantState='leased'`. `CapabilityAggregate.expire()`
(`aggregates/capability.py:352-362`) has **no caller** and no `CapabilityExpired`
event exists.
**Why it matters.** Same trap as H-5, on the capability axis. A host reading
capability state cannot distinguish "lease active" from "uses reserved", and expired
grants never transition.
**Enhancement.** Drive `expired` from `validUntil` (deterministically, so replay
agrees), and either assign a real `reserved` state on reserve or drop it from the
contract.

### H-7 [R] Mission and driver-run transitions have no actor-kind gate
**Symptom.** `transition_mission` (`services.py:483-516`), `create_driver_run`
(`923-946`) and `transition_driver_run` (`948-973`) call `require_authority()` for
no act — they validate only `CommandMetadata`. By contrast `transition_task`,
`cancel_task`, `cancel_driver_run`, `request_human_approval` and
`submit_human_approval_decision` do call it.
**Why it matters.** In a deny-by-default authority model, the un-gated paths are the
interesting ones. Mission and driver-run state changes are reachable by any
authenticated actor.
**Enhancement.** Add explicit acts (`transition_mission`, `create_driver_run`,
`transition_driver_run`) to the authority table with the intended actor kinds. This
is a small, high-value hardening change.

### H-8 [R] `security_rejections` misses the refusal class that matters most
**Symptom.** Exactly two producers exist in-repo:
`unauthenticated_ipc_attempt` and `provider_spend_threshold_alert`. An operator
command whose envelope carries a foreign `operatorId`/`sessionId` is refused as
`rejected`/`unauthorized` and writes **no** rejection row. `rejection_kind` is
unconstrained TEXT with no CHECK.
**Evidence.** `desktop/m1_command_service.py:123-136,219-229`;
`store.py:79-90,642-662`; repo-wide grep for `record_security_rejection`.
**Why it matters.** Identity-spoofing attempts — the most security-relevant refusal
— leave no audit trace, while a missing token does.
**Enhancement.** Record a rejection for envelope identity failures (kind e.g.
`unauthorized_envelope_identity`) with the presented vs bound ids recorded as
digests, never raw. Also constrain `rejection_kind` to a known set so the audit
surface is queryable.

---

## C. Context + memory — inert machinery

*This cluster is why CAPT's context pipeline should NOT be adopted wholesale by a
host. It is the strongest argument for the "one context engine" rule.*

### H-9 [V] `context_pipeline` is dead code
**Symptom.** `run_pipeline`, `build_context_slice_stage` and `package_context_pack`
have **no runtime callers**. A repo-wide search finds them only in themselves, a
probe script, tests, and docs — no `services.py`, no `desktop/`, no `driver_host.py`.
**Evidence.** Direct file search; corroborates `capt_runtime/context_pipeline.py`.
**Why it matters.** The five-stage pipeline (knowledge bubble -> selection ->
reduction -> slice -> pack) is the documented architecture, and the live path does
not use it. Anyone integrating "CAPT's context pipeline" integrates a corpse.
**Enhancement.** Either wire it into the live retrieval path or move it to
`experimental/` with a docstring saying it is unshipped. The current state — a
well-documented dead path — is the worst option because it reads as load-bearing.

### H-10 [V] `context_merkle` is unused and self-declared non-authoritative
**Symptom.** No runtime caller (same search); the module declares
`authority='provenance_only'`, `replacesContextPackDigest=False`,
`providerCacheHitClaim=False`.
**Why it matters.** It cannot serve as an invalidation or cache-correctness signal
for any live path. Fine as a tool, dangerous as an assumption.
**Enhancement.** Same as H-9: wire or quarantine. If it is intended to localize
change for cache invalidation, add the benchmark that proves it does.

### H-11 [R] Three memory-policy fields are declared and never referenced
**Symptom.** `trust_threshold` and `project_scope` are declared on
`MemoryStore.query` and never referenced anywhere else in the file — no SQL filter,
no Python filter. `contextUsageAfter` is computed as
`context_usage_before + sum(... over an empty list)`, so it always equals
`contextUsageBefore` — and is still hashed into the pack digest.
**Evidence.** `capt_runtime/memory/store.py:265-310`;
`capt_runtime/memory/contextpack.py:132-134,126-128`.
**Why it matters.** A caller passing `trust_threshold` believes retrieval is
filtered by trust. It is not. A digest that includes a field which can never vary
gives false confidence in pack identity.
**Enhancement.** Implement the filters or remove the parameters. Compute
`contextUsageAfter` from the selected records, or drop it from the digest input.

### H-12 [R] Non-retrieval triggers latch a flag and do nothing
**Symptom.** The engine sets `compression_fired` / `checkpoint_fired` /
`consolidation_fired` and no compression, checkpoint-write or consolidation routine
is invoked on firing. Only retrieval produces an artifact (the ContextPack).
**Evidence.** `capt_runtime/memory/engine.py:216-228`; repo-wide grep for the flags
finds consumers only inside `accounting.py`'s own evaluation.
**Why it matters.** The policy is advertised as four triggers with budgets; three
of them are decorative. Budgeting and enforcement stories built on them are
inaccurate.
**Enhancement.** Wire the three actions, or reduce the policy to the one trigger
that exists and say so. Prefer the honest reduction until each action is real.

### H-13 [R] Triggers fire only on exact multiples, and trigger state is not persisted
**Symptom.** `_fires` computes a boundary from the current value and tests
`current >= boundary` against that same value — effectively a boundary-equality
test, not "crossed since last check". Usage that jumps past a boundary in one step
fires; usage that sits between boundaries never does. Separately, `TriggerState` is
in-memory only, so the no-refire latch resets on restart while the trigger log
persists.
**Evidence.** `capt_runtime/memory/accounting.py:107-110,124-125`;
`capt_runtime/memory/engine.py:72`.
**Why it matters.** Enforcement is step-size dependent and non-deterministic across
restarts — a replay can see different trigger behaviour than the original run.
**Enhancement.** Make the test "did we cross a boundary since the last evaluated
position", persist the evaluated position, and derive it from the ledger so replay
agrees.

### H-14 [R] Two incompatible `ContextPackDigest` meanings are never reconciled
**Symptom.** (i) The memory-engine pack digest (`_digest_pack`) which the DriverHost
enforces at dispatch; (ii) the continuation-selection digest (`_digest_records`)
embedded as `ContextPackDigest: ...` in the model-operator prompt assembly.
Different inputs, different producers, one field name, and nothing checks that the
prompt's digest corresponds to any memory-engine pack.
**Evidence.** `capt_runtime/memory/contextpack.py:163-189`;
`capt_runtime/continuation_context.py:110-130`;
`capt_runtime/prompt_approval.py:118`; `capt_runtime/operator_provenance.py:96`.
**Why it matters.** Provenance says "ContextPackDigest: X" and a reader reasonably
assumes X addresses the governed memory pack. It may address something else
entirely.
**Enhancement.** Rename one of them (`continuationDigest`) and, where both exist,
record both. This is a one-line-per-site fix with outsized clarity benefit.

### H-15 [R] Salience is a 4-value trust rank, and record digests omit fields
**Symptom.** Scoring is a trust rank only — no embeddings, no recency decay, no
class weighting — and it does not reorder candidates (order is fixed by
`created_at DESC` before scoring). `MemoryRecord._digest` omits `created_at`,
`last_verified_at`, `expires_at` and `downstream_use_restriction`, so records
differing only in those fields share a digest. `expiresAt` is stored and projected
but **never compared to now** — staleness is a writer-set boolean.
**Evidence.** `capt_runtime/memory/contextpack.py:56-57,80`;
`capt_runtime/memory/store.py:76-94,71,110`.
**Why it matters.** "Salience" implies ranking; there is none. Identical digests for
materially different records break idempotency claims. Expired records stay
retrievable.
**Enhancement.** In order: enforce `expiresAt` at retrieval; include the omitted
fields in the digest; then, if ranking is wanted, make the score actually order
candidates.

### H-16 [R] Broken export and a placeholder digest
**Symptom.** `ContextPackBuilder` is in `capt_runtime/memory/__init__.py __all__`
but is never imported or defined — `from capt_runtime.memory import *` raises
`AttributeError`. `build_context_slice_stage` defaults the pack digest to
`'sha256:' + '0'*64`.
**Why it matters.** A wildcard import crashing is a packaging bug that will surface
as a confusing failure in a host. A zero-hash used as an address is a silent
"unknown" masquerading as a digest.
**Enhancement.** Remove or implement `ContextPackBuilder`; reject a zero digest at
the boundary rather than accepting it as an address.

---

## D. ClaimGuard usability

### H-17 [V] The claim gate accepts five exact literals — which makes it unusable as a general gate
**Symptom.** `_ALLOWED_CLAIM_STATEMENTS` is a frozenset of exactly five sentences,
and any statement not exactly equal to one is refused with "not in M0-B allowed
set". Every ordinary completion claim is therefore rejected.
**Evidence.** `capt_runtime/verification.py:28-47` (read directly). Observed live:
`capt_claim_check` on any prose returns `verdict: rejected`.
**Why it matters — two distinct problems.**
1. *Semantics.* `rejected` means "not in the allowed set", **not** "false". Any
   surface that renders this as a truth verdict is wrong and will erode trust in the
   gate. (The MCP read surface already collapses it to `accepted`/`rejected`.)
2. *Utility.* A five-literal vocabulary cannot gate real work. It reads as an M0-B
   scaffold, not a general ClaimGuard.
**Enhancement.** Keep the bounded M0-B set as a strict mode, and add a graded path:
statements that are *bounded and evidence-linked* (a claim kind, an evidence id, a
scope) should be adjudicable without being one of five frozen sentences. Until that
exists, every consumer must be told `rejected != false` — as this integration had to.

### H-18 [R] `qualify` and `escalate` verdicts have no read projection
**Symptom.** The decision vocabulary is `accept | qualify | reject | escalate`, but
the read surfaces collapse to `accepted`/`rejected`. No projection exposes the
middle two.
**Why it matters.** Two of four outcomes are invisible to any host, so an operator
cannot see that a claim was qualified or escalated.
**Enhancement.** Project the full four-valued verdict plus `verificationId`, and
keep the collapse only as an explicit compatibility flag.

### H-19 [R] No per-mission verification store
**Symptom.** Verification attaches to `claim-<id>` streams; there is no per-mission
verification record, and the MCP `capt_verification` tool returns a
non-authoritative gateway projection (which it says, correctly).
**Why it matters.** "Is this mission verified?" has no authoritative answer today.
**Enhancement.** Add a derived, read-only mission verification projection that
aggregates claim-level results, clearly labelled derived.

---

## E. Consistency and hygiene

### H-20 [R] `CheckpointManifest` schema and code disagree
**Symptom.** `create_checkpoint` emits `humanApprovalVersions`,
`promptProposalVersions`, `artifactPromotionVersions`, `cohortVersions`,
`replayForkVersions`, `toolExecutionVersions`, but the schema's required list omits
them.
**Why it matters.** Either the schema under-specifies (benign) or strict
`additionalProperties` handling differs between validator and emitter (not benign).
**Enhancement.** Reconcile the emitter and the schema; add a test asserting emitted
== required ∪ optional.

### H-21 [R] Policy digest excludes provenance-relevant fields
**Symptom.** `timestamp`, `command_id`, `correlation_id`, `previous_policy_digest`
and operator-superseding metadata are not hashed into `policyDigest`, which is the
value dispatch checks.
**Why it matters.** Two materially different policy histories share a digest.
**Enhancement.** Include the supersession chain in the digest input, or document
precisely that the digest covers only the effective policy.

### H-22 [R] `evidence` projection key casing is unproven
**Symptom.** The projection filters on `ev.get('missionId') or ev.get('mission_id')`
while the writer stores the evidence dict verbatim.
**Why it matters.** A casing mismatch silently returns an empty evidence list —
which reads as "no evidence" rather than "query bug".
**Enhancement.** Normalise the key at write, and assert the projection's filter key
in a test against a real written record.

### H-23 [R] Contract enforcement depth is unverified
**Symptom.** It was not established that every generated validator enforces the
constraints the JSON schemas declare (e.g. evidence `trust` const, maxLengths).
**Enhancement.** A conformance test that writes a deliberately-invalid record per
contract and asserts rejection. Until then, treat schema text as intent, not
enforcement.

---

## Suggested order

**Do first (pure read, no new authority, unblocks operators and hosts):**
H-2 read projections for approvals/missions/tasks -> H-3 checkpoint projection ->
H-4 make `capabilities` live-derived.

**Do second (small hardening, high value):**
H-7 actor-kind gates on mission/driver-run -> H-8 audit unauthorized envelopes ->
H-5/H-6 drive or remove the undriven states.

**Do third (honesty pass — cheap, large clarity gain):**
H-14 rename the second ContextPackDigest -> H-9/H-10 wire-or-quarantine the dead
context paths -> H-11/H-12 remove or implement the inert policy fields and triggers
-> H-16 remove the broken export.

**Do fourth (real work):**
H-17 graded ClaimGuard -> H-18 full verdict projection -> H-13 deterministic
trigger evaluation -> H-15 salience and digest completeness -> H-19 mission
verification projection.

**Decide, then document:**
H-1 capability lifecycle reachability. This is a design decision, not a bug fix, and
every host integration depends on the answer.

---

## Cross-cutting pattern

Most items here are one of three shapes, and the same three fixes would prevent the
class rather than the instance:

1. **Declared but undriven** (H-5, H-6, H-9, H-10, H-11, H-12): the contract names a
   state, field or trigger that no code produces. *Fix:* a conformance test that
   every declared state is reachable and every declared event is emitted somewhere.
2. **Commandable but not inspectable** (H-2, H-3, H-18): 21 command ops, almost no
   read ops. *Fix:* a rule that a new command op ships with its read projection.
3. **Two things with one name** (H-14, `evidence` workspace-bundle vs
   `EvidenceRecord`): a shared name for different objects, never reconciled.
   *Fix:* when a second object needs a name that is taken, rename rather than
   overload — provenance fields are read by humans who assume the obvious meaning.
