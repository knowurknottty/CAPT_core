# Terra Acceptance Closure Matrix — R3 no-repeat pass

Workflow prompt provenance: Treasure Chest
`docs/workflows/prompts/TERRA_ACCEPTANCE_CLOSURE_NO_REPEAT_R3_PROMPT.md` at
`527b535703a902b2e15ea98ffebe0593597129e9`.

CAPT Core branch: `terra/operator-prompt-contract-r5`
Starting/final SHA for this pass: `9ab722e3f637358d5b82acb98ce125bc612aba9d`

## New acceptance evidence

- Installed wheel with dependencies installed in clean venv: PASS.
- Installed `capt tui --help`: PASS.
- Installed `capt tui` started in a PTY and rendered the Textual cockpit/footer
  for over 40 seconds; process was then explicitly terminated by the harness.
- Local Ollama readiness probe: reachable; seven models advertised. No model
  request was dispatched and no credentials were read or recorded.
- Restart/no-repeat/checkpoint and ContextPack suites:
  `58 passed, 10 deselected in 2.06s` from
  `test_replay.py`, `test_desktop_m0.py`, `test_memory_trigger.py`, and
  `test_memory_trigger_hermes.py`.

## Final-mile installed-runtime attempt

An installed-wheel runtime was started at `/private/tmp/capt-final-mile-state`
with `capt start --state-dir ... --seed`. `capt status` reported `HEALTHY`,
`runtimeVersion: 0.1.0`, the installed runtime database path, and the governed
command surface. Installed `capt tui` connected and rendered the cockpit in a
PTY. The automated PTY key sequence did **not** produce a new RuntimeService
command: the ledger head remained `13` and `capt evidence` showed only the
seeded demonstration state. The UI process and runtime were then explicitly
stopped. This is a failed interaction-automation attempt, not provider
acceptance and not evidence of a governed dispatch.

## Exact workflow terminal statuses

| Workflow | Status | Evidence / remaining gap | Falsifier |
|---|---|---|---|
| `OVERNIGHT_TERRA_OPERATOR_PRODUCT_R5_WORKFLOW.md` | `PARTIAL_INSTALLED_FULL_INTERACTION_AND_GOVERNED_PROVIDER_ACCEPTANCE_NOT_EXECUTED` | Installed cockpit launch is proven; full keyboard/mouse provider→run→checkpoint path, response-mode persistence, live governed Ollama/OpenRouter dispatch, and current-run correlation are not. | A successful installed governed run with correlated IDs and inspection output would close the stated gap; a failure disproves readiness. |
| `CAPT_RUNTIME_SKILL_SOURCE_IDENTITY_AND_ENVIRONMENT_ISOLATION_WORKFLOW.md` | `PARTIAL_FULL_WORKFLOW_EVIDENCE_ARTIFACT_NOT_YET_ASSEMBLED` | Source identity and isolated CAPT homes were used in this mission; its dedicated complete acceptance ledger is absent. | A dedicated artifact with path/import/PYTHONPATH/installed-source evidence is required. |
| `CAPT_TEST_ISOLATION_AND_CHECKOUT_HYGIENE_WORKFLOW.md` | `PARTIAL_FULL_WORKFLOW_EVIDENCE_ARTIFACT_NOT_YET_ASSEMBLED` | Tests used temporary `CAPT_SOLO_HOME`; no full clean-checkout/hygiene closure record exists. | A clean-checkout/isolation record with exact commands is required. |
| `CAPT_DISTRIBUTION_ARTIFACT_PARITY_AND_SMOKE_REPAIR_WORKFLOW.md` | `PARTIAL_INSTALLED_TUI_LAUNCH_PROVEN_GOVERNED_INSTALLED_SMOKE_PENDING` | Wheel, clean install, command help, and TUI launch are proven; installed governed provider smoke is not. | A clean installed governed run is required. |
| `CAPT_BRIDGE_RELEASE_CANDIDATE_FINAL_VERIFICATION_WORKFLOW.md` | `PARTIAL_BRIDGE_SPECIFIC_FINAL_ACCEPTANCE_NOT_EXECUTED` | Replay/checkpoint/no-repeat tests pass; bridge release-candidate workflow acceptance was not performed. | Exact bridge handshake/recovery evidence is required. |
| `CORDIS_DONOR_ARCHAEOLOGY_AND_GOVERNED_COMPOSITION_R5_WORKFLOW.md` | `PARTIAL_RUNTIME_HELPERS_TESTED_DONOR_WORKFLOW_NOT_FULLY_CLOSED` | Dependency epoch, world digest, topology anomaly, and runtime debt helpers/tests exist; full donor archaeology/attestation integration is not claimed. | Integration into a governed runtime path with before/mount/unmount attestation is required. |

## Deliberate non-claims

- No OpenRouter credential or live OpenRouter run was attempted.
- No real provider model request was dispatched from the clean installed environment.
- A state flush is not labeled a semantic checkpoint merely because checkpoint
  and no-repeat regression tests passed.
- Existing ContextPack provenance is not represented as a complete derived-
  context lifecycle acceptance without a concrete summarized/pruned specimen.

Final status: `TERRA_ACCEPTANCE_CLOSURE_BLOCKED_GOVERNED_INSTALLED_PROVIDER_AND_FULL_INTERACTION_ACCEPTANCE_PENDING`
