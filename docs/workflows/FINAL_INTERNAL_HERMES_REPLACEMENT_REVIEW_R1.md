# CAPT Terminal Internal Hermes-Replacement Review — R1

**Purpose:** perform one final, evidence-driven, repository-wide review and integration pass before CAPT becomes the default Inversion Labs internal model-work / software-work harness in place of Hermes.

**Classification target:** internal-use readiness only. This workflow MUST NOT convert an internal-use PASS into a public-release, security-complete, production-SaaS, or universal-readiness claim.

**Execution owner:** GPT-5.6 Sol / Syntellect, acting as final integrator and reviewer.

**Repository:** `knowurknottty/CAPT_core`

**Workflow branch:** `workflow/final-internal-hermes-replacement-review-r1`

**Workflow starting source:** PR #98 clean head `e561eed036e00e41c391e2edd470878e3fe391c8`, stacked on PR #47 head `10854b5a2b9835788478ee7770fcaa17bb4e1156`.

---

## 0. Non-negotiable operating rules

1. **GitHub is authority for remote state.** Re-fetch all PR heads, branch heads, reports, CI, and merge ancestry at execution time. Do not rely on this document's SHAs if GitHub has advanced.
2. **RuntimeService/EventStore remain the only authoritative runtime state-transition path.** UI, TUI, drivers, Cohorts, tools, providers, models, prompt builders, memory selectors, evidence viewers, security dashboards, and review harnesses remain clients/projections/execution adapters.
3. Never collapse these claims:
   - observed;
   - recorded as evidence;
   - verified in a named domain;
   - ClaimGuard accepted;
   - task completed;
   - mission completed;
   - internal-use ready;
   - public-release ready.
4. **No source mutation without root-cause reconstruction and a RED test first.** Use root-cause → RED → minimal GREEN → refactor → fresh proof.
5. **Every generated or materially edited artifact receives true 5-pass recursion.**
   - Pass 1: factual/state reconstruction.
   - Pass 2: architecture/authority/security invariants.
   - Pass 3: adversarial/restart/replay/TOCTOU.
   - Pass 4: evidence/provenance/claim calibration.
   - Pass 5: contradiction search, minimality, human readability, final recheck.
6. Preserve all failed evidence. Correct classifications; do not erase inconvenient failed runs.
7. No secret values in reports, ledgers, command receipts, test fixtures, screenshots, logs, or commits.
8. No unexplained test failure is accepted as "pre-existing." Any such claim requires same-head ablation evidence.
9. Do not integrate experimental or attractive features merely because they exist. For tomorrow's internal cutover, prefer the smallest coherent terminal candidate that fully performs the real operator job.
10. Do not delete Hermes during this workflow. Hermes remains the rollback path until CAPT completes the cutover acceptance sequence.

---

## 1. Exact objective

Build and audit one **terminal integrated candidate** that can replace Hermes for Inversion Labs internal work tomorrow.

The candidate must prove, on one exact source head and one exact installed artifact, that CAPT can:

- accept a human objective;
- select a provider/model;
- assemble and bind the exact model-visible prompt/context;
- require and consume bounded human approval correctly;
- call a real local or authenticated remote model;
- preserve model output as evidence without self-promoting it to truth;
- retain prior cognition across full process death and a different model;
- perform a **real governed software mutation workflow**, not merely read/analysis;
- isolate writes before promotion;
- run verification/tests over the produced work;
- promote verified work through explicit governed authority;
- survive replay/restart/crash boundaries without duplicate external effects;
- remain operable from the CLI/TUI by the operator without hand-editing ledgers or hidden harness injection;
- enforce the internal single-operator security/resource profile sufficiently for bounded Inversion Labs use.

The terminal proof is not "CAPT has many features." It is:

> **CAPT can perform the actual work Hermes was being used for, with stronger governed state, memory, replay, evidence, provider, and recovery semantics.**

---

## 2. Starting branch topology to reconstruct, not blindly merge

Refresh all refs before work. The currently known lanes include:

### Core v0.7 / authority stack

- PR #44 — Discovery Governor / SEAL.
- PR #46 — Ouroboros post-driver lifecycle and restart/idempotency correction.
- PR #47 — governed prompt assembly, approval binding, provider integration, prepared execution, provider-authority correction; verified head `10854b5a...` when this workflow was authored.
- PR #98 — governed cross-model continuation context; clean head `e561eed...` when authored.

### Cohort/security/upgrade lane

- PR #48 — bounded Cohort coordination projection layer.
- PR #49 — fail-closed security infrastructure gate.
- CAPT-UPG stack beginning at PR #52, including bounded IPC, state permissions, security rejection audit, resource ceilings, injection assurance, provider acceptance, restart/recovery, isolated workspace promotion, durable Cohorts, steering, `.capt-flight`, context Merkle, epistemic ladder, replay/fork, provenance lens, security cockpit, reciprocal-review benchmark, symbol index, structural hashing, chunk-stability probe, and cognitive-debt cockpit.

### Critical topology rule

Do **not** merge this topology mechanically.

Several upgrade branches were built from older prompt/provider/cohort heads and may duplicate or regress functionality later corrected in PR #47/#98. Build a fresh integration branch and transplant semantic deltas only after comparing them against the canonical current path.

---

## 3. Explicit supersession / deduplication rules

Treat the following as starting hypotheses and verify them from source:

1. **PR #98 is canonical for true cognitive cross-model continuity.** Earlier CAPT-UPG-007 / PR #64 restart-continuity tests may contribute discriminating tests, but must not replace #98's actual governed ContextPack selection/binding.
2. **PR #47 exact live OpenRouter evidence supersedes older "provider blocked" evidence** where the older branch simply lacked credentials. Preserve historical blocked evidence but do not reclassify current transport as unverified without new exact-head contrary evidence.
3. **PR #47 provider-authority correction is canonical.** No upgrade branch may restore provider-output auto-verification, auto-ClaimGuard acceptance, task success, or mission success.
4. **PR #46/#47 prepared-execution/Ouroboros semantics are canonical.** Destructive-recovery upgrades must integrate into those semantics rather than reintroduce raw-command reconstruction after approval consumption.
5. **PR #98 continuation context is canonical over simple "same mission survived restart" tests.** The next model must receive actual prior context through CAPT, with trust labels and exact context digest binding.
6. **PR #74 is synchronization/stack-repair history, not a product feature.** Never merge it as an independent product change.
7. **PR #45 is an archive.** Do not mix archival transcripts into runtime code.
8. **Hermes LOCAL-002 / D-09 remains quarantined** unless independently restored and revalidated. Even if restored, it is not proof of current CAPT exact-head readiness.
9. Experimental probes (FastCDC, Tree-sitter structural hash, benchmark harnesses, optional cockpits) are not tomorrow's P0 unless they touch the terminal runtime path or are needed to make the operator workflow usable.

---

## 4. Create the terminal integration candidate

Create a fresh branch, suggested:

`integration/internal-hermes-replacement-r1`

Preferred starting base: the latest independently accepted PR #98 head, after confirming its ancestry includes the accepted PR #47 provider-authority head.

Then build a **semantic integration ledger** before transplanting anything:

| Candidate source | Unique value | Overlap | Risk | Decision | Evidence |
|---|---|---|---|---|---|
| PR #44 | Discovery/SEAL | low | scanner authority | include/rebuild/defer | ... |
| PR #46/#47 | Ouroboros/provider authority | canonical | high | preserve | ... |
| PR #98 | context continuity | canonical | high | preserve | ... |
| PR #49 | security gate | medium | exact-head drift | include after reconcile | ... |
| UPG-001.. | security/runtime increments | high overlap | high | per-commit review | ... |

For every transplant:

- compare base/head;
- identify the actual invariant/functionality added;
- identify overlapping current code;
- transplant the smallest surviving delta;
- add/retain discriminating tests;
- run focused tests before next transplant;
- document rejected stale pieces.

Never solve conflicts with blanket `ours`/`theirs` without semantic review.

---

## 5. Review domain A — authority and state-machine integrity

Review every authoritative aggregate/service path:

- Mission;
- Task;
- Capability Grant;
- Capability Lease;
- HumanApproval;
- DriverRun;
- Evidence;
- Verification;
- Claim;
- ClaimGuard;
- Cohort if included;
- checkpoint/replay;
- command idempotency;
- security rejection state where applicable.

Required invariants:

- no UI-owned authoritative state;
- no driver/provider-owned completion authority;
- no model text interpreted as an authoritative event;
- no accepted command without actor/authority checks;
- exact replay is idempotent;
- different payload under same idempotency identity conflicts;
- no consumed approval becomes reusable after restart;
- no lease is silently revived;
- no verification in one domain implies another domain;
- no task/mission success is inferred from provider response alone.

Search explicitly for shortcuts such as:

- direct `store.append` outside intended authoritative services;
- hidden state sidecars;
- in-process dicts acting as durable authority;
- `except Exception: pass` on authority-sensitive transitions;
- state reconstruction from UI fields;
- synthetic `verified` or `succeeded` defaults.

---

## 6. Review domain B — prepared execution, prompt/context, approval, provider boundary

Re-prove the full chain:

`raw operator intent`
→ deterministic preparation
→ context selection
→ prompt assembly
→ approval request
→ human decision
→ immutable prepared execution
→ atomic consequential admission / approval consumption
→ exact dispatch
→ provider result
→ evidence
→ `awaiting_verification`.

Required checks:

- all deterministic P0/P1 validation occurs before consumption;
- context selected at approval equals context dispatched;
- provider/model/target/mission/task/run/context/human-verification/executable identity is bound;
- exact outbound prompt digest is checked at final driver seam;
- no global mutable digest registry can cross-contaminate concurrent runs;
- credentials are resolved after deterministic preparation and are never included in prepared-execution/evidence material;
- exact replay causes zero second provider dispatch;
- materially different second use causes zero provider dispatch.

Re-run invalid-input proofs including:

- invalid context budget `12345`;
- model-visible prompt/title overflow;
- mismatched provider/model;
- mismatched mission/task/run;
- expired approval;
- absent approval receipt;
- post-approval context change;
- post-approval target/resource change.

---

## 7. Review domain C — continuation context, memory, and evidence trust

PR #98 adds the required governed continuation path. The final review must strengthen the difference between **durable artifact material** and **admitted evidence**.

### Mandatory P0/P1 question

`select_continuation_context()` currently can select completed DriverRun staging artifacts. Before internal cutover, prove one of these is true:

A. the selected staging bytes are cryptographically bound to a committed EvidenceRecord / DriverRun result digest and the selector verifies that binding before inclusion; **or**

B. harden the selector so only evidence/artifact bytes with an authoritative digest/provenance link are eligible.

A completed DriverRun plus a file at an expected filesystem path is not by itself sufficient to call the file authoritative evidence.

Also review:

- deterministic ordering when multiple claims/evidence records exist;
- duplicate record identities when multiple artifacts belong to one run;
- artifact tamper between approval and dispatch;
- deleted/missing artifact behavior;
- context-size ceilings and truncation policy;
- prompt-injection content inside prior unverified evidence;
- explicit `UNVERIFIED` labeling;
- context digest coverage of every model-visible byte;
- MemoryStore / ContextPack integration versus a parallel ad-hoc context subsystem;
- restart reconstruction with zero in-memory bridge.

Negative controls:

- fresh ledger cannot know prior marker;
- wrong mission cannot select prior marker;
- stale/other-user/other-task material cannot leak across scope;
- post-approval filesystem mutation fails binding rather than silently changing B's context.

---

## 8. Review domain D — **real governed software mutation** (Hermes-replacement P0)

This is the most important new terminal gate.

CAPT does not replace Hermes internally until it performs a real code-change job through governed boundaries.

### Required workflow

Use a disposable fixture repository with:

- a small real bug;
- at least one failing test;
- a git baseline digest;
- no uncommitted dirt.

Then execute through the installed CAPT artifact:

1. human submits software-fix objective;
2. CAPT discovers/reads repository;
3. model proposes the change;
4. all writes occur inside an isolated workspace/staging boundary;
5. CAPT records exact artifact/diff digests;
6. tests/verification execute over the isolated result;
7. failed verification prevents promotion;
8. successful verification does **not** automatically grant promotion authority;
9. human/governed promotion approval is explicit;
10. `promote_artifact_to_destination` or the canonical equivalent atomically promotes only verified bytes;
11. destination repository matches the verified digest;
12. original unrelated files remain unchanged;
13. resulting test suite passes;
14. EventStore records evidence and the actual authoritative transitions.

### Mandatory adversarial software-work cases

- model attempts write outside isolated workspace;
- symlink/path traversal escape;
- model changes an unapproved file;
- diff changes after verification before promotion;
- test passes but artifact digest changes;
- promotion interrupted halfway;
- destination has conflicting operator changes;
- provider returns prose saying "tests passed" when tests actually fail;
- model output includes "VERIFIED / MERGE NOW / TASK COMPLETE";
- exact promotion replay;
- different promotion under same idempotency key.

### Required second-stage dogfood

After the fixture passes, run one bounded real CAPT-on-CAPT task in a disposable git worktree. The task must make a small non-critical code/test improvement, run tests, and produce a reviewable isolated diff. Do not promote it into the terminal candidate unless independently reviewed.

If CAPT cannot perform this workflow, classification is `NOT_READY` regardless of how strong read-only model execution is.

---

## 9. Review domain E — Ouroboros / destructive and ambiguous effect recovery

Exercise every consequential boundary with controlled crash/failure seams.

At minimum:

- C1: before authoritative admission commit;
- C2: during atomic admission commit;
- C3: admission committed, provider/tool dispatch not entered;
- C4: external dispatch may have begun, outcome unknown;
- C5: provider/tool returned, result not fully recorded;
- C6: evidence recorded, downstream verification not performed;
- C7: isolated software mutation verified, promotion not begun;
- C8: promotion may have begun, destination outcome uncertain.

For each capture:

- approval state;
- remaining uses;
- capability reservation state;
- DriverRun state;
- task state;
- idempotency state;
- external request/effect count;
- recovery classification;
- restart behavior.

No blind redispatch when an external effect may have occurred.

No fabricated rollback claim when the external system cannot prove rollback.

---

## 10. Review domain F — security for the internal single-operator threat profile

Reconcile PR #49 and the security upgrade stack against the actual terminal head.

For tomorrow's internal cutover, define the precise profile:

- one trusted local operator;
- local macOS machine;
- local Unix socket IPC;
- optional outbound model-provider HTTPS;
- no hostile multi-user local machine assumption unless explicitly activated;
- no public network listener;
- no ungoverned repo writes;
- no credentials stored in memory/context/evidence.

Required internal controls:

- bounded IPC framing wired in production service/client;
- socket/token/state filesystem permissions;
- raw provider credentials absent from EventStore/logs/reports;
- durable non-secret security rejection audit;
- prompt/context/memory/provider injection tests;
- request/token/cost ceilings;
- fail-closed provider timeout behavior;
- no arbitrary path escape;
- safe secret reference resolution;
- dependency/secret scan with exact-head evidence;
- capability profile accurately activates applicable controls.

Do not require public-SaaS controls that are structurally N/A to the internal local-only profile, but do not convert N/A to PASS.

At-rest encryption may remain a public/high-assurance blocker if the operator explicitly accepts the trusted-local-disk internal profile; document the boundary rather than pretending encryption exists.

---

## 11. Review domain G — resource and financial ceilings

Prove runtime enforcement, not just UI settings:

- maximum external requests per governed operation;
- requested/effective context budget;
- token ceiling where transport reports/enforces tokens;
- cost ceiling for paid provider paths;
- timeout ceiling;
- artifact/output ceiling;
- retry ceiling;
- no automatic retry after ambiguous consequential dispatch;
- no paid request caused by exact replay.

For OpenRouter/internal paid providers, run a tiny bounded live transaction and capture redacted usage/cost evidence if available.

---

## 12. Review domain H — Cohorts and operator steering

Cohorts are valuable but must not delay tomorrow's single-model software-work cutover unless they are part of the chosen default workflow.

If included in the terminal candidate, require:

- durable Cohort aggregate/state;
- restart reconstruction;
- participant identities and cursors;
- epoch/stale-contribution semantics;
- dissent retained;
- steering through RuntimeService authority;
- no steering-based capability widening;
- Cohort result is evidence, not automatic verification/completion;
- actual participant provider/model invocations are governed.

If the scheduler/execution bridge is not production-ready, ship tomorrow's internal cutover with Cohorts disabled/default-off rather than exposing a half-authoritative surface.

---

## 13. Review domain I — CLI/TUI/operator usability

The internal replacement has to be pleasant enough that the operator actually uses CAPT instead of opening Hermes again.

Dogfood only supported commands from a fresh installed artifact.

Required operator path should be discoverable without repository archaeology:

- install;
- doctor;
- start runtime;
- connect TUI;
- configure/test provider;
- select model;
- submit mission/work objective;
- inspect exact model-visible prompt/context;
- approve/deny;
- observe execution state;
- inspect evidence/provenance;
- perform verification;
- approve promotion when applicable;
- checkpoint;
- stop;
- resume;
- change model and continue;
- inspect errors and recovery instructions.

Review:

- keyboard flows;
- pending approval visibility;
- provider health;
- active model always visible;
- `awaiting_verification` is visually distinct from success;
- stale/indeterminate/lost states are understandable;
- CaveCAPT verbosity affects presentation only;
- no hidden requirement to edit JSON/SQLite manually.

Internal readiness may use the Textual TUI / current desktop operator MVP. Native SwiftUI `.app` completion is not required for tomorrow unless explicitly chosen as the launch surface.

---

## 14. Review domain J — packaging / installed-artifact truth

All final acceptance must move off editable/source execution.

On the terminal source head:

1. clean tree;
2. build wheel and sdist;
3. record SHA-256;
4. create fresh venv outside repo;
5. non-editable wheel install;
6. empty `PYTHONPATH`;
7. `PYTHONNOUSERSITE=1`;
8. isolated interpreter where practical;
9. prove critical imports resolve from site-packages;
10. run installed CLI/TUI commands;
11. run installed regression subset;
12. perform live provider dogfood;
13. perform software-mutation dogfood;
14. perform process restart / cross-model continuation;
15. re-run secret scan over the built distribution.

Never reuse artifact evidence after a source/report/package-content change unless the exact bytes are unchanged and the claim is explicitly about runtime bytes only.

---

## 15. Review domain K — repository and code-quality sweep

Perform a repository-wide source review, not merely tests.

Search for:

- TODO/FIXME/HACK/XXX on runtime paths;
- dead compatibility branches;
- duplicate runtime/services;
- duplicate authority functions;
- hardcoded local paths;
- `/tmp` assumptions in production code;
- shell=True / unsafe subprocess construction;
- unbounded reads/writes;
- exception swallowing;
- mutable globals crossing concurrent operations;
- unsafe thread/process state;
- missing locks around shared provider state;
- path traversal/symlink hazards;
- secrets in serialization;
- stale contract fields;
- tests that assert implementation details instead of behavior;
- test skips masking required internal paths;
- misleading names (`verified`, `success`, `authoritative`) on advisory data;
- documentation contradicting current code.

Run static/syntax/contract checks available in repo and record exact versions/results.

---

## 16. Review domain L — test-suite truth

At terminal head run, separately report:

- focused authority tests;
- approval/prepared-execution tests;
- continuation/memory tests;
- provider-driver tests;
- software mutation/promotion tests;
- Ouroboros/recovery tests;
- security tests;
- Cohort tests if included;
- TUI/operator tests;
- checkpoint/replay tests;
- `tests/capt_runtime` total;
- full repository total;
- skipped and deselected counts with reasons.

Rules:

- zero unexplained failures;
- skips in a P0 internal path are blockers unless replaced by live proof;
- tests requiring real providers must distinguish environment BLOCKED from implementation FAIL;
- no self-certification from a test whose assertions merely restate fixture data.

---

## 17. Final live provider matrix

At minimum test:

### Local
- Ollama real model through installed CAPT.

### Authenticated remote
- OpenRouter through installed CAPT with credential-presence-only evidence.

For each:

- fresh approval;
- one dispatch;
- real response;
- exact replay no second dispatch;
- task `awaiting_verification`;
- no auto verification;
- no auto claim acceptance;
- secret audit.

Do not retest every provider registration. Distinguish registered, health-probe-supported, model-list-supported, executable, and governed-execution-proven.

---

## 18. Terminal Hermes-replacement dogfood sequence

Run these in order on the exact installed terminal artifact.

### Dogfood 1 — normal analysis
A small repository analysis using local model. Prove normal usability.

### Dogfood 2 — authenticated remote analysis
Tiny OpenRouter task. Prove paid remote path and ceilings.

### Dogfood 3 — real software fix
Disposable fixture repository; model produces a real code fix in isolated workspace; tests verify; explicit promotion; destination passes.

### Dogfood 4 — process death + Model B continuation
Model A works on a mission, full runtime shutdown, new process, Model B receives CAPT-restored prior context and continues with no Model A redispatch.

### Dogfood 5 — destructive ambiguity
Kill runtime/provider/tool at an ambiguous boundary and prove fail-closed recovery/no blind redispatch.

### Dogfood 6 — CAPT self-work
In a disposable CAPT worktree, CAPT performs one small real code/test improvement from objective → governed model → isolated mutation → verification → reviewable diff. Do not auto-promote to source.

The terminal candidate is not Hermes-replacement-ready if Dogfood 3 or Dogfood 6 cannot be completed without an ungoverned manual bridge.

---

## 19. Documentation / public-claim reconciliation

After code truth is frozen, update only docs that are now stale.

Required internal docs:

- exact internal install/start commands;
- provider configuration with secret references only;
- TUI quick start;
- software-work workflow;
- approval meanings;
- `awaiting_verification` meaning;
- recovery states;
- checkpoint/restart/model-switch flow;
- rollback to Hermes;
- known internal limitations.

Do a 5-pass README/public-facing audit but do not announce public release solely from the internal gate.

Explicitly retire stale claims such as "cross-model continuity pending" once exact terminal evidence supports otherwise.

---

## 20. Internal cutover / rollback plan

Do not uninstall Hermes immediately.

For the first internal cutover window:

- CAPT becomes default launcher/workflow;
- Hermes remains fallback only;
- record every fallback reason;
- no silent switching mid-mission;
- if CAPT blocks, preserve CAPT state/evidence before fallback;
- after at least three successful real internal CAPT tasks including one software mutation and one restart continuation, reevaluate whether Hermes can be removed from the default toolchain.

Suggested rollback criterion:

- any authority violation;
- duplicate paid/external effect;
- lost work with false completion claim;
- inability to recover mission state;
- unbounded write outside isolated workspace;
- secret leakage;
- software promotion of bytes different from verified bytes.

---

## 21. Severity and priority model

### P0 — blocks internal replacement

Examples:

- authority bypass;
- provider result self-promotes to success;
- approval can be reused or burned incorrectly in normal deterministic rejection;
- duplicate external effect on replay;
- context continuity requires manual injection;
- selected continuation bytes are not integrity/provenance bound;
- software mutation cannot be isolated/promoted safely;
- write escape;
- secret leakage;
- restart falsely claims success/rollback;
- installed artifact cannot perform the real workflow.

### P1 — must fix before default use unless operator explicitly narrows scope

- significant TUI unusability;
- missing bounded IPC/resource control in active path;
- unsafe artifact selection edge;
- ambiguous multi-claim selection;
- important security audit gap;
- recovery state not surfaced clearly.

### P2 — high-value near-term improvement, not tomorrow blocker

- native desktop polish;
- extra provider adapters;
- performance optimization;
- richer cockpits;
- benchmark/probe features;
- public packaging/docs polish beyond internal runbook.

### P3 — backlog / experimentation

- optional research probes;
- aesthetic improvements;
- non-blocking developer ergonomics.

---

## 22. Required terminal artifacts

Create on a dedicated evidence/review branch:

1. `reports/final-review/CAPT_INTERNAL_HERMES_REPLACEMENT_FINAL_REVIEW.md`
2. `reports/final-review/CAPT_INTERNAL_HERMES_REPLACEMENT_FINAL_REVIEW.json`
3. `reports/final-review/CAPT_INTERNAL_HERMES_REPLACEMENT_FUNCTIONALITY_MATRIX.md`
4. `reports/final-review/CAPT_INTERNAL_HERMES_REPLACEMENT_FINDINGS.md`
5. `reports/final-review/CAPT_INTERNAL_HERMES_REPLACEMENT_DOGFOOD.md`
6. `docs/INTERNAL_CUTOVER_RUNBOOK.md`

Every artifact must name:

- exact source head;
- exact wheel/sdist hashes;
- platform/Python;
- provider/model identities;
- test counts;
- live gates;
- unverified/blocked items;
- remaining P2/P3 work;
- whether any source changed after a previously recorded proof.

---

## 23. Final classification

Choose exactly one:

### `INTERNAL_HERMES_REPLACEMENT_READY`

Requires all P0/P1 internal-use criteria green and all six terminal dogfood flows that are applicable to the chosen internal profile.

### `INTERNAL_HERMES_REPLACEMENT_READY_WITH_BOUNDED_LIMITS`

Allowed only when remaining limitations are explicit, operator-acceptable, do not weaken authority/effect/write/secret/recovery guarantees, and are outside the chosen internal workflow. Example: native SwiftUI app incomplete while Textual TUI is fully usable.

### `NOT_READY`

Any unresolved P0 or unaccepted P1.

### `BLOCKED`

Required proof cannot execute because of an external dependency and correctness cannot be established another way.

Do not invent a fifth classification.

---

## 24. Final RETURN block

Return exactly this structure:

```text
TERMINAL SOURCE HEAD:
...

WHEEL SHA-256:
...

SDIST SHA-256:
...

INTEGRATED PR/UPGRADE LINEAGE:
...

REJECTED/SUPERSEDED LINEAGE:
...

FULL SUITE:
...

CAPT_RUNTIME SUITE:
...

SECURITY GATE:
...

AUTHORITY REVIEW:
...

APPROVAL / PREPARED EXECUTION:
...

CONTINUATION CONTEXT:
...

CONTINUATION ARTIFACT INTEGRITY BINDING:
...

LOCAL PROVIDER LIVE:
...

OPENROUTER LIVE:
...

SOFTWARE MUTATION DOGFOOD:
...

ISOLATED WORKSPACE:
...

VERIFICATION BEFORE PROMOTION:
...

PROMOTION DIGEST MATCH:
...

PROCESS RESTART / MODEL B:
...

AMBIGUOUS EFFECT RECOVERY:
...

EXACT REPLAY SECOND EFFECT:
yes/no

SECRET LEAK:
yes/no

TUI DOGFOOD:
...

CAPT-ON-CAPT DOGFOOD:
...

P0 FINDINGS:
...

P1 FINDINGS:
...

P2/P3 BACKLOG:
...

HERMES FALLBACK USED DURING GATE:
yes/no + why

FINAL CLASSIFICATION:
INTERNAL_HERMES_REPLACEMENT_READY | INTERNAL_HERMES_REPLACEMENT_READY_WITH_BOUNDED_LIMITS | NOT_READY | BLOCKED

EXACT INTERNAL CUTOVER COMMANDS:
...

ROLLBACK COMMANDS:
...

NEXT ACTION:
...
```

---

## 25. Definition of done

This workflow is complete only when the conclusion is grounded in **one exact terminal installed artifact**, not a mosaic of green results from different historical heads.

The decisive question is not:

> "Did CAPT's tests pass?"

It is:

> **"Can I stop opening Hermes tomorrow, hand CAPT a real internal software job, kill/restart/switch models when needed, trust its authority/evidence/replay boundaries, and get a verified promotable result without hidden manual glue?"**

If yes, cut over.

If no, keep fixing until the answer is yes or a concrete external blocker makes further proof impossible.
