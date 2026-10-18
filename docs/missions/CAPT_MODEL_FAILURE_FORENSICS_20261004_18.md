# CAPT model-execution reliability investigation — October 4–18, 2026

**Evidence**: read-only audit of authoritative CAPT RuntimeService ledger, event transitions, eight encrypted immutable provider diagnostics, and nested tool-settlement events. Complete per-run timeline: `~/capt-node-workspace/model-failure-audit-20261004-18/model_run_timeline.json` and `model_runs.tsv` on the operator's Mac. Independent Hermes / provider billing logs not exhaustively reconciled.

## Quantified results

During October 4–18, CAPT created/transitioned **93 provider DriverRuns**: 50 completed, 33 lost/reconciliation-required, 8 failed, 2 cancelled. Lost runs are **not** billable-safe to replay without provider-side reconciliation. Eight lost runs have a sanitized provider-failure diagnostic.

| UTC date | Run | Approved provider / model | HTTP/phase | Physical attempts |
|---|---|---|---|---:|
| Oct 8 | dr-model-e9cbd12292d3706ecd8ad60a | DeepSeek V4 Flash 0731 `:free` | 404 headers | 1 |
| Oct 10 | dr-model-1c2a7430573c02dcf3fa56fd | DeepSeek V4.1 Flash | 402 headers | 1 |
| Oct 11 | dr-model-64f428677078311ceb163b0f | Xiaomi MiMo 2.6 Flash | 402 headers | 1 |
| Oct 12 | dr-m-capt-donor-convergence-r1-glm53-flash | GLM Flash cohort; exact approval binding not resolved | 400 headers | 24 |
| Oct 13 | dr-model-f5086e13545fb67dfab0ec67 | DeepSeek V4.1 Flash | response-body timeout | 1 |
| Oct 17 | dr-model-809f9cd364700c07bac84194 | GLM 5.3 Flash, xhigh reasoning | 400 headers | 13 |
| Oct 18 | dr-model-2a3879f5d9dec026209bdfbb | GLM 5.3 Flash | response completed, then unclassified failure | 5 |
| Oct 18 | dr-model-5b3a17b2c7859e6f8a6e00c6 | DeepSeek V4.1 Flash 1017 | 404 headers | 1 |

In addition: 16 image-generation DriverRuns lost together Oct 7; 9 other unknown-outcome model runs lost Oct 8. Model DriverRun failures before dispatch on Oct 7–9 total 7; one media run failed Oct 17. Two cancelled runs are tracked distinctly. Nested tool terminations in the window: 11 failed file.search, 8 failed terminal.exec, 6 failed file.read, 7 indeterminate terminal.exec. These are **not** independent additional model runs.

## Findings

1. **Unauthenticated IPC probe noise, local defect repaired in this PR.** 17,974 `unauthenticated_ipc_attempt` security rejections in the window (sampling at audit time), with detail `invalid_or_missing_session_token`. `scripts/capt_recover.py::local_runtime()` opened a throwaway socket via `is_live()` before making its *already authenticated* handshake. Each such probe is correctly rejected by RuntimeService; a periodically scheduled caller can account for the approximate one-per-minute rate. Remove only the extraneous preliminary probe; preserve the authenticated challenge and legitimate Node-level liveness checks. The exact scheduled caller remains to be verified.
2. **Post-response content parser defect repaired in this PR.** `ProviderDriver._execute()` no-tool mode took `choice.message.content` directly as a string, though OpenAI-compatible replies may include list-form text parts; later `text.encode()` could raise after a successful response. Use `_final_facing_text` (existing safe helper) and classify no visible answer as `PROVIDER_NO_CONTENT` in `response_body`. This is a *possible* cause of some `response_completed` losses, not demonstrated causality for the Oct 18 GLM incident.
3. **Model catalog mismatch not fixed here.** `deepseek/deepseek-v4-flash-0731:free` and `deepseek/deepseek-v4.1-flash-1017` were absent from `~/.capt/ui/providers.json` when 404s occurred. Public OpenRouter listings currently advertise 1017; the API route `https://openrouter.ai/api/v1` is locally configured. Missing catalog admission/preflight is an observed gap; specific upstream 404 cause needs non-billable provider-model discovery.
4. **402 needs a credit-state gate.** OpenRouter documents this as insufficient credits for the key/account. Refuse further billable attempts with an explicit credit-state diagnostic until balance/route changes, preserving each approval's exact model. Do not auto-spend or change model on user's behalf.
5. **400s must be correlated with per-round request shape.** 24 or 13 physical attempts does not imply 24 identical retries; CAPT can make one HTTP call per tool turn. Invalid tool history, reasoning parameter, overlarge prompt, or provider-specific constraints remain hypotheses without a safe structured request-schema receipt. Do not preserve raw prompts or provider exception bodies in logs.
6. **Unknown outcome needs reconciliation rather than replay.** Keep 33 lost DriverRuns suspended. For Oct 18 GLM response-completed run, inspect authenticated staging artifact and CAPT result-persistence boundary; do not infer that it completed successfully.

## Release and validation

Changes are additive repairs in `capt_runtime/drivers/provider.py`, `scripts/capt_recover.py`, and two existing test modules. No credentials, prompts or private context are emitted. The authenticated RuntimeService handshake, provider Http boundary accounting, token-cost governor, approvals, and provider URL remain unchanged.

New tests cover list-form text output, rejection of reasoning-only content, and ensuring the recovery runtime health check has exactly one **authenticated** socket connection rather than a preliminary probe.

**Observed tests:** 35/35 provider-driver + recovery tests, plus 18/18 physical accounting and local OpenAI-provider tests passed. Local pytest basetemp must be short on macOS to avoid AF_UNIX's 104-byte pathname limit. A failing test caused by the default long pytest temp path is not a production provider failure.

**Remaining gates:** full suite and GitHub CI; catalog/credit preflight; causal attribution of 17,974 IPC probe events to scheduled invoker; account/provider transaction reconciliation for lost runs; exact post-restart release verification. No automatic model inference was issued by this audit. No lost runs replayed.
