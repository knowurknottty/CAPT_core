# CAPT-UPG-006–009 Convergence Reconciliation

Date: 2026-08-19

Integration branch: `integration/capt-core-main-convergence-r1`

Current integration parent: `649cf91`

CAPT provenance mission: `mission-main-convergence-7f16527a311c`

## Disposition

- CAPT-UPG-006: `SUPERSEDED_BY_STRONGER_CURRENT_PROVIDER_EVIDENCE`
- CAPT-UPG-007: `SUPERSEDED_BY_STRONGER_CURRENT_CROSS_MODEL_CONTINUITY`
- CAPT-UPG-008: `SUPERSEDED_BY_STRONGER_CURRENT_OUROBOROS_RECOVERY`
- CAPT-UPG-009: `IMPLEMENTED_ON_CURRENT_SPINE_WITH_REPLAY_AND_CHECKPOINT_CORRECTIONS`

No merge-to-main or release authorization is implied.

## UPG-006 — live provider acceptance

The historical UPG-006 branch was blocked for lack of an exercised live provider. The current native/provider spine already has stronger evidence:

- authenticated OpenRouter transport was exercised on the governed provider-authority lineage;
- local Ollama and local OpenAI-compatible provider execution are exercised;
- provider output remains untrusted / `awaiting_verification` rather than auto-verifying itself;
- exact approval use is consumed once and replay does not issue a second dispatch;
- current PR #107 additionally proves credentialless execution only for admitted local loopback OpenAI-compatible endpoints and preserves endpoint-derived provenance.

Replaying the old UPG-006 branch would therefore weaken evidence rather than add capability.

## UPG-007 — Model A → process death → Model B continuity

The historical test proved two model identities across a process boundary. The current cross-model continuation lineage is stronger: prior Model A evidence is selected from durable authoritative state and actually inserted into Model B's governed prompt/context assembly after restart, with trust state and ContextPack digest preserved.

The old branch is retained as history but not transplanted.

## UPG-008 — destructive / ambiguous effect recovery

The current Ouroboros lifecycle already covers the substantive UPG-008 contract and later hardening:

- pre-dispatch failure does not consume authority;
- boundary-crossed / unknowable effects become `indeterminate`;
- a lost run is not blindly redispatched after restart;
- affected tasks become suspended and require reconciliation/cancellation;
- capability use is consumed conservatively where the external effect may have occurred;
- command admission is durable and same-key replay is idempotent while conflicting replay fails closed;
- crash-boundary tests exercise the recovery points.

No stale UPG-008 runtime files were copied.

## UPG-009 — authoritative artifact promotion

UPG-009 is genuinely additive and has been semantically transplanted.

### Authority model

The canonical composed service is now `GovernedRuntimeService`, a subclass of the existing `RuntimeService`, selected at the one composition root. It is not a second runtime or sidecar authority.

Artifact adoption is intentionally distinct from verification and ClaimGuard:

`candidate -> isolated staging -> exact digest evidence -> verification -> promotion prepared -> human/governance authorization -> atomic filesystem adoption`

ClaimGuard cannot authorize filesystem adoption. A model/execution plane cannot authorize its own promotion.

### Durable transaction

`ArtifactPromotionAggregate` binds:

- promotion identity;
- candidate/workspace identity;
- exact source path;
- exact destination path;
- content digest;
- claim, verification, and evidence identities;
- preparation, authorization, adoption/discard state;
- mechanical adoption receipt.

Direct legacy promotion helpers refuse consequential `promote` decisions and require callers to use the RuntimeService lifecycle.

Atomic adoption supports crash recovery: if the exact authorized destination already contains the exact authorized digest, recovery returns an `already_present_reconciled` receipt instead of re-copying or inventing success.

### Convergence defects corrected

#### Human approval replay was missing on the current spine

The current runtime/event schema persisted `HumanApprovalRequested`, `HumanApprovalDecided`, and `HumanApprovalConsumed`, and checkpoints recorded `humanApprovalVersions`, but `capt_runtime.replay` had no human-approval reducers and checkpoint replay did not load `humanApprovalVersions`.

A RED regression reproduced the contradiction: a valid consumed approval failed `full_replay` at `HumanApprovalRequested` because replay considered the stream nonexistent.

The integrated replay now reconstructs all three approval events, including one-use consumption, and checkpoint replay includes the approval stream versions.

#### Promotion checkpoints are explicit, not origin-replayed forever

Historical UPG-009 omitted extension streams from the frozen checkpoint contract and rebuilt them from origin. The integrated design instead adds an optional backward-compatible `artifactPromotionVersions` checkpoint field and includes it in checkpoint replay.

This keeps deterministic recovery bounded while preserving compatibility with older manifests that do not contain the optional field.

### Contract evolution

The language-neutral schema now includes:

- `artifact_promotion-*` StreamId;
- `ArtifactPromotionPrepared`;
- `ArtifactPromotionAuthorized`;
- `ArtifactPromotionAdopted`;
- `ArtifactPromotionDiscarded`;
- `ArtifactPromotionState`;
- `ArtifactAdoptionReceipt`;
- optional checkpoint `artifactPromotionVersions`.

Current `HumanApprovalConsumed` contracts remain preserved.

The TypeScript parity harness was also hardened so it rebuilds generated TS before every parity run and discovers every fixture JSON file rather than trusting a stale `dist/` or a fixed fixture list.

## Verification

RED proof before implementation:

- governed promotion tests failed collection because `ArtifactPromotionAggregate` did not exist;
- approval replay regression failed at `HumanApprovalRequested` with a no-prior-state integrity violation.

Focused integrated gate:

- promotion/replay/approval/contracts: PASS;
- TypeScript fixture parity: 21 cases / 0 failures;
- generated contract drift: PASS.

Broad exact working-tree gate:

- Python: `970 passed, 13 skipped, 12 deselected`;
- contract drift: `DRIFT CHECK: OK (11 generated files match the schema source)`;
- Swift: `54 executed, 4 explicit live-runtime skips, 0 failures`;
- `swift build --product CAPTNativeMac`: PASS;
- `git diff --check`: PASS.

## Remaining limits

This checkpoint proves the UPG-009 lifecycle in source and deterministic replay. It does not yet claim installed-wheel acceptance of this integration branch, signed-app installation, or an end-to-end native UI promotion workflow. Those belong to the terminal convergence gate after the remaining upgrade stack is integrated.
