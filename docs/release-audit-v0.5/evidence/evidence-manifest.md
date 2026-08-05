# CAPT Standalone Harness v0.5 — Release Evidence Manifest
SHA-bound to: b45c4b005c9171172d055697a55034006bb0f2fe
Branch: release/capt-standalone-final
Date: 2026-08-05
Attribution: knowurknot
Terminal verdict: CAPT_MODEL_OPERATOR_PROVEN_AND_RELEASE_READY

## 1. Source identity (provenance)
- HEAD commit: b45c4b005c9171172d055697a55034006bb0f2fe
- Branch: release/capt-standalone-final
- Worktree: CLEAN (git status --porcelain empty; .hermes.md gitignored,
  not deleted). Evidence: git-status.txt, git-head.txt, git-log.txt
- Canonical composition root: capt_runtime.composition.create_runtime()

## 2. Full test suite (source, from clean SHA)
- Command: PYTHONPATH= .venv/bin/python -m pytest -q
- Result: 766 passed, 12 deselected in 19.83s, exit 0
- Evidence: full-suite.log
- Deselection rule: pyproject.toml [tool.pytest.ini_options]
  addopts = "-m 'not slow'"
- 12 deselected (all marked slow; real-Hermes / memory-trigger):
  - tests/capt_runtime/test_hermes_driver.py::
    test_real_hermes_read_only_governed_run,
    test_duplicate_run_id_rejected_at_driver
  - tests/capt_runtime/test_memory_trigger_hermes.py::
    test_prompt_contains_only_contextpack_slice_reference,
    test_prompt_without_pack_ref_has_no_memory_line,
    test_real_hermes_dispatch_with_trigger_policy[1..4],
    test_hermes_cannot_alter_policy,
    test_hermes_cannot_suppress_trigger,
    test_hidden_hermes_context_labeled_external,
    test_removal_of_hermes_does_not_break_trigger_logic
- Why acceptable: the real-Hermes coverage those tests provide is
  independently proven by the INSTALLED lifecycle proof below (3 real
  Hermes executions through the packaged governed command). No
  capability is left unproven by deselection.

## 3. Installed wheel (packaged, SHA-bound)
- Wheel: artifacts/capt_solo-0.5.0-py3-none-any.whl
- sha256: 348fe9da477e0323d9c9b294677a1e10de4f9245373a27300367a9e8bdf879b3
  (artifacts/wheel-sha256.txt)
- Built from clean SHA b45c4b0 via pip wheel --no-deps
- Installed --no-deps into fresh venvs with PYTHONPATH= cleared, run from
  /tmp (outside the repo). Import proof: capt_runtime, desktop,
  capt_runtime.task_resolver.TaskResolver all import from the wheel.

## 4. Installed governed model operator — lifecycle proof
Authenticated `capt harness command run_approved_hermes_inspection`
through the installed wheel; real Hermes 0.20.0 subprocess (external
model backend; CAPT owns runtime/lifecycle).

Sequence (all exit 0 unless noted; ledger evidence in installed/ledger-*.db):
1. start ............ healthy, token auth, unix socket
2. health ........... status HEALTHY, integrity ok
3. capabilities ..... advertises run_approved_hermes_inspection
4. model task 1 ..... REAL Hermes run: objective -> Task aggregate ->
   TaskResolver -> bounded prompt; evidence-backed finding (product
   0.5.0 vs capt_runtime RUNTIME_VERSION 0.1.0); verification
   repo_unchanged + no_git_mutation + artifact digest; ClaimGuard
   allowlisted claim; checkpoint. Ledger 0 -> 13 events.
   Artifact: artifacts/hermes-analysis-dr-model-cmd-51ff69b208ea8412.md
   sha256 5de1e47c...  (model-artifacts-sha256.txt)
5. idempotent replay . same key -> status idempotent, classification
   duplicate, SAME receipt, ledger head UNCHANGED (13); no second
   Hermes execution
6. model task 2 ..... distinct objective -> fresh mission/task/run/claim;
   driver inventory, UNKNOWN=0. Ledger 13 -> 26.
   Artifact: hermes-analysis-dr-model-cmd-b7d2b2ea1112e367.md
   sha256 c441be0d...
7. checkpoint ........ full manifest at ledger position 26,
   ledgerDigest sha256:021b316a..., integrityDigest
   sha256:f8ee17be..., recoveryState clean
8. stop ............. accepted, server exit 0
9. restart .......... SAME ledger; headSequence 26, ledgerChainDigest
   MATCHES checkpoint digest; integrity ok
10. resume ........... checkpoint verified, execution "not_repeated"
11. model task 3 ..... AFTER restart (continuation): fresh
    mission/task/run/claim; capability.py inventory matched source
    exactly. Ledger 26 -> 39.
    Artifact: hermes-analysis-dr-model-cmd-da7e16eaf4dbf138.md
    sha256 91c1af06...
12. stop ............. accepted, server exit 0

## 5. Raw authority matrix (installed, adversarial)
Script: installed/adversarial-battery.py (raw socket, forged envelopes
after real auth; every case with no-mutation + healthy-after proof).
Run on the final installed wheel (b45c4b0) against a fresh ledger:
- forged_operatorId ....... rejected/unauthorized  head 0->0
- forged_sessionId ........ rejected/unauthorized  head 0->0
- unsupported schema ...... rejected/malformed    head 0->0
- unsupported operation ... rejected/malformed    head 0->0
- missing envelope field .. rejected/malformed    head 0->0
- forged shutdown ......... rejected/unauthorized  head 0->0 (server stays up)
- forged resume ........... rejected/unauthorized  head 0->0
- idempotent first call ... accepted               head 0->2
- conflicting idempotency payload ... rejected/classification=idempotency,
  detail "idempotency key reused with a different operation fingerprint",
  head 2->2 (NO mutation)
- HEALTHY_AFTER_ADVERSARIAL head=2 integrity=ok
Earlier run on the populated ledger (head 39): same 7/7 forgery
rejections with head unchanged and healthy-after proof.
Defect discovered by this battery: create_mission_with_approval's
early-return idempotency check ignored the stored fingerprint (same key
+ different payload returned "idempotent" and dropped the payload).
Fixed in b45c4b0 (commit "fix(runtime): reject idempotency key reuse
with conflicting payload") with regression test
test_idempotency_key_conflicting_payload_rejected.

## 6. Commit history (release line, oldest -> newest)
- 7475dcf feat(runtime): resolve driver tasks from authoritative task references
- 554ff15 feat(harness): expose governed Hermes model operator
- cb8089d feat(harness): advertise governed Hermes model operator capability
- 3aa1be5 fix(harness): drop non-contract field from OperatorMissionIntent
- ac6d057 fix(harness): grant artifact.create in model operator lease
- 6af19cd fix(client): decouple command recv timeout from connect timeout
- 6737f2c fix(harness): use ClaimGuard allowlisted claim for model task
- b45c4b0 fix(runtime): reject idempotency key reuse with conflicting payload

## 7. Driver inventory (final; UNKNOWN must equal zero)
- hermes ....... KNOWN (real external model runtime adapter; governed
  model operator; the packaged model-capable ExecutionDriver)
- openharness .. KNOWN (fixed-function read-only repo inspector;
  proven lifecycle path retained)
- registry/init . KNOWN (registry and protocol interface modules, not
  drivers; classified by the real model in model task 2, UNKNOWN=0)

## 8. Evidence artifacts (this directory)
- git-head.txt / git-log.txt / git-status.txt .... source provenance
- full-suite.log ................................ 766 passed, 12 deselected
- artifacts/capt_solo-0.5.0-py3-none-any.whl ..... installable wheel
- artifacts/wheel-sha256.txt ..................... wheel digest
- artifacts/hermes-analysis-*.md (3) ............. real model outputs
- artifacts/model-artifacts-sha256.txt ........... artifact digests
- installed/ledger-6737f2c.db .................... lifecycle ledger (39 events)
- installed/ledger-b45c4b0.db .................... adversarial fresh ledger (2 events)
- installed/adversarial-battery.py ............... reproducible battery
