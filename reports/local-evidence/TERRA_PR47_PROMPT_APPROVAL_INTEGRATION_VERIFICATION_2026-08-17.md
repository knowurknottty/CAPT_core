# TERRA PR #47 Prompt-Approval Integration Verification — 2026-08-17

## 1. Executive Verdict

**NOT_VERIFIED**

PR #47’s focused tests pass and it adds a real RuntimeService-backed approval request and exact digest check. It is not release-ready for its stated exact-prompt/approval scope because the authoritative binding is incomplete, approved requests remain usable after expiry and across arbitrary run identities, and the full repository suite is red at this head.

An independent identity discrepancy also prevents accepting the supplied Hermes evidence as authority: `evidence/hermes-local-002-r6` and commit `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04` are absent from the fetched remote/GitHub object API. The supplied temporary-workflow SHA `e6d47a48f774e0a12ea448ff93c0df4cbac17887` is also absent; Actions run `32018991180` exists but reports head SHA `e6d4faa66f1556f3e6c8fcfd046d4a43a2e4cec5`.

## 2. Exact Repository Identity

| Item | Expected | Observed / evidence |
|---|---|---|
| Repository | `knowurknottty/CAPT_core` | origin `https://github.com/knowurknottty/CAPT_core.git` |
| PR/head branch | `terra/operator-prompt-contract-r5` | remote ref resolves to `e104c4a56dd77604b4396f4e12d62a91864670bc` |
| Head | `e104c4a56dd77604b4396f4e12d62a91864670bc` | exact match; detached audit worktree then evidence branch created from it |
| PR base | `fix/v07-ouroboros-lifecycle-terra` | remote base `533ef470f7ccaf4488922b6d39171eca9ed83a1a`; proven ancestor of head |
| Main baseline | `ffdc41e6b579291b120dc1a23b5d3d0f1461321c` | exact remote match |
| Documentation reconciliation | `d4ae4739dddfd38fece943e3ed75ce3c985da2b3` | object exists locally after fetch; not a claimed current head |
| Hermes evidence | branch/head as supplied | branch did not resolve in `git ls-remote`; supplied SHA absent locally and GitHub API returned 404 |
| Audit source tree before report | clean | `git status --porcelain` empty |

Remote identity of the PR head is proven. The missing Hermes evidence identity is a divergence, not a negative finding about an unseen report.

## 3. Environment

- macOS 26.4.1 (build 25E253), arm64.
- Host Python: 3.9.6. Isolated audit interpreter: `/private/tmp/capt-pr47-e104-venv/bin/python`, Python 3.12.13.
- Isolated editable installation: `capt-solo 0.5.0`, editable project `/Users/knowurknot/terra-pr47-audit`; imports proved from that worktree.
- pytest 9.1.1 in audit venv. Node/npm were not required by the Python PR path and not treated as evidence.
- Base comparison used separate worktree `/Users/knowurknot/terra-pr47-base-audit` at `533ef470...` and a separate venv; source import from that base worktree was explicitly re-proven.

## 4. Five Recursive Review Passes

### Pass 1 — Structural reconstruction

PR #47 has 29 changed files / 2,069 additions / 285 deletions relative to base. The relevant addition is `capt_runtime/prompt_approval.py`, wired through `desktop/m1_command_service.py:34-46,134-143`, `capt_ui/operator/runtime.py:118-122`, and `capt_ui/surfaces/tui/app.py:463-624`.

`request_model_prompt_approval()` creates a durable `HumanApprovalRequest` through `RuntimeService.request_human_approval`, not through TUI state. `RuntimeService.require_approved_prompt_assembly()` is invoked before the runner claims/dispatches the run (`desktop/capt_runtime_service.py:725-734`). The TUI’s receipt is local and is cleared before dispatch (`app.py:557-588`).

Actual intended path, with the important limitation:

```
TUI APPROVE
 -> Operator.request_prompt_approval
 -> RuntimeClient.command(request_model_prompt_approval)
 -> RuntimeCommandService.execute
 -> prompt_approval.request_model_prompt_approval
 -> RuntimeService.request_human_approval (persisted HumanApprovalAggregate)
 -> RuntimeClient.command(submit_approval_decision)
 -> RuntimeService.submit_human_approval_decision
 -> TUI local receipt
 -> RuntimeClient.command(run_approved_hermes_inspection)
 -> RuntimeService.require_approved_prompt_assembly
 -> new mission/task/grant/lease/DriverRun and dispatch
```

### Pass 2 — Contract / authority audit

The UI does not manufacture the persisted `approved` state. The approval request stores request/mission/task IDs, operation, resource/scope, expiry, correlation, and one `promptAssemblyDigest` (`human_approval.py:59-82`). The runtime admission check, however, reads only:

```
state == approved
state.operation == operation
state.promptAssemblyDigest == recomputed_digest
```

(`services.py:741-756`). It does **not** validate `expiresAt` at use, mission ID, task ID, driver-run ID, provider, model, context budget, or human-result-verification setting.

Planner identity derives request/mission/task/driver-run IDs from correlation (`prompt_approval.py:62-69`). Exact command retry is intended to retain correlation; a deliberate new command receives a new RuntimeClient correlation. The inner approval request has a derivative idempotency key (`:approval`) and `replay_policy="never"` (`lines 91-101`). A second deliberate approval can therefore be distinct; it does not collide merely because prompt settings are identical.

### Pass 3 — Adversarial testing

| Case | Expected | Observed | Evidence | Verdict |
|---|---|---|---|---|
| OFF + no approval + RUN | blocked | runtime requires `approvalRequestId` before dispatch | source `capt_runtime_service.py:725-731`; focused tests pass | PASS |
| Enhancement on + no ENHANCE + APPROVE | blocked by TUI | local gate rejects when engine != OFF and `_enhancement_ready` false | `app.py:473-479` | PASS, TUI only |
| Prompt/response-mode/engine mutation | changed digest / blocked | each contributes to canonical assembly | `operator_provenance.py:41-114`; digest mismatch unit test | PASS |
| Provider/model/context-budget/human-verification mutation | must be bound if execution-relevant | omitted from planner and assembly; runner accepts/uses them outside assembly | `prompt_approval.py:52-60`; `operator_provenance.py:104-114`; runner `capt_runtime_service.py:697-715,736-742` | **FAIL: D-01** |
| Altered digest | rejected | `MODEL_PROMPT_APPROVAL_DIGEST_MISMATCH` | temporary direct probe exit 0 | PASS |
| Pending/denied | rejected | state must equal `approved` | `services.py:749-755`; focused negative test | PASS |
| Expired after prior approval | rejected | approved request remains accepted; no use-time expiry test | direct probe: `EXPIRED_USE_ACCEPTED approved`; `services.py:741-756` | **FAIL: D-02** |
| Valid approval with altered mission/task/driver IDs | rejected / IDs bound | admission check ignores all three; local live run progressed beyond admission and created execution state before its deliberately malformed fake executable failed | `services.py:741-756`, runner accepts payload IDs at `689-695`; live probe exit 0 | **FAIL: D-03** |
| Receipt reuse | runtime enforcement required if claimed | TUI clears local receipt once, but RuntimeService does not decrement or reserve an approval use; every new run creates a fresh grant/lease | `app.py:567-568`; `human_approval.py:72` stores `remainingUses` but never consumes it; `services.py:741-756` | OPEN CONTROL GAP / D-03 impact |
| Capability/operation confusion | rejected for different operation | operation exact match | focused unit test and `services.py:752-753` | PASS |

The live altered-ID probe used a fresh local temporary git repo and fake executable only. It did not call an external provider. The normal and altered submissions both passed the approval gate and advanced enough to produce dispatch-related state; both finally failed only because the temporary fake executable was accidentally malformed (`Exec format error`). This is still direct admission evidence, not provider-execution proof.

### Pass 4 — Cross-layer reconciliation

The focused test command is real and green, but test coverage is materially incomplete:

```
/private/tmp/capt-pr47-e104-venv/bin/python -m pytest -q \
 tests/capt_runtime/test_prompt_approval_binding.py \
 tests/capt_runtime/test_prompt_approval_command.py \
 tests/capt_runtime/test_operator_provenance.py \
 tests/capt_runtime/test_provider_driver.py \
 tests/capt_runtime/test_model_operator.py \
 tests/test_prompt_intelligence.py tests/test_tui_dogfood.py
31 passed in 2.52s
```

It does not test provider/model/context/verification binding, use-time expiration, request-to-run mission/task/driver identity binding, approval reuse, or capability advertisement. `test_model_operator.py` substitutes a stub runner for the relay path (`lines 52-80`) and therefore cannot prove runtime admission.

The existing full lifecycle suite is stale against the new mandatory approval behavior. At PR head:

```
python -m pytest -q tests/capt_runtime
374 passed, 15 failed, 12 deselected in 10.61s
python -m pytest -q
848 passed, 15 failed, 57 skipped, 12 deselected in 19.98s
```

All 15 failures are `tests/capt_runtime/test_ouroboros_lifecycle.py`, which invokes `run_approved_hermes_inspection` without an approval request. The same lifecycle suite at the proven base, using source imported from the base worktree, passed `18 passed in 6.31s`. The rejection itself is fail-closed behavior, but shipping a red repository suite and un-migrated authoritative-flow regression tests is a release defect (D-04), not an environmental failure.

The TUI/prompt suite passed:

```
python -m pytest -q tests/test_tui_dogfood.py tests/test_prompt_intelligence.py
12 passed in 1.34s
```

Main documentation at `ffdc41e...` consistently distinguishes merged main, active integration, and release proof. It does not falsely state PR #47 is merged/release-proven. PR #47’s own description correctly discloses capability-advertisement drift and non-proven one-use enforcement, but overstates “exact model-visible PromptAssembly” if that phrase is read to include execution-relevant provider/model/budget/verification settings and run identity.

The unavailable Hermes report cannot support `HERMES_LOCAL_002_COMPLETE` in this verification. Even if later supplied, a Hermes workspace/TUI state-map result would be adjacent evidence; it would not prove PR #47’s Python RuntimeService approval binding, provider execution, installed wheel, or this exact head unless its source identity and commands establish those facts.

### Pass 5 — Release-gate re-review

Fresh re-review preserved these independent conclusions: (1) runtime durable approval exists; (2) the digest correctly protects fields that the current canonical builder actually includes; (3) the digest does not bind several execution-relevant fields; (4) expiry and run identity are not checked at use; (5) normal RuntimeClient retries create new approval requests rather than idempotent replay because correlation changes; (6) Hermes dispatches a larger unbound prompt; (7) the command surface accepts but does not advertise the new operation; and (8) full regression is red. No authoritative source was changed.

## 5. Approval / Digest Binding Analysis

`build_model_operator_prompt_assembly()` is called by planner with only `human_prompt`, `response_mode`, and `enhancement_engine` (`operator_provenance.py:104-114`). It uses static digest inputs:

- `digest({"context":"not-selected-at-admission"})` (`line 16`)
- `digest({"operations":["RepositoryRead","FilesystemRead","ArtifactCreate","AnalysisOnly"]})` (`lines 17-19`)

The runner independently rebuilds the same static assembly (`capt_runtime_service.py:716-721`), so planner/runner serialization matches for those three mutable fields plus the static references. It does not encode provider ID, model, requested/effective budget, human verification, target root, or mission/task/driver-run identity. The runner uses provider/model/budget/verification after its approval check (`lines 697-715,736-742`). Thus identical digest is not sufficient evidence of identical planned execution.

## 6. Integration Evidence

| Scope | Status | Evidence |
|---|---|---|
| Unit / focused slice | PASS | 31 passed / 0 failed / 0 skipped, 2.52s |
| RuntimeService persisted approve/reload and changed digest | PASS, bounded | `test_prompt_approval_binding.py`; direct expiry probe disproves full expiry semantics |
| Command service | PASS, bounded | request command accepted and creates persisted request; test is narrow |
| TUI receipt behavior | PASS, local facade only | 12 TUI/prompt tests; local invalidation and consume behavior present |
| Real socket command admission | PASS, bounded | request accepted while capability omitted; altered identities crossed approval gate |
| Full capt_runtime | FAIL | 374 passed / 15 failed / 12 deselected, 10.61s |
| Full repository | FAIL | 848 passed / 15 failed / 57 skipped / 12 deselected, 19.98s |
| Live provider | NOT PROVEN | no configured provider invoked |
| Installed wheel | NOT PROVEN | editable install only; no wheel build/install test |
| Restart continuity for this slice | NOT PROVEN | stale old lifecycle tests do not create approvals; no approved Model-A→restart→Model-B evidence |

## 7. Capability Advertisement Audit

**Defect class:** runtime capability/introspection drift.

`RuntimeCommandService._VALID_OPS` accepts `request_model_prompt_approval` (`desktop/m1_command_service.py:34-46`), and a live socket command returned `accepted`. `RuntimeQueryService.handle({"op":"capabilities"})` omits it from `commandOperations` (`desktop/capt_runtime_service.py:512-518`). Live result: `ADVERTISED False`, then `ACCEPTED accepted True`.

Consumers found: `Operator.status()` exposes the list in raw status (`capt_ui/operator/runtime.py:80-90`) and `capt_cli.py:499-508` projects the first eight operations. Current TUI execution does not gate or dispatch based on this list, so it does not break the current direct TUI path. It does break truthful discovery/onboarding and external capability-respecting clients: they will conclude the accepted command is unsupported. Mechanical fix: add `request_model_prompt_approval` to `desktop/capt_runtime_service.py`’s `commandOperations` list and add a socket-level regression asserting set equality or at minimum containment of every `_VALID_OPS` command.

Severity: **medium** by current direct-TUI impact; release-blocking only together with the more serious D-01–D-04 defects, not alone.

## 8. Defects

### D-01 — HIGH — incomplete approval digest binds a different execution

- File/symbol: `capt_runtime/prompt_approval.py:52-60`; `capt_runtime/operator_provenance.py:104-114`; `desktop/capt_runtime_service.py:697-721,736-742`.
- Reproduction: approve a given objective/response/engine, then change provider, model, requested context budget, or `humanVerificationRequired` in the run payload.
- Expected: all execution-relevant inputs admitted by approval are either included in one canonical approval binding or rejected when changed.
- Observed: planner and runner assembly digest remain unchanged while runner uses the changed settings.
- Impact: a durable approval can authorize a materially different provider/model/budget/verification configuration than the operator reviewed.
- Recommended correction: define one canonical planned-execution/PromptAssembly input containing every execution-relevant setting; construct it once or prove byte-identical planner/runner construction; add mutation-matrix tests at actual runner admission.

### D-02 — HIGH — expiry is enforced only at decision, not at execution

- File/symbol: `capt_runtime/aggregates/human_approval.py:108-114`; `capt_runtime/services.py:741-756`.
- Reproduction: approve before `expiresAt`, then call `require_approved_prompt_assembly` after expiry.
- Expected: expired approval is rejected/transitioned before dispatch.
- Observed: direct probe printed `EXPIRED_USE_ACCEPTED approved`.
- Impact: nominal 15-minute approval window is not a runtime admission boundary.
- Recommended correction: inject/obtain authoritative current time at use; reject or durably mark expired before returning approval; test pending, denied, expired-before-decision, and expires-after-decision/before-use.

### D-03 — HIGH — approval request does not bind planned mission/task/driver run and has no runtime use consumption

- File/symbol: `capt_runtime/services.py:741-756`; `desktop/capt_runtime_service.py:689-695,725-731`; `capt_runtime/aggregates/human_approval.py:72`.
- Reproduction: use an approved `approvalRequestId` with new lower-case mission/task/driver-run IDs and a fresh run idempotency key.
- Expected: exact planned identities are bound to request and one intended execution, or runtime non-enforcement is prevented/explicitly constrained.
- Observed: `require_approved_prompt_assembly` checks neither identities nor remaining uses. The live socket altered-ID command passed admission and progressed to execution setup; only the intentionally malformed temporary executable failed later. `remainingUses` is stored optionally but never consumed.
- Impact: one approved digest/request can authorize independent executions and state correlation different from the request the human approved.
- Recommended correction: bind and verify mission/task/driver-run (and appropriate execution correlation) at admission. Decide and implement explicit runtime single-use/lease semantics or hard-limit/document the safely enforced scope; add replay and competing-run tests.

### D-04 — HIGH — full regression suite is red at PR head

- File/symbol: `tests/capt_runtime/test_ouroboros_lifecycle.py` (15 failures).
- Reproduction: full repository command above.
- Expected: existing governed lifecycle tests are migrated to create/approve the new mandatory receipt or otherwise updated to test the new fail-closed contract.
- Observed: 15 failures at head, versus `18 passed` for this suite at base.
- Impact: no suite-green release evidence; formerly tested lifecycle/restart behavior is not tested through the new approval gate.
- Recommended correction: update lifecycle helpers to request and approve exact receipt before every authorized run; preserve explicit no-approval negative tests; rerun full suite.

### D-05 — MEDIUM — accepted command missing from self-description

- File/symbol: `desktop/capt_runtime_service.py:515` vs `desktop/m1_command_service.py:34-46`.
- Reproduction: live capability query and live command result above.
- Expected: accepted command advertised.
- Observed: omitted.
- Impact: discovery/onboarding/external clients honoring capabilities fail closed incorrectly.
- Recommended correction: mechanical list update plus socket-level regression.

### D-06 — HIGH — normal RuntimeClient approval retry is not idempotent

- File/symbol: `capt_runtime/prompt_approval.py:62-69,91-101`; `desktop/desktop_runtime_client.py:119-144`.
- Reproduction: send `request_model_prompt_approval` twice through the real RuntimeClient with identical payload and idempotency key. Live result: both receipts `accepted`; `approval-model-corr-ffc4...` and `approval-model-corr-dbda...` were distinct.
- Expected: an exact retry returns the same durable request / idempotent receipt, as planner comments claim.
- Observed: RuntimeClient creates a fresh random correlation per invocation, while planner derives request and inner idempotency identities from correlation. The outer approval command itself is not durably claimed.
- Impact: retry produces duplicate approval requests instead of stable replay, undermining audit correlation and the stated retry contract.
- Recommended correction: preserve correlation across an exact idempotency retry, or derive approval identity from a durable command identity and claim the outer command before planning; add an actual RuntimeClient retry regression.

### D-07 — HIGH for Hermes / MEDIUM for provider — approved text is not the actual Hermes dispatch prompt

- File/symbol: `desktop/capt_runtime_service.py:716-735`; `capt_runtime/drivers/hermes.py:167-229,345-380`; `capt_runtime/drivers/provider.py:115-136`.
- Reproduction: trace the runner: it persists `modelVisiblePrompt` as task objective, then Hermes wraps that objective with target/path/tool/budget/read-only instructions using `build_prompt` before external dispatch.
- Expected: approval binds a digest of the actual model prompt admitted at the external boundary, or explicitly limits its claim to the smaller objective projection.
- Observed: Hermes has a distinct larger prompt without an actual-prompt digest or equality check. Provider diagnostics hashes submitted text, but that digest is not persisted/compared to the approval’s `modelVisiblePromptDigest`.
- Impact: the PR claim “exact model-visible PromptAssembly” is false for Hermes and only dataflow-inferred for provider.
- Recommended correction: construct and approve the complete driver-specific prompt at admission, or bind a canonical immutable prompt manifest and record/compare the exact dispatched prompt digest per driver.

### D-08 — MEDIUM — caller-supplied request ID can recreate an existing approval aggregate

- File/symbol: `capt_runtime/prompt_approval.py:65-69`; `capt_runtime/services.py:668-696`.
- Reproduction: submit an intent containing a pre-existing `requestId` under a new correlation/derived inner idempotency key.
- Expected: an existing approval stream is rejected or idempotently replayed; terminal approved state cannot be recreated as requested.
- Observed: planner accepts caller request ID; `_append_request_human_approval` uses the current aggregate version and unconditionally applies `HumanApprovalAggregate.create`, which produces `state="requested"`.
- Impact: authenticated callers that know a request ID can at least reset/replace its projected approval state; exact exploitability depends on ingress authorization, but the aggregate creation lacks a first-create guard.
- Recommended correction: reject existing request IDs unless the durable command fingerprint/idempotency proves a replay; add terminal-state and concurrent-create tests.

### D-09 — MEDIUM — living documentation asserts unavailable Hermes evidence is a pushed branch

- Files/symbols: `README.md`, `docs/CURRENT_STATE.md`, `docs/RELEASE_EVIDENCE.md`, `docs/TUI.md`, and `docs/PROVIDERS.md` at main `ffdc41e...` name `evidence/hermes-local-002-r6`, `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`, and the requested report as a dedicated pushed record.
- Reproduction: `git ls-remote origin refs/heads/evidence/hermes-local-002-r6` returned no ref; local object lookup and GitHub commit/branch API returned missing/404; the named report is absent from PR head and main.
- Expected: present-tense public evidence claims resolve to a remote ref/object/report, or are explicitly marked unavailable/pending propagation.
- Observed: current remote state contradicts the public “dedicated pushed branch” availability assertion.
- Impact: `HERMES_LOCAL_002_COMPLETE` cannot currently be independently inspected; its stated test counts are documentation assertions, not usable evidence.
- Recommended correction: restore/publish the exact evidence branch and report, or amend living docs to label the evidence unavailable and keep its scope adjacent to—not proof of—PR #47.

## 9. Non-Blocking Observations

- TUI local receipt invalidation covers prompt, provider, model, response mode, context budget, enhancement engine, and human-verification checkbox. This is useful UX safety, not authoritative enforcement against a direct client.
- `humanVerificationRequired` is semantically separated from the authorization decision in the UI and provenance. Its value nevertheless influences execution/provenance and is currently unbound, which is D-01.
- `CaptTUI._dispatch_run` bypasses the `Operator` facade and calls `self._op.client.command(...)` directly (`capt_ui/surfaces/tui/app.py:607-624`) because the facade has no `run_approved_hermes_inspection` method. This does not bypass RuntimeService approval, but it is a maintainability/consistency risk: future facade policy/telemetry/validation would be silently skipped.
- `commandOperations` also unconditionally advertises injected runner commands. A standalone `RuntimeCommandService` can reject `run_approved_hermes_inspection` as `HERMES_DRIVER_UNAVAILABLE`; normal `serve()` wires it. This is a second self-description precision weakness, not evidence the normal socket server lacks the runner.
- `Operator.store_memory` directly instantiates and mutates `MemoryEngine` (`capt_ui/operator/runtime.py:172-196`), contradicting the facade module claim that all mutations route through governed command operations. It is outside the prompt-approval path but should be separately reviewed as an authority-boundary claim defect.
- The exact provided PR head contains no temporary workflow file. Historical Actions exists, but its recorded SHA differs from the supplied claimed temporary commit; it cannot independently prove e104 without a tree/diff equivalence demonstration.

## 10. Remaining Gates

Not proven in this pass:

1. Installed-wheel verification of this prompt-approval slice.
2. Live-provider acceptance at `e104...`.
3. Model A → runtime restart → Model B continuity through approved receipts.
4. Destructive external-provider/tool-kill rollback E2E.
5. #49 security gate closure.
6. Cohort durable persistence/reconstruction/evidence admission.
7. Native desktop `.app` completion.
8. Runtime-level one-use approval consumption / universal approval-use count enforcement.
9. Authenticity or contents of the stated Hermes evidence report.

## 11. Final Release-Gate Recommendation

**NOT_READY**

Do not proceed to terminal integration validation as a release gate until D-01 through D-04 are corrected and re-tested. D-05 is mechanical and should be corrected in the same implementation pass, but it is not the highest-risk issue.

The narrowest safe priority is to make the approval object bind the full planned execution identity/configuration and enforce expiration/use at authoritative admission; then migrate the old lifecycle tests to exercise that new path. Only after that should capability advertisement be synchronized and full/installed/live-provider validation be attempted.
