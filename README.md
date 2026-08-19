# CAPT Core

**Local-first governed runtime, continuity substrate, and operator layer for AI systems.**

> **The model is replaceable. CAPT keeps the state, authority, evidence, memory, and recovery.**

CAPT moves responsibilities that should not live inside a transient model session into a durable local runtime: authoritative state, memory, execution history, governance, evidence, verification, capability control, context policy, checkpoint/recovery, and operator control.

The model is an inference component. **CAPT is the system of record around it.**

---

## Current repository status

CAPT Core currently spans four distinct truth classes:

1. **Numbered package release:** `pyproject.toml` still declares `capt-solo 0.5.0`; preserved release proof lives under `release_evidence/v0.5/`.
2. **Merged `main`:** substantially newer productization code is already merged: normal CLI on-ramp, shared operator layer, provider/model foundations, CaveCAPT verbosity, Textual TUI MVP, Tk operator MVP, SwiftUI client contract, onboarding, and continuity scaffolding.
3. **Active stacked integration:** Discovery, hardened Ouroboros/Hermes lifecycle, prompt/cognitive provenance, upgraded TUI run surface, bounded ProviderDriver, Cohorts, and the fail-closed security gate are being reconciled through the current stack.
4. **Proof/evidence:** a source file, passing unit test, controlled protocol test, installed-runtime run, live-provider run, restart test, and destructive failure-injection test are different evidence classes.

A branch implementation is not described as shipped merely because the code exists.

### Active integration stack

| PR | Area | Current classification |
|---|---|---|
| #44 | Discovery Governor + bounded local scanner | implemented/local evidence; not yet merged |
| #46 | governed Hermes/Ouroboros execution lifecycle | hardened lifecycle/recovery; not yet merged |
| #47 | prompt assembly, cognitive provenance, TUI cockpit, ProviderDriver | **exact-head source/editable full-suite verified; not yet merged; installed/live-provider proof remains separate** |
| #48 | bounded Cohort coordination | coordination contracts; durable runtime integration later |
| #49 | fail-closed SecurityGate | draft; intentionally blocked until applicable controls close |

### Hermes LOCAL-002 metadata status

On 2026-08-17, Terra independently attempted to resolve the operator-supplied LOCAL-002 identifiers. The expected branch `evidence/hermes-local-002-r6`, supplied HEAD `5c8cbf5ec1dfc0034ba7fa0931e21c88fe0cfc04`, and named report `reports/local-evidence/HERMES_AGENT_TUI_WORKSPACE_TESTS_AND_STATE_MAP_8F97AE9_2026-08-17.md` are absent from the current GitHub remote/API.

The previously stated `HERMES_LOCAL_002_COMPLETE`, 98/0/0 focused result, 174/0/2 broader result, npm-version notes, and no-blocker statement are therefore **operator-supplied, currently unverified metadata**, not independently usable evidence.

This does **not** invalidate preserved historical v0.5 Hermes evidence. If LOCAL-002 is later restored and independently verified, it would still be adjacent Hermes workspace evidence only; it would not by itself prove PR #47 exact-head correctness, installed-wheel behavior, live-provider execution, destructive rollback, restart continuity, or release readiness.

PR #47 itself now has separate clean source/editable proof at `4334657a919f74803e65d9b01aa5054d6d7b9a61`: 8 approval-security tests, 31 focused prompt/provider/TUI/operator tests, 18 Ouroboros lifecycle tests, 387 `capt_runtime` passes, and 861 full-repository passes. Installed-artifact/live-provider/restart/destructive proof remains separate.

See [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) and [`docs/RELEASE_EVIDENCE.md`](docs/RELEASE_EVIDENCE.md) for the exact evidence boundary.

---

## Start here

```zsh
git clone https://github.com/knowurknottty/CAPT_core.git
cd CAPT_core
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[ui]'

capt --version
capt doctor
capt start
capt status
```

Exercise durable state:

```zsh
capt memory store "CAPT keeps durable state outside the model."
capt memory search "durable state"
capt evidence
capt checkpoint
```

Launch the merged TUI:

```zsh
capt-ui dashboard
```

Then prove restart continuity:

```zsh
capt stop
capt start
capt resume
capt status
```

For the guided path, use [`START_HERE.md`](START_HERE.md).

---

## What is merged on `main`

### Governed runtime and continuity

- authoritative ordered EventStore history and replay;
- authenticated local RuntimeService IPC;
- mission/task/runtime aggregates and governed state transitions;
- capability grants and bounded leases;
- DriverHost and execution-driver boundaries;
- checkpoint, restart, idempotency, and no-repeat recovery;
- CAPT Solo durable Memory Engine;
- Runtime Memory Governor and ContextPack policy;
- CTP operational transaction/recovery journaling;
- KHSB in-process coordination;
- evidence and verification machinery;
- ClaimGuard;
- proof/workflow/Foundry/Knowledge Bubble components;
- pinned external authored-skill verification and governed `ContextSlice.skillContext`;
- bounded Hermes compatibility execution.

### Normal operator surfaces

| Surface / capability | Merged status |
|---|---|
| `capt` normal CLI | **SHIPPED** |
| runtime lifecycle / evidence / doctor | **SHIPPED** |
| durable memory CLI | **SHIPPED / PROVEN** |
| `capt skills status/list/show` pinned authored-skill inspection | **SHIPPED** |
| shared `capt_ui.operator` facade | **SHIPPED** |
| Textual TUI | **SHIPPED MVP** |
| governed approve/deny in TUI | **SHIPPED MVP** |
| provider registration/configuration | **SHIPPED** |
| provider health/model discovery where supported | **SHIPPED** |
| model selection/favorites/overrides | **SHIPPED FOUNDATION** |
| CaveCAPT Minimal/Normal/Detailed/Diagnostic | **SHIPPED** |
| first-run onboarding | **SHIPPED** |
| Tk desktop operator | **OPERATOR MVP / reference fallback** |
| native SwiftUI | **CLIENT CONTRACT / LIBRARY ONLY** |
| true process-boundary cross-model continuity | **NOT YET RELEASE-PROVEN** |

The UI is deliberately thin. **CLI, TUI, and desktop surfaces do not become alternate runtimes.**

Pinned external authored skills are a separate trust class from bundled CAPT operation skills and executable Skill Foundry procedures. CAPT verifies the `CAPT_Skills` release lock, freezes explicitly selected bytes before authoritative mutation, carries them only inside the validated `ContextSlice`, and emits provenance-only receipt evidence. See [`docs/AUTHORED_SKILLS.md`](docs/AUTHORED_SKILLS.md).

---

## TUI: merged MVP and active cockpit upgrade

The merged Textual TUI already exposes runtime health, mission/task state, memory/context state, providers/models, approvals, evidence/verification, logs, checkpoint/resume/cancel, and CaveCAPT verbosity through the shared Operator facade.

PR #47 adds:

- provider/model selection in the governed run surface;
- response modes `MAX`, `SPOCK`, `CAVE CAPT`, `MIN`;
- requested context budgets 32K–256K;
- enhancement engines `OFF`, `AUTO`, `OMNI`, `META`, `FORGE`, `SIGMA`;
- inspectable enhancement rather than invisible prompt rewriting;
- clarification when the input is underspecified;
- explicit **ENHANCE -> REVIEW -> APPROVE -> RUN** for transformed prompts, with durable RuntimeService approval required for RUN even when enhancement is `OFF`;
- persisted non-secret prompt preferences;
- requested/effective context provenance;
- prompt-assembly digest and cognitive provenance.

The enhancement layer may propose a better prompt. It may not mint capability, bypass approval, write authoritative state, or declare completion.

See [`docs/TUI.md`](docs/TUI.md).

---

## Provider execution status

Merged `main` has provider registration/health/model-discovery/model-selection foundations.

PR #47 adds a bounded ProviderDriver for:

- Ollama native `/api/generate`;
- OpenAI-compatible `/chat/completions`;
- provider/model/endpoint provenance;
- prompt/response digests;
- secret exclusion from artifacts/diagnostics;
- explicit dispatch-boundary tracking;
- truthful cancellation semantics;
- reconciliation of pre-dispatch, response-complete, and externally-unknown states.

Controlled local HTTP tests prove protocol/lifecycle behavior. They are **not** the same as exact-head live-provider installed-runtime acceptance.

See [`docs/PROVIDERS.md`](docs/PROVIDERS.md).

---

## Architecture at a glance

```text
Human / Application / Agent Host
            |
      CLI / TUI / Desktop
            |
      shared Operator facade
            |
      authenticated local IPC
            v
       RuntimeService
            |
  +---------+----------+----------------+
  |                    |                |
EventStore          Governance       Memory/context
runtime history     grants/leases    durable memory
                    approvals        + ContextPack
  |                    |                |
  +---------- governed execution -------+
            |
        DriverHost
            |
  bounded model/tool drivers
            |
   replaceable inference
```

### Authority boundaries

- EventStore owns authoritative runtime event history.
- CTP is an operational transaction/recovery journal, not the runtime ledger.
- KHSB is currently in-process and non-durable.
- durable memory and bounded working context are separate layers.
- evidence is not verification.
- verification is not claim acceptance.
- claim acceptance is not task completion.
- task completion is not mission completion.
- driver output is untrusted until admitted through CAPT boundaries.
- a UI action is a request, not UI-owned authority.
- provider discovery does not prove provider execution.
- synthetic model switching does not prove real cross-model continuity.

---

## Cohorts and multi-perspective cognition

PR #48 introduces bounded CAPT-native Cohort coordination: typed contributions, participant rosters, deliberation epochs, stale-result rules, sequence cursors, silence/positive quorum, material dissent/escalation, cognitive debt, and bounded-incomplete discrimination.

It does **not** yet claim durable Cohort persistence/reconstruction, restart-safe cursors, evidence admission, governed participant scheduling, or installed-runtime/TUI Cohort dogfood.

---

## Discovery and Ouroboros lifecycle hardening

PR #44 adds bounded read-only discovery/SEAL scanning without self-granting capability.

PR #46 hardens long-running governed execution around durable idempotency, dispatch-boundary accounting, lease consumption, cancellation, lost/indeterminate execution recovery, and suspension rather than unsafe redispatch.

Central rule: **if CAPT cannot prove whether external dispatch occurred, it does not silently replay the work.**

---

## Security posture

CAPT is local-first; local-first is not automatically high-assurance.

Current limitations include incomplete CAPT-managed encryption at rest, no multi-user authorization model, no independently rooted signed audit history, incomplete production IPC/resource-ceiling hardening, and incomplete adversarial prompt/context/provider assurance.

PR #49 converts security requirements into fail-closed infrastructure and is intentionally **BLOCKED** until every applicable control has exact-head evidence.

Read [`docs/SECURITY.md`](docs/SECURITY.md) before higher-trust use.

---

## Documentation map

| I want to... | Read this |
|---|---|
| See exact current state | [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) |
| Get CAPT running | [`START_HERE.md`](START_HERE.md) |
| Navigate all docs | [`docs/README.md`](docs/README.md) |
| Understand CAPT in one screen | [`docs/MENTAL_MODEL.md`](docs/MENTAL_MODEL.md) |
| Use the TUI | [`docs/TUI.md`](docs/TUI.md) |
| See capability truth | [`docs/CAPABILITY_MATRIX.md`](docs/CAPABILITY_MATRIX.md) |
| See operator/runtime functionality | [`docs/FUNCTIONALITY_MATRIX.md`](docs/FUNCTIONALITY_MATRIX.md) |
| Configure providers | [`docs/PROVIDERS.md`](docs/PROVIDERS.md) |
| Inspect UI acceptance | [`capt_ui/ACCEPTANCE_STATUS.md`](capt_ui/ACCEPTANCE_STATUS.md) |
| Run workflows | [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) |
| Run demos | [`docs/DEMOS.md`](docs/DEMOS.md) |
| Troubleshoot | [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) |
| Understand architecture | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Review security | [`docs/SECURITY.md`](docs/SECURITY.md) |
| Inspect evidence | [`docs/RELEASE_EVIDENCE.md`](docs/RELEASE_EVIDENCE.md) |
| Read the whitepaper | [`docs/WHITEPAPER.md`](docs/WHITEPAPER.md) |
| See agent/provenance rules | [`AGENTS.md`](AGENTS.md) |

---

## Release semantics

CAPT intentionally uses stricter language than “the code exists”:

```text
implemented
 -> locally tested
 -> integrated
 -> exact-head verified
 -> installed-runtime verified
 -> live external dependency/provider verified (when applicable)
 -> release-proven
```

The repository contains work at several stages simultaneously. Public docs should name the stage rather than collapse them into one green checkbox.

---

## Support CAPT

CAPT Core is independently developed open-source infrastructure.

- Solana: `7kgPboqCUY9vUaTSFs1opvfEv86UD1e31ckAPHqgdQuV`
- Bitcoin: `bc1q82dsstmrh9qzpp8gsa8hwzr8t5caj6n0w2w94j`
- Ethereum / EVM: `0xB4E04b51191fB52C5Bae5C2dC4D6457a431d6825`

Verify destination addresses before sending. Cryptocurrency transfers are generally irreversible.

## License

CAPT Core is available under the MIT License. See [`LICENSE`](LICENSE).