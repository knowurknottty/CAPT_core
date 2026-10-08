# CAPT One-Off Python Workaround and Missing-Capability Audit — 2026-10-08

## Evidence and limitations
This is a sampled inventory of **actual inspected local files**, not proof that every workaround across the user's disk has been discovered. These scripts must not be executed automatically; inspect source, permissions, and provenance first. A standalone file is *candidate evidence of a gap*, not proof that its feature is missing in canonical CAPT. Existing capabilities must be checked before porting code. Test artifacts and experiment-specific research programs should remain separate.

## Verified repair completed in source
- **P0 stale CAPT workspace IPC:** `capt-workspace-mcp/src/capt_workspace_mcp/runtime_ipc.py` cached a Unix socket after the service endpoint changed. Fresh authenticated `RuntimeClient` worked while the Inversion Commander CAPT read path failed with `runtime socket send failed: Broken pipe`. Patched read-only query to reconnect and retry once; command path now preflights with a read-only identity query and never retries a command after uncertain delivery. `tests/test_runtime_ipc.py` now contains negative cases. Test: **5 passed, 3 skipped** in the connected project's virtualenv. **Not live-validated on the already-running stale workspace plugin until it reloads.**
- **Earlier CAPT Core import issue:** `capt_runtime/cloudflare_resource_adoption.py` imports `tools/backends/cloudflare_resource_inventory.py`. The target module currently exists and `capt_runtime.composition` imports successfully. Historical `capt --help` failure must be recorded, but it is **not a currently confirmed missing module**.
- **Governance approval shorthand:** `CAPT_core/capt_runtime/approval_bundle.py` exists as a provisional module containing exact `AA` / `all approved` recognition, frozen scope preview and atomic EventStore decision logic; **not yet wired into running command API, no live approval authority**. Only explicit listed request IDs; no universal grant.

## Concrete inspected one-off files -> native capability candidate
| Priority | Inspected file(s), under `~/capt-node-workspace` unless noted | Repeatable job / native CAPT destination | Do not do |
|---|---|---|---|
| P0 | `capt_swift_two_cohort_review_20261008.py`; `run-compact-council.py`; `run-direct-final-review.py`; `run-direct-final-review2.py` | One `CouncilMission` setup, inspect, model selection, per-cohort approval, governed dispatch, convergence and claims with one-call-per-cohort accounting | Do not use private direct provider calls as an alternative to RuntimeService approvals |
| P0 | `CAPT_core/capt_runtime/approval_bundle.py` (new provisional), `capt-node-workspace/dispatch_recent10_22v_cohorts_approved.py` | Exact-scope, atomic, reviewed `ApprovalBundle` for `AA`/all approved with digest, expiry, per-child idempotency and cost policy | No auto-approval, no global wildcard permissions |
| P1 | `generate_mission_triage_20261008.py` | Native read-only durable Mission/Task/DriverRun triage projection with stale/expired/indeterminate states | Never infer state from last textual message |
| P1 | `live_pi_probe.py`, `live_pi_override_probe.py`, `live-pi-smoke.py`, `live-pi-space-bunny.py` | Native Prompt Intelligence diagnostic/verification command: OFF/AUTO/OMNI/META/FORGE/SIGMA resolved model/provider, fallbacks, before/after receipts | No hidden provider charges, no change to live selected model |
| P1 | `capt-hardening-r2-failover.py`, `capt-hardening-r2-migration.py`, `capt-hardening-r2.py`, `capt-hardening-r2-tests.py` | Typed provider-fallback, migration, and recovery tests in canonical runtime, not recurring search-and-replace repair programs | Never blindly rerun temporary patch scripts on newer branches |
| P1 | `add-authority-tests.py`, `add-authority-tests2.py` | Durable reusable authority/capability contract tests and incident regression harness | Never patch test files to fake green results |
| P1 | `bot_ui_patch.py`, `swift-pi-ux-hardening.py`, `capt-hardening-r2-swift.py`, `capt-hardening-r2-swift-followup.py` | CAPT Swift desktop self-check, contract/parity tests, provider identity/bot registration workflow | Preserve concurrent Swift changes and UI ownership |
| P2 | `capt_missions_tia_accept_20261008.py`, `capt_swift_tia_smoke_20261008.py` | Native AX-driven semantic desktop acceptance, auditable screenshots and reports | No global input injection or spoofed user actions |
| P2 | `inversion-commander-scaffold.py` | Review if scaffolding belongs in CAPT skill/connector registry; source includes base64 payload, manual security review required | Do not execute unreviewed scaffold or paste secrets |
| P2 | `capt-workspace-mcp/.tmp_chatgpt_runtime_snapshot.py`, `capt-workspace-mcp/.tmp_rick_visibility.py` | Structured diagnostics under the maintained workspace plugin with bounded output | Do not merge ad-hoc debug files without provenance and tests |
| Not a generic CAPT gap | `apex-sn1-stage3-20260923/stage4_*.py`, `stage9_*.py`, `stage11_*.py`, `audit_astra44_*.py` | Competition-specific research artifacts. Retain separately unless a reusable, verified algorithmic primitive is discovered | Do not absorb project-specific experiments wholesale |

## Runtime incident / approval and Ouroboros status
1. Four 22-logical-vessel OpenRouter cohort requests were created against the original repositories. The first set used `providerNetworkPolicy=local_only`, and CAPT refused remote OpenRouter dispatch with `REMOTE_PROVIDER_NETWORK_NOT_AUTHORIZED`; **correct fail-closed behavior**.
2. Four corrected requests with `remote_allowed` and `fileMutationAllowed=false`, `shellAccessAllowed=false` were created. The previous check confirmed MiMo approved and other three requested. Do not assume all approved or dispatched unless current authoritative ledger confirms.
3. CAPT's runtime socket was reachable from a **fresh** authenticated client, but the workspace MCP connector received Broken pipe on its pooled connection. Patched in source and added regression tests; reload and then verify on the running connector.
4. Model execution output remains unverified until CAPT DriverRun / evidence / ClaimGuard and human completion decisions.

## Next engineering gates
1. Reload workspace MCP client safely without losing unrelated active sessions; demonstrate live `capt_state_get` read and command preflight after daemon restart.
2. Complete and test `ApprovalBundle` integration into `desktop/m1_command_service.py`, `desktop/capt_runtime_service.py`, and connector profile; add atomicity, replay, expiry, stale digest, scope-widening and wrong-session tests; publish exact diff.
3. Inspect current canonical code before cherry-picking one-off patch scripts. Move **behavior and tests**, not ephemeral script wrappers, into stable modules.
4. Test governed launch with one cohort first. Capture exact authority/cost evidence, then dispatch four concurrently only if all four leases valid and explicitly approved.

## 2026-10-08 follow-up: MCP reload, council execution repair and live dispatch

- MCP reload: the Inversion Commander bridge restarted its supervised lane worker through guru -> pro -> guru mode switches. Fresh RuntimeService reads succeeded.
- P0 bug: desktop/capt_runtime_service.py incorrectly interpreted the opaque cohort configurationId ouro-repair-v1 as reasoning effort, raising REASONING_EFFORT_UNSUPPORTED after consuming approval but before dispatch.
- Source fix: capt_runtime/reasoning.py now has legacy_cohort_configuration_reasoning_effort; desktop/capt_runtime_service.py calls it so arbitrary cohort configuration IDs no longer become provider reasoning knobs. Recognized legacy low/medium/high/xhigh aliases remain supported.
- Verification: 53 passed (test_cohort, test_model_operator, test_cohort_dispatcher, test_council_alpha). CAPT checkpoint accepted, graceful shutdown accepted; capt start returned HEALTHY.
- Failed prior council r3 leases consumed; all four associated DriverRuns were verified failed with dispatchBoundary not_dispatched before new approvals issued.
- Authorized council r4: GLM=dr-model-de984803e1535f1399c9a5eb; MiMo=dr-model-57abab82040be641df04c451; Qwen=dr-model-717f593634c83f8d5133368b; DeepSeek=dr-model-8d2a7d19b597c59fdb8461ee. Each explicitly approved with 22 logical vessels, read/search tools, project scope, remote OpenRouter only.
- Council r4 command exceeded 80-second IPC client timeout. CAPT Node operation remote-capt-20261008T073124Z-d723612a failed with an IPC timeout; do not repeat the exact external dispatch.
- Durable reconciliation: all four r4 DriverRuns crossed provider request_started and some show response_started/response_completed events. GLM and Qwen subsequently transitioned to lost/reconciliation_required; MiMo and DeepSeek last observed running. This is not verified completion.
- P0 accounting finding: multiple provider request_started/response_completed events occur inside individual cohort DriverRuns. A logical cohort does not necessarily equal one external inference request; investigate and enforce physical call/budget ceilings. No claims of four total billed HTTP model requests.
- Next gates: reconcile lost DriverRuns without replaying uncertain requests; inspect verified artifacts, provider costs, and output; add exact retry/cost regression tests. Local source fixes not yet committed.
