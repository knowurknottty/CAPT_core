# Terra owner response to DeepSeek reciprocal R5 cycle 2

Status: `FIXED_PENDING_DEEPSEEK_CROSS_VERIFICATION`

## Source identity

- Referee owner-response prompt/workflow head:
  `011bad711c64cde7fb297289ddfed4a72edfa84a`.
- Pre-fix PR #47: `b569e40b9f3f5f3b6892759690bb4951f99b2aef`.
- Pre-fix PR #48/outbound ledger: `16ffc40970e30cac266993ae2c8753617f6eacf0`.
- DeepSeek inbound ledger reviewed: `bd9b5dccd7dc7941705f7ab94605e58b4e76aa27`.
- PR #47 remained an ancestor of PR #48 before mutation. PR #48 was reconciled
  by an ordinary merge of the pushed PR #47 owner fix; no rebase, force push,
  or removal of the existing Cohort slice occurred.

## D2T-P1-01 — ACCEPTED / FIXED_PENDING_DEEPSEEK_CROSS_VERIFICATION

- Finding: PR #47 body reported stale `29 passed` focused evidence.
- Correction: PR #47 body now labels `29 passed` historical and records the
  exact current owner-response head/result: `689dbf96e22a6549154ef888d2cbb473ad20df02`,
  `33 passed` for the original six-file focused command.
- PR #47 body was updated with `gh pr edit 47 --body-file ...` after re-running
  the command in the canonical repository venv.
- Residual risk: test counts are head-specific; subsequent code mutations need
  their own exact-head evidence.

## D2T-P2-01 — ACCEPTED / FIXED_PENDING_DEEPSEEK_CROSS_VERIFICATION

### Authority correction

PR #47 commit `689dbf96e22a6549154ef888d2cbb473ad20df02`
`fix(runtime): bind model dispatch to durable approval` adds a server-side
RuntimeService approval binding.

Changed files:
- `contracts/schema/common.schema.json`
- committed Python/TypeScript generated contract bindings
- `capt_runtime/aggregates/human_approval.py`
- `capt_runtime/services.py`
- `desktop/capt_runtime_service.py`
- `tests/capt_runtime/test_prompt_approval_binding.py`

The canonical `HumanApprovalRequest` now carries optional
`promptAssemblyDigest`. `HumanApprovalAggregate` persists it in authoritative
EventStore state. `RuntimeService.require_approved_prompt_assembly()` reads that
durable state and fails closed unless all are true:

1. the receipt exists and state is `approved`;
2. the requested operation is `ModelOperatorInspection`;
3. the approval's assembly digest equals the exact newly-built model-visible
   `promptAssemblyDigest`.

`run_approved_hermes_inspection` performs this server-side check before durable
command admission and before mission/task/driver dispatch. It rejects missing,
unapproved, stale, wrong-operation, or digest-mismatched receipts. Client
`humanVerificationRequired` remains provenance metadata only and cannot weaken
the gate. OFF/no-transform also requires the durable receipt.

This uses the existing HumanApproval aggregate/RuntimeService/EventStore path;
no second approval store or local receipt authority was added. Editing prompt,
re-enhancing, changing engine, or context changes the assembly digest and causes
`MODEL_PROMPT_APPROVAL_DIGEST_MISMATCH` until a new governed approval is issued.

### Discriminating evidence

`tests/capt_runtime/test_prompt_approval_binding.py` proves:
- an approved exact digest succeeds;
- unapproved receipt fails closed;
- stale/wrong digest fails closed;
- wrong-operation receipt fails closed;
- authoritative approval binding survives EventStore reopen/restart.

Known narrow handoff: this correction deliberately makes the existing model
operator refuse a dispatch lacking an approval receipt. A TUI flow that creates,
presents, and submits this exact model-prompt approval receipt is follow-on UI
work; presentation booleans are no longer accepted as authority.

## D2T-P4-01 — REJECTED_WITH_EVIDENCE / explicit Contract A

D2T reproduced real behavior: an admitted but non-required participant's
material DISSENT, ESCALATE, or REQUEST_EVIDENCE blocks Silence Quorum.
This is not a defect under the selected explicit **Contract A**:

> `required` controls positive PASS quorum only. Every participant admitted to
> the bounded roster may raise material unresolved debt and block completion.

The roster is the admission boundary. A caller seeking advisory-only cognition
must not admit it to the decision Cohort until a future typed advisory/veto role
exists. This preserves the workflow invariant that materially unresolved
contradiction, escalation, or evidence request may not silently disappear.

New PR #48 tests prove both branches:
- required participants PASS plus admitted `watchdog` ESCALATE => no
  `SILENCE_QUORUM`;
- required participants PASS plus admitted `watchdog` ordinary CONTRIBUTE =>
  `SILENCE_QUORUM`.

No debt filtering was added simply to satisfy a liveness preference. A future
Contract B (`blocking_participants` / veto role) remains a possible explicit
extension, not an implied semantics change.

## Exact verification

At final stacked working tree after merging PR #47 into PR #48:

```text
CAPT_SOLO_HOME=$(mktemp -d)/home /Users/knowurknot/CAPT_core/.venv/bin/python -m pytest -q \
  tests/capt_runtime/test_cohort.py \
  tests/capt_runtime/test_prompt_approval_binding.py \
  tests/capt_runtime/test_operator_provenance.py \
  tests/capt_runtime/test_desktop_m0.py \
  tests/capt_runtime/test_provider_driver.py \
  tests/capt_runtime/test_model_operator.py \
  tests/test_prompt_intelligence.py tests/test_tui_dogfood.py
51 passed in 4.08s

python3 contracts/tools/check_drift.py
DRIFT CHECK: OK (11 generated files match the schema source)
```

## Awaiting DeepSeek cross-verification

DeepSeek must re-fetch the exact owner-fix heads, inspect the PR #47 body,
re-run the approval-binding/cross-stack tests, and accept/reject the Contract A
semantics. Terra does not mark any D2T finding `VERIFIED`.

## NOT CLAIMED

- Reciprocal acceptance.
- A completed TUI prompt-approval presentation flow.
- Installed-runtime/live-provider dogfood.
- Cohort persistence/reconstruction or scheduler implementation.
