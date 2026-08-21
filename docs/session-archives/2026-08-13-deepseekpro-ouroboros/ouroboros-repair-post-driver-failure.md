# Ouroboros Repair — CAPT Core Post-Driver-Failure Finalization

Author: DeepSeek Pro (CAPT-native cognitive engine)
Date: 2026-08-13
Specimen: live authoritative ledger `/Users/knowurknot/.capt/runtime.db`
  (mission/task/claim `*-cmd-2748f1347537f6ee`), runtime PID 30727, cwd
  `/Users/knowurknot/CAPT_core`, HEAD `71163d9` on `main`.
Method: full 5-pass recursion. Inspect-before-propose. No mutation performed.

---

## 0. Authority / provenance statement

Authoritative CAPT Core checkout: `/Users/knowurknot/CAPT_core`
  remote https://github.com/knowurknottty/CAPT_core.git, branch `main`, HEAD `71163d9`.
The running service (PID 30727) was launched with cwd `/Users/knowurknot/CAPT_core`,
so the live runtime is CAPT_core `main`, NOT the `capt-harness-convergence` worktree
(branch `feat/capt-harness-convergence`, HEAD `3b2b091`). The two checkouts DIVERGE on
`capt_runtime/verification.py` (confirmed by diff). The harness worktree already
contains a newer verification.py (first-class-evidence / minItems-1 semantics);
CAPT_core `main` has the older `_view`/`strip_view` variant. This divergence is
itself a finding (F8).

No file, ledger row, or process was mutated. The specimen is preserved.

---

## 1. Exact failure timeline (PROVEN — reconstructed from the authoritative ledger)

Ledger global sequences for the second model-command run (`*-cmd-2748f1347537f6ee`):

  18  MissionCreated
  19  TaskCreated
  20  TaskTransitioned (ready)
  21  TaskTransitioned (assigned)
  22  TaskTransitioned (running)
  23  PolicyEvaluated
  24  CapabilityGranted      (maxUses=1, usesConsumed=0)
  25  CapabilityLeaseActivated (lease maxUses=1, state=active)
  26  DriverRunCreated
  27  DriverRunStateChanged  (submitted)
  28  DriverRunStateChanged  (running)
  29  DriverRunStateChanged  (completed)   <-- driver completed
  30  ClaimCreated           (promotionState=proposed)
  31  EvidenceRecorded       (ev-sha256:942ef7f66 on claim)
  -- (no ClaimVerified, no ClaimGuardDecided) --

Final authoritative snapshot state (PROVEN):
  driverrun: state=completed, reconciliationStatus=not_required
  task:      state=running, attempt=1, resultRefs=[]
  claim:     promotionState=proposed, verificationId=null, verificationStatus=null,
             guardVerdict=null, evidenceIds=["ev-sha256:942ef7f66"]
  capability: grantState=leased, lease.state=active, usesConsumed=0, reservations=[],
             consumptions=[]

So the failure boundary is EXACTLY at step 4c of the model-command runner:
`build_verification_result(...)` raised `VerificationFailure` (the
`repo_unchanged=%s no_git=%s artifact_ok=%s` message), BEFORE `record_verification`,
BEFORE `decide_claim`, and BEFORE `finalize_use`. Everything after step 29
(driver completed) is unreached because the runner is a single unguarded
synchronous function inside one IPC command handler.

---

## 2. Violated invariants, ranked by severity

S1  STRANDED LIFECYCLE (severity: CRITICAL)
    driverrun=completed + task=running + claim=proposed + lease active/usesConsumed=0,
    with NO recovery transition. This is precisely the CAPT forbidden state
    "completed driver + running task + no recovery transition". The system is
    stranded.

S2  LEASE ACCOUNTING BROKEN UNDER PARTIAL FAILURE (CRITICAL)
    A one-use lease (maxUses=1) was activated and used for a real external Hermes
    process (externalRunId, exitCode, elapsed recorded in the run), yet
    `reserve_use` was never called and `finalize_use` was never called, so
    usesConsumed=0 and the lease stays `active`. The capability subsystem's
    reservation/consumption machinery (capability.py `reserve`/`finalize`/
    `check_lease`) is ENTIRELY BYPASSED by the model-command runner. The
    consequential-boundary accounting exists in code but is not wired into the
    driver path that performs the actual external side effect.

S3  FAILURE NOT PERSISTED AS STATE (CRITICAL)
    VerificationFailure is an exception, not a recorded VerificationResult with
    status kind failed/contradicted, not a claim promotionState transition, not
    a task transition. Negative verification must be state, not an exception
    swallowed by the IPC handler.

S4  PROJECTION MISREPRESENTS AUTHORITATIVE STATE (HIGH)
    `claimguard_disposition()` in CAPT_core `main` recomputes `guard_claim()` live
    and returns verdict "accepted" for the demo/default statement — WITHOUT
    checking whether a ClaimGuardDecided event was ever committed. The
    harness worktree version fixed this (committed-decision-first), but CAPT_core
    `main` regressed to pure recomputation. A read-only recomputation is being
    shown as if it were an adjudication. (The harness version correctly labeled
    this `committed: True/False`.)

S5  VERIFICATION PROJECTION RECOMPUTES, NEVER READS COMMITTED STATE (HIGH)
    `verification()` in CAPT_core `main` rebuilds a fresh VerificationResult from
    `self.demo[...]` (the seeded OpenHarness demo), not from the claim stream's
    committed ClaimVerified event. It cannot ever show the failed model-command
    claim's actual (absent) verification state. The projection is decoupled from
    authoritative claim state.

S6  EVIDENCE PROJECTION READS THE WRONG STREAM (HIGH)
    `project_evidence(client, mission_id)` in CAPT_core reads
    `mission-<id>` stream events and extracts `EvidenceRecorded` payloads there.
    But `record_evidence()` commits the `EvidenceRecorded` event onto the
    CLAIM stream (`claim-<id>`), never the mission stream. Hence `capt evidence`
    shows `evidence: []` even though the claim stream holds
    `EvidenceRecorded(ev-sha256:942ef7f66)`. The evidence is persisted; the
    projection looks in the wrong stream. This is a projection bug, NOT lost data.

S7  CLAIM EVIDENCE ID vs EVIDENCE EVENT ID (MEDIUM)
    The claim's `evidenceIds` holds `ev-sha256:942ef7f66` (from the
    artifact-digest fingerprint), but the runner built the evidence record with
    the SAME id. Consistent here, but the id scheme (`"ev-" + fingerprint[:16]`)
    is digest-truncation with no collision guard and is shared across the
    artifact/command evidence id and the verificationId derivation — fragile.

S8  REPO DIRT PRE-EXISTS AND BREAKS `no_git` (ROOT TRIGGER, MEDIUM)
    `verify_no_git_mutation` runs `git status --porcelain` and requires empty
    stdout. `/Users/knowurknot/CAPT_core` has ~20 pre-existing untracked scratch
    files, so `no_git=False` is a FALSE POSITIVE for "the driver mutated git".
    The check cannot distinguish pre-existing dirt from driver-induced mutation
    because it captures no BEFORE git snapshot. So repo_unchanged=True (tree
    digest) and artifact_ok=True, but no_git=False trips the whole verification.

    NOTE (verified fact): in the SPECIMEN, the actual failure message is
    `repo_unchanged=True no_git=False artifact_ok=True` per the mission brief.
    The source confirms no_git=False alone is sufficient to raise
    VerificationFailure, and repo_unchanged/artifact_ok were both True. This
    makes S8 the proximate trigger and is consistent with the observed state.

S9  RUNNER NOT TRANSACTIONAL / NO ERROR RECOVERY (HIGH)
    The model-command runner (`_run_approved_hermes` in
    desktop/capt_runtime_service.py) performs mission→task→policy→grant→lease→
    driver-run→dispatch→claim→evidence→verify→decide→checkpoint as ~20 separate
    committed commands with NO error handling around verify/decide/finalize and
    NO catch that reconciles task/claim/lease on failure. The IPC handler catches
    the exception and returns `classification=internal_failure`, discarding the
    fact that steps 18–31 already committed.

S10 LEASE NEVER CONSUMED ON SUCCESS EITHER (HIGH, even happy path)
    Even on success, `_run_approved_hermes` never calls `reserve_use`/`finalize_use`,
    so usesConsumed stays 0 and the grant never reaches `consumed`. The one-use
    lease is decorative in the model-command path. (The M0-A scenario and the
    harness capability tests exercise reserve/finalize, but the live model-command
    runner does not.)

---

## 3. Proven vs inferred

PROVEN (directly observed in authoritative ledger + source):
  - The exact event sequence 18–31 and the final aggregate snapshots (read from
    runtime.db).
  - Driver completed, task running, claim proposed, verification null, lease
    active with usesConsumed=0.
  - `record_evidence` commits EvidenceRecorded to the CLAIM stream (services.py).
  - `project_evidence` reads the MISSION stream (desktop_runtime_client.py +
    capt_cli.py `_evidence_view`), so `capt evidence` returns [].
  - `claimguard_disposition`/`verification` in CAPT_core `main` are live
    recomputations (capt_runtime_service.py lines 351–386).
  - The model-command runner never calls reserve_use/finalize_use and has no
    error reconciliation (capt_runtime_service.py lines 559–785).
  - CAPT_core `main` verification.py differs from the harness worktree
    verification.py (diff performed).
  - CAPT_core repo is dirty with pre-existing untracked files (git status).

INFERRED (strong, from source + observed state, not directly executed):
  - The VerificationFailure message values repo_unchanged=True / no_git=False /
    artifact_ok=True (from the mission brief's stated observation, consistent
    with source semantics and the dirty repo).
  - The exception propagated from `_run_approved_hermes` → `RuntimeCommandService`
    handler → `internal_failure` receipt.

HYPOTHESIS (falsifiable, not established):
  - The `no_git` false-positive is the single proximate trigger in this run
    (S8). It is sufficient but not proven to be the only contributor.

---

## 4. Minimal fix set

Ordered smallest-first. Each fix is additive; none rewrites authority.

FIX A — Projection reads the claim stream for evidence (correctness, no schema change).
    `project_evidence` (and `_evidence_view`) must gather EvidenceRecorded events
    from CLAIM streams (or scan all streams), not mission streams. `capt evidence`
    then shows the persisted evidence. One function + its callers.

FIX B — ClaimGuard/verification projections prefer committed state.
    Port the harness worktree's committed-decision-first logic into CAPT_core
    `claimguard_disposition` and `verification`: read the claim stream for a
    `ClaimGuardDecided` / `ClaimVerified` event; only fall back to recomputation
    for a statement with no committed decision, and mark it `committed:false`.
    (This is a revert of a regression; the harness branch already had it.)

FIX C — Make verification failure a recorded state transition (not an exception).
    Add a `record_verification_failure` service method that commits a
    VerificationResult with `status.kind = "contradicted"` (or a new `failed`)
    onto the claim, driving `promotionState -> rejected` via the existing
    `record_verification` "contradicted" branch, and a task transition to
    `failed`. Preserve the failure detail in the event payload.

FIX D — Wire reserve/finalize into the model-command runner.
    Before dispatch call `reserve_use`; after dispatch call `finalize_use` with
    outcome succeeded/indeterminate/failed as appropriate. This makes the
    one-use lease actually consume and reach `consumed`/`exhausted`, closing S2/S10.

FIX E — Add reconciliation on runner failure.
    Wrap steps 4c/4d/4e in try/except: on VerificationFailure (or any CaptRuntimeError),
    record the negative verification (FIX C), transition the task to `failed`,
    finalize the lease as failed/indeterminate (FIX D), and return a classified
    receipt that references the claim/verification/task state — do NOT return a
    bare internal_failure that hides committed state.

FIX F — Capture a BEFORE git snapshot so no_git is not a false positive.
    Record `git status --porcelain` (and/or tracked-file list) BEFORE the driver
    dispatch; compare AFTER to BEFORE, ignoring pre-existing dirt. Only a NEW
    uncommitted change should fail `no_git`. This is the discriminating fix for
    the S8 trigger and preserves the "no git mutation" intent.

FIX G — (optional, smallest) Add evidence-id collision guard / full-length digest.
    Derive evidence/verification ids from full 64-hex digests or include a
    disambiguating counter; 16-char truncation is a latent collision risk.

---

## 5. Exact regression tests required (one per fix, discriminating)

  R-A: seed claim with evidence; assert `project_evidence(client, mission_id)`
       returns the evidence recorded on the claim stream (currently returns []).
  R-B: with a committed ClaimGuardDecided(accept) on the claim, assert
       `claimguard_disposition` returns verdict from the committed event and
       `committed=True`; with none, assert `committed=False` and a recomputation.
  R-C: force `build_verification_result` to raise (dirty target); assert the
       runner commits a contradicting verification and the claim reaches
       `rejected`, task reaches `failed` (not stranded in running/proposed).
  R-D: happy path model command; assert lease `usesConsumed == 1` and
       `grantState == consumed` (or lease exhausted), and a `CapabilityUseFinalized`
       event exists.
  R-E: inject VerificationFailure mid-runner; assert the receipt classification
       references the claim/verification/task ids and ledger head advanced only
       by the committed steps (no partial silent success).
  R-F: create a repo with PRE-EXISTING untracked file; run the driver; assert
       `no_git` is True (no new mutation) and verification passes on
       repo_unchanged+artifact_ok. Then create a NEW untracked file post-before-
       snapshot and assert `no_git` is False.
  R-G: (optional) assert two distinct artifacts never collide on evidence id.

---

## 6. Migration / backward-compatibility risks

  - FIX B and FIX A change PROJECTION output shape (add `committed` field; move
    evidence source). GUI/TUI consumers that index `claimGuardDisposition.verdict`
    and `evidence` keep working; add fields are additive. No schema migration.
  - FIX C/FIX E add new events (`VerificationFailed` / a contradicting
    `ClaimVerified`) and new task `failed` transitions. Existing replay/idempotency
    is unaffected (new idempotency keys), but any downstream consumer asserting
    the exact event-type list for a model command must be updated.
  - FIX D adds `CapabilityUseReserved`/`CapabilityUseFinalized` events and mutates
    grant state to `consumed`/lease `exhausted`. This is the CORRECT accounting
    but changes observable grant state for existing runs; replay of old runs does
    not retroactively consume (events already committed), so old stranded leases
    remain stranded until explicitly reconciled. A one-time reconciliation path
    (revoke or finalize-as-indeterminate) is needed for the CURRENT specimen.
  - FIX F changes the semantics of `no_git` from "worktree is clean" to "no NEW
    mutation since baseline". This is a behavior change with a stronger guarantee;
    the `checks.noGitMutation` boolean in committed VerificationResults is
    version-agnostic (no schema change), but documentation must state the new
    meaning.

---

## 7. What NOT to change

  - Do NOT add a second runtime/authority path, daemon, or "RuntimeAggregate".
    RuntimeService remains the sole command surface.
  - Do NOT let the Hermes driver emit EvidenceRecord / VerificationResult /
    ClaimGuardDecision. The driver stays untrusted (Mode A). FIX C/D/E are all
    CAPT-side.
  - Do NOT change the frozen ExecutionDriver surface (describe/submit/inspect/
    cancel/resume/reconcile) or the contract schema version 1.0.0.
  - Do NOT modify `capability.py` reserve/finalize semantics (they are correct and
    tested); only WIRE them into the runner.
  - Do NOT change ClaimAggregate's central rule (completion claim requires
    verified + evidence). It is correct; the runner simply never reached it.
  - Do NOT convert `guard_claim`'s allowed/forbidden statement sets (M0-B bounded
    claims) — the failure is orchestration, not claim policy.
  - Do NOT "clean up" the pre-existing untracked files as part of this repair;
    they are the specimen's trigger condition and unrelated scratch (FIX F makes
    them harmless without deleting evidence).

---

## 8. Recommended implementation order

  1. FIX A + FIX B  (projection correctness; pure read-path, lowest risk, makes
     the operator able to SEE the true state). Tests R-A, R-B.
  2. FIX F          (discriminating no_git baseline; removes the false-positive
     trigger). Test R-F.
  3. FIX C + FIX E  (persist negative verification; reconcile stranded lifecycle).
     Tests R-C, R-E.
  4. FIX D          (wire lease accounting). Test R-D.
  5. FIX G          (optional, last).

  After 1–5, reconcile the CURRENT stranded specimen: finalize its lease
  (failed/indeterminate) and transition its task/claim to a terminal state via
  the governed path, so no stranded state persists.

---

## 9. Stop condition for this repair mission

STOP when ALL of the following are true, verified against the live ledger and the
test suite (no further iteration):

  1. Every regression test R-A..R-G passes with real exit codes, and the
     discriminating tests actually flip on their trigger (R-F fails without the
     baseline fix, passes with it; R-A fails against the current projection).
  2. The specimen claim/task/lease are no longer stranded: task terminal,
     claim terminal, lease finalized/revoked with usesConsumed reconciled.
  3. `capt evidence` for the model mission shows the persisted evidence (non-empty).
  4. `capt status`/verification projection reflects COMMITTED verification state,
     not a live recomputation, for every claim with a committed decision.
  5. A fresh end-to-end model command (happy path) produces driverrun=completed,
     task=succeeded, claim=accepted, lease=consumed — with no internal_failure
     and no stranded state on either success or injected failure.
  6. No new authority path, no schema drift, and the frozen ExecutionDriver
     surface unchanged (diff-empty against the frozen contract).

If a blocker appears (e.g., the runner's transaction boundaries cannot be made
safe without touching the frozen surface), STOP, record the blocker as evidence,
and do not claim completion.

Final assessment: WOULD THIS SURVIVE CAPT? Only after FIX A–F plus the specimen
reconciliation. The diagnosis in the brief is CORRECT in direction but INCOMPLETE:
the proximate trigger is the `no_git` false positive (S8/FIX F), but the deeper
defects are (a) failure-not-persisted (S3), (b) lease accounting unwired (S2/S10),
(c) projection reading wrong stream / recomputing adjudication (S6/S4/S5), and
(d) non-transactional runner with no recovery (S1/S9). Fixing only the git check
would leave CAPT stranded on the next partial failure.
