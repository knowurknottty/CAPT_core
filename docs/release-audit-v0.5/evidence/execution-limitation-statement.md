# CAPT Standalone Harness v0.5 — Execution Limitation Statement

SHA-bound to: b45c4b005c9171172d055697a55034006bb0f2fe
Date: 2026-08-05

## What the installed product provides (proven)
Installed CAPT Solo 0.5.0 (wheel sha256
348fe9da477e0323d9c9b294677a1e10de4f9245373a27300367a9e8bdf879b3)
provides a standalone authenticated headless CAPT runtime:

- `capt harness start|health|capabilities|command|stop` over a
  token-authenticated Unix-domain socket (single-user macOS operator).
- Governed operator commands: create_mission, submit_approval_decision,
  cancel_task, cancel_driver_run, update_memory_trigger_policy,
  run_fixed_openharness_inspection, run_approved_hermes_inspection,
  checkpoint_runtime, shutdown, resume_runtime.
- A PACKAGED MODEL-CAPABLE ExecutionDriver (`hermes`): the governed
  `run_approved_hermes_inspection` command runs a REAL external model
  backend (Hermes CLI; backend owns inference only). The objective is
  persisted in the CAPT Task aggregate; the frozen ExecutionDriverWorkOrder
  carries missionId/taskId references; TaskResolver resolves the
  authoritative task inside CAPT's trusted boundary; the bounded prompt
  is derived inside CAPT; driver output enters as untrusted; CAPT
  verifies (repo unchanged, no git mutation, artifact digest), applies
  ClaimGuard, persists the claim and checkpoint, and returns a
  classified receipt.
- Full installed lifecycle proven end-to-end: start -> health ->
  capabilities -> real model task -> verification/claim/checkpoint ->
  idempotent replay (no re-execution) -> second distinct model task ->
  checkpoint -> stop -> restart on same ledger (chain digest matches) ->
  resume (not_repeated) -> third model task after restart -> clean stop.

## Limitations (documented, non-blocking for v0.5)
1. Model backend is Hermes CLI 0.20.0 (an external process). CAPT owns
   runtime/lifecycle; the backend owns inference only. The installed
   wheel does NOT bundle or vendor a model; it requires the operator's
   Hermes installation (or another external model-capable driver).
2. No OpenAI-compatible packaged CAPT driver exists (LM Studio endpoint
   was live during the proof but is not wrapped in a CAPT driver).
3. ClaimGuard accepts only the bounded M0-B allowlisted statements; the
   model task claim is the allowlisted "Repository inspected in
   read-only mode." — proportionate to the evidence, no overclaims.
4. Operator identity is the local macOS user (operator-<user>), bound
   per authenticated session. No enterprise identity, multi-user, or
   tenant isolation claim is made.
5. Verification requires a clean worktree (git status --porcelain empty);
   session-local files must be gitignored (e.g. .hermes.md) or removed
   before a model task run.
6. Plugin version axis is not established in v0.5 (see version-map.md,
   backlog).
7. Repository-wide lint (Ruff) is not clean (2,721 findings inherited
   from the pre-release baseline). Final quality claims are scoped to
   the targeted harness/model-operator tests and installed lifecycle
   proof, not to repository-wide lint.
8. The fixed-function OpenHarness lifecycle remains the retained
   proven path and is unchanged by the model operator addition.
