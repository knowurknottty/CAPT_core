# CAPT Core

**Local-first governed runtime, continuity substrate, and operator layer for AI systems.**

> **The model is replaceable. CAPT keeps the state, authority, evidence, memory, and recovery.**

CAPT moves responsibilities that should not live inside a transient model session into a durable local runtime: authoritative state, memory, execution history, governance, evidence, verification, capability control, context policy, checkpoint/recovery, and operator control.

The model is an inference component. **CAPT is the system of record around it.**

---

## Current repository status

CAPT Core has four distinct authority/evidence states that must not be collapsed:

1. **Numbered package:** `pyproject.toml` still declares `capt-solo 0.5.0`; preserved proof under `release_evidence/v0.5/` is historical.
2. **Merged integration `main`:** PR #117 was merged on 2026-08-21, bringing the reconciled provider/native spine, CAPT-UPG-001→019, replay/checkpoint corrections, durable Cohorts + steering, governed artifact promotion, lease controls, forensic/provenance/epistemic/security projections, authored-skill approval binding, and macOS ↔ RuntimeService ↔ MCP authority acceptance onto `main`. Closed-unmerged PR #118's provider/model-coherence semantics are included through that reconciled line.
3. **Release authorization:** exact-head and independent of merge status. The historical merged PR #117 head `570babeef113943860c1268722200a48639e406d` remains a failed Release Security receipt (run `32440329043`). PR #124 closed the applicable Core controls; release-security implementation baseline `2199c036aa22af33fb3eb0700f63f820a35aa55a` is **release-security authorized** by hosted Release Security run `32617740908`, which returned **21 PASS / 0 FAIL / 0 NOT_VERIFIED / 26 NOT_APPLICABLE** with no blockers. M0-A push run `32617740848` also passed on that exact merge SHA.
4. **Separate open work:** CAPT-UPG-020→024, Inversion Labs/Forge edition work, and the public-release design/plan lineage remain independent PR lanes and are not silently counted as released Core functionality.

Release-security authority is **per exact source SHA**. Historical blocked heads remain blocked evidence; a later commit becomes release-security authorized only when its own hosted Security Closure Cockpit returns PASS. Final public artifacts must still be rebuilt and re-hashed from the exact authorized source commit.

See [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md), [`docs/PR_TOPOLOGY.md`](docs/PR_TOPOLOGY.md), [`docs/FUNCTIONALITY_MATRIX.md`](docs/FUNCTIONALITY_MATRIX.md), and [`docs/RELEASE_EVIDENCE.md`](docs/RELEASE_EVIDENCE.md) for the exact boundary.

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
| native SwiftUI / `CAPTNativeMac` | **MERGED / BUILDABLE APPLICATION** |
| true process-boundary cross-model continuity | **MERGED / INTEGRATED; RELEASE PROOF SEPARATE** |

The UI is deliberately thin. **CLI, TUI, and desktop surfaces do not become alternate runtimes.**

Pinned external authored skills are a separate trust class from bundled CAPT operation skills and executable Skill Foundry procedures. CAPT verifies the `CAPT_Skills` release lock, freezes explicitly selected bytes before authoritative mutation, carries them only inside the validated `ContextSlice`, and emits provenance-only receipt evidence. See [`docs/AUTHORED_SKILLS.md`](docs/AUTHORED_SKILLS.md).

---

## Operator surfaces and native macOS convergence

Current `main` includes the Textual TUI/Tk operator foundation and the PR #117 reconciled cockpit/provider/runtime projections, including the real `CAPTNativeMac` application target.

The native app remains a thin RuntimeService client: governed chat/approval flow, runtime/provider controls, encrypted session-cache persistence, typed projections, and origin-session-bound asynchronous configuration updates do not create a second authority plane.

Fresh candidate verification includes **64 Swift tests / 7 deliberate live/cross-surface skips / 0 failures**, strict concurrency + warnings-as-errors PASS, and ThreadSanitizer PASS with no sanitizer finding.

A source-buildable/tested native app is not yet the same evidence class as a signed/notarized/distributed release.

See [`docs/DESKTOP.md`](docs/DESKTOP.md) and [`docs/TUI.md`](docs/TUI.md).

---

## Provider execution status

The terminal convergence provider spine supports governed Ollama and local/authenticated OpenAI-compatible execution, endpoint/model provenance, resource ceilings, and bounded local prewarm.

PR #118 closes a real native-selection defect by keeping global provider/model persistence coherent, backfilling provider defaults without overwriting user configuration, and preserving session-vs-global selection semantics. The false generic native `MLX / mlx_lm` placeholder is retired unless materially configured; a real local OpenAI-compatible MTPLX/MLX service is a separate supported path.

Provider health or model discovery is not itself governed-execution proof. Controlled loopback execution proves authority/transport/idempotency, not model quality or release authorization.

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

Merged `main` moves beyond the old “coordination contracts, durability later” status. It contains durable Cohort EventStore persistence/reconstruction, evidence admission, governed steering, epochs/rounds, stale-result handling, quorum/dissent semantics, and the Cohort Chamber projection.

Cohort consensus remains advisory cognition. It cannot manufacture verification, grant capability, or bypass RuntimeService/EventStore authority. Council-scale public-product orchestration is a later tranche.

---

## Discovery, replay, and execution hardening

Merged `main` contains the reconciled bounded discovery, long-running execution recovery, replay correction, lease governance, artifact promotion, and forensic/provenance projections in one authority spine.

Central rule: **if CAPT cannot prove whether consequential external dispatch occurred, it does not silently replay the work.** Historical replay reconstructs the exact ledger prefix; replay forks create new history without reactivating old approvals/capabilities.

---

## Security posture

CAPT is local-first; local-first is not automatically high-assurance.

Merged `main` includes the 47-control Security Closure Cockpit and substantial hardening—bounded IPC framing, covered rejection auditing, restrictive state permissions, resource ceilings, injection-assurance regressions, one-use exact approval binding, and encrypted native session-cache handling.

Those implementation/test facts are **not** automatically control attestations. For the release-security implementation baseline `2199c036aa22af33fb3eb0700f63f820a35aa55a`, the exact-head Release Security gate is now **PASS**. Core file-backed authoritative EventStore/MemoryStore sensitive content has authenticated at-rest protection, and the configured paid OpenRouter release/runtime credential has provider-side hard-cap evidence plus an independent CAPT spend alert. Open higher-assurance areas still include independently rooted/signed audit attestations, universal process isolation, compromised-host resistance, and final signed/notarized native distribution proof. The release process must still rebuild and re-hash artifacts from the authorized source commit.

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