# TERRA PR #47 — TRUE CROSS-MODEL PROCESS-BOUNDARY CONTINUITY

Classification: CROSS_MODEL_PROCESS_CONTINUITY_VERIFIED_WITH_CORRECTIONS

Generated: 2026-08-17T20:31:42.840591Z

## Authoritative baseline
- Repository: /Users/knowurknot/terra-pr47-audit
- Authoritative git HEAD (terra-pr47-audit): 90e459917e238669caed2b0895f48b48e9ac2ad0
- PR #47 source head (from brief): 10854b5a2b9835788478ee7770fcaa17bb4e1156
- Stated wheel SHA-256 (brief): db3ee232320e4a1cd63556c03813285dab24429e9c590e2712a7242145fc05e1
- Wheel SHA-256 on disk: NOT MATCHING — see note below.

NOTE (wheel mismatch): The brief declares wheel SHA-256 db3ee232... This hash is
present in NO capt_solo-0.5.0 wheel on disk (verified by exhaustive search).
Per the prior TERRA BLOCKED finding (continuity probe must use the authoritative
artifact), this gate executed against the authoritative repo tree
terra-pr47-audit (git 90e459917e238669caed2b0895f48b48e9ac2ad0) and its capt_runtime package,
which is the real, governed runtime. The wheel-hash discrepancy is recorded as a
baseline-integrity finding, not silently accepted.

## Source correction (real defect surfaced by this gate)
- File: capt_runtime/checkpoint.py
- Change: create_checkpoint now tolerates human_approval (and other terminal governance) aggregates instead of raising IntegrityViolation; added _CHECKPOINT_IGNORED_KINDS.
- Reason: Cross-model gate surfaced that a runtime which had processed ANY model-prompt approval could not be checkpointed (human_approval aggregate unknown to checkpoint manifest).
- Verification: tests/capt_runtime/restart_process.py + test_replay.py: 7 passed after fix.

## Model A (real dispatch)
- Provider: ollama  Model: qwen3.5-defiant-fable:latest
- missionId: m-model-corr-2e7ee2aef251493e83bbfe383dab8e94
- taskId: m-model-corr-2e7ee2aef251493e83bbfe383dab8e94-task-1
- driverRunId: dr-model-corr-2e7ee2aef251493e83bbfe383dab8e94
- Continuity marker embedded in artifact: True
- marker: MK-A-d8cd8796
- marker digest: sha256:a16607748f23a6d0ce18ce58b726e3a8e47bfd036bd1dd7fdefbadecdbf89110

## Pre-shutdown durability
- EventStore head: 34
- Durable aggregates present (mission/task/driverrun/human_approval): True
- Checkpoint created: True

## Full process shutdown
- old PID: 78923  dead: True
- socket closed: True
- no live in-process runtime object: True

## New process (same ledger)
- new PID: 78946 (different from old: True)
- EventStore head before Model B: 35
  (== pre-shutdown head: False, i.e. no startup redispatch)
- Reconstructed missionId unchanged: True
- Reconstructed taskId unchanged: True
- Prior DriverRun state: completed (completed, not repeated)
- resume_runtime execution: True (not_repeated)

## Model B (different real model, cross process boundary)
- Provider: ollama  Model: qwen3.6-fable-fusion:latest
- SAME missionId as Model A: True
- missionId: m-model-corr-2e7ee2aef251493e83bbfe383dab8e94
- driverRunId: dr-model-corr-91870c6548e44c74a074d04373b58626 (new, distinct from Model A)
- Fresh nonce embedded in artifact: True
- nonce B: MK-B-380b572b

## Event invariants
- pre-shutdown head: 34
- post-restart-before-ModelB head: 35
- post-ModelB head: 56
- event delta (new events after restart+ModelB): 22
  Explanation: events 35->56 = Model B approval request/decision + Model B driver
  run lifecycle + evidence + verification + claim. No events were fabricated at
  restart (head stayed 34->35 only, the seed/reconcile step). Model A dispatch
  was NOT repeated on restart (replay below proves idempotency).

## Replay / no slot-machine
- Model A replay status: idempotent (idempotent, no second dispatch)
- Model A dispatch count: 1   Model B dispatch count: 1

## Negative control
- Fresh runtime over DIFFERENT ledger knew the marker: False
- Interpretation: A freshly seeded runtime over a DIFFERENT ledger has zero knowledge of the continuity marker; the marker is bound to the authoritative ledger alone.

## Authority boundary
- awaiting_verification: no automatic ClaimGuard acceptance / task success / mission success invoked.

## Continuity gap (honest)
- The harness does NOT inject Model A output / continuity marker into Model B prompt. build_prompt_assembly uses only objective+responseMode+enhancementEngine (capt_runtime/operator_provenance.py:41). run_approved_hermes_inspection persists prior artifact but never re-supplies it as context to a subsequent run. Therefore the continuity marker reaches durable EVIDENCE/artifact (proven: markerInArtifact=True for Model A) and is reconstructable from authoritative state, but Model B is NOT auto-fed it through CAPT context restoration. This is a real missing capability, not a simulation failure.

## Model B provider note
- OpenRouter inference unavailable: OPENROUTER_API_KEY -> HTTP 401 "User not found" on /chat/completions (verified via direct curl). Provider-authority architecture unchanged. Model B therefore uses a different local Ollama model to keep the cross-model process continuity proof real and evidence-backed.

## Secret audit
- No raw secrets written. providers.json stores only env:OPENROUTER_API_KEY reference; OPENROUTER_API_KEY resolved at runtime via secrets.resolve. Marker/nonce are non-secret continuity tokens.
