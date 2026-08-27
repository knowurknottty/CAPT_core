# CAPT Core

**Local-first governed runtime, continuity substrate, and operator layer for AI systems and bounded tools.**

> **The model is replaceable. CAPT keeps the state, authority, evidence, memory, recovery, and effect history.**

CAPT moves responsibilities that should not live inside a transient model session into a durable local runtime: authoritative state, memory, execution history, governance, evidence, verification, capability control, context policy, checkpoint/recovery, tool-effect reconciliation, and operator control.

The model is an inference component. Tools are effect adapters. **RuntimeService + EventStore + governance are the authority plane around them.**

---

## Current repository status — 2026-08-27

CAPT Core deliberately distinguishes source state from proof state:

1. **Numbered package:** `pyproject.toml` still declares `capt-solo 0.5.0`; preserved `release_evidence/v0.5/` is historical.
2. **Merged Core `main`:** current audit-start head `3aee7370bac880aed99ce3c9ecfaa6d9ff48101e` includes the August 21 convergence plus governed ToolBroker (#126), approved public-release design/plan convergence (#128), and managed authored skills R1 (#129).
3. **Release/security evidence:** authorization is exact-SHA. Historical #117 remains a failed security receipt; `2199c036…` has an exact hosted Release Security PASS; ToolBroker PR #126 head `b21ed6e…` also had hosted M0-A + Release Security PASS before squash merge. Those receipts do not automatically transfer to later SHAs.
4. **Current open Core work:** CAPT-UPG-020→024 (#89/#91/#93/#95/#97). The old Labs/Forge and #111/#116 design PRs are no longer the open Core queue.

At audit start, M0-A push run `32958741310` for `3aee737…` had Python 3.12, contract drift, and TypeScript parity PASS while Python 3.10 failed because the Docker availability probe timed out during test collection. The failed job was retried during this documentation audit; do not infer a green exact-head state from older receipts.

See [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md), [`docs/PR_TOPOLOGY.md`](docs/PR_TOPOLOGY.md), [`docs/FUNCTIONALITY_MATRIX.md`](docs/FUNCTIONALITY_MATRIX.md), and [`docs/RELEASE_EVIDENCE.md`](docs/RELEASE_EVIDENCE.md).

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

Launch the TUI:

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

- authoritative ordered EventStore history and exact-prefix replay;
- authenticated local RuntimeService IPC;
- mission/task/runtime aggregates and governed state transitions;
- capability grants, bounded leases, inspection, and revoke;
- DriverHost and execution-driver boundaries;
- checkpoint, restart, idempotency, and no-repeat recovery;
- durable Memory Engine, Memory Governor, and ContextPack policy;
- CTP operational transaction/recovery journaling and KHSB in-process coordination;
- evidence, verification, ClaimGuard, proof/Foundry/Knowledge Bubble machinery;
- durable Cohorts, evidence admission, epochs/rounds, steering, and Chamber projection;
- governed artifact promotion, forensic flight bundle, provenance DAG, epistemic and security projections;
- bounded Hermes compatibility execution and governed provider execution.

### Governed ToolBroker

PR #126 adds durable `ToolExecution` state and a ToolBroker subordinate to RuntimeService/EventStore authority.

Initial terminal backends are exactly:

- `local`
- `ssh`
- `docker`

The runtime also registers bounded file/code adapters. Consequential execution remains capability/lease governed. Readiness is not effect proof, and indeterminate effects enter reconciliation instead of blind redispatch.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and the ToolBroker implementation/tests for the exact boundary.

### Authored skills

CAPT supports two governed context trust classes:

- **`pinned_external`** — immutable release-pinned authored packs such as `CAPT_Skills`;
- **`managed_local`** — local Agent Skills imported into CAPT-managed state and integrity-bound by manifest/content/tree digests.

Operator surfaces include:

```zsh
# pinned external inspection
capt skills status --root /path/to/CAPT_Skills
capt skills list --root /path/to/CAPT_Skills
capt skills show inversion-creative-director --root /path/to/CAPT_Skills

# managed local pack
capt skills import --source /path/to/skills
capt skills verify
```

Explicit pinned selection outranks contextual managed-local selection. Selected skill context is bound before model approval and revalidated before dispatch. Skill text is guidance only and cannot grant filesystem/network/tool/provider/approval/policy authority.

The current inline contract fails closed rather than truncating a skill above 32,768 characters.

See [`docs/AUTHORED_SKILLS.md`](docs/AUTHORED_SKILLS.md).

### Operator surfaces

| Surface / capability | Merged status |
|---|---|
| `capt` normal CLI | **SHIPPED SOURCE SURFACE** |
| runtime lifecycle / evidence / doctor | **MERGED** |
| durable memory CLI | **MERGED** |
| `capt skills status/list/show` | **MERGED** |
| `capt skills import/verify` | **MERGED** |
| shared `capt_ui.operator` facade | **MERGED** |
| Textual TUI | **MERGED MVP** |
| governed approve/deny in TUI | **MERGED MVP** |
| provider registration/configuration | **MERGED** |
| provider health/model discovery where supported | **MERGED** |
| governed Ollama/OpenAI-compatible execution | **MERGED** |
| model selection/favorites/overrides | **MERGED FOUNDATION** |
| CaveCAPT Minimal/Normal/Detailed/Diagnostic | **MERGED** |
| first-run onboarding | **MERGED** |
| Tk desktop operator | **OPERATOR MVP / reference fallback** |
| native SwiftUI `CAPTNativeMac` | **MERGED / BUILDABLE APPLICATION** |
| ToolBroker local/SSH/Docker terminal execution | **MERGED** |
| true process-boundary cross-model continuation | **MERGED / INTEGRATED; RELEASE PROOF SEPARATE** |

The UI is deliberately thin. **CLI, TUI, desktop, MCP, providers, and tool adapters do not become alternate runtimes.**

---

## Public-release design vs implementation

PR #128 preserves the exact owner-approved public-release design (#111) and implementation plans (#116) on current Core ancestry without importing their stale runtime bases.

That means the plans are current documentation authority. It does **not** mean the planned product features are implemented.

Still implementation-gated unless later source proves otherwise:

- Secure Intake / Quarantine;
- Projects and project-context eligibility;
- human-first results layer;
- composer capability palette;
- Search / Deep Research governed surfaces;
- Cohort Council public product layer.

Merged low-level Cohorts do not by themselves equal the planned Council product.

---

## Architecture at a glance

```text
Human / Application / Agent Host
            |
      CLI / TUI / Desktop / MCP
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
      +-----+------+
      |            |
  DriverHost    ToolBroker
      |            |
 model drivers  tool adapters
```

### Authority rules

- EventStore owns authoritative runtime event history.
- CTP is an operational transaction/recovery journal, not the runtime ledger.
- KHSB is in-process and non-durable.
- durable memory and bounded working context are separate layers.
- evidence is not verification.
- verification is not claim acceptance.
- claim acceptance is not task completion.
- task completion is not mission completion.
- model/tool output is untrusted until admitted through CAPT boundaries.
- a UI action is a request, not UI-owned authority.
- provider/tool discovery or readiness does not prove execution/effects.
- a skill is context, not capability.
- synthetic model switching does not prove every real cross-model boundary.

---

## Provider execution

Merged `main` supports governed Ollama and local/authenticated OpenAI-compatible execution with endpoint/model provenance, resource ceilings, and bounded local prewarm.

The generic direct native `MLX / mlx_lm` placeholder is not represented as a working adapter unless materially configured. A real local OpenAI-compatible MLX/MTPLX service is a supported path through the OpenAI-compatible boundary.

Provider health/model discovery is not itself governed-execution proof, and controlled execution proves authority/transport—not model quality.

See [`docs/PROVIDERS.md`](docs/PROVIDERS.md).

---

## Security posture

CAPT is local-first; local-first is not automatically high-assurance.

Merged source includes the 47-control Security Closure Cockpit, bounded IPC framing, rejection auditing, restrictive state permissions, resource ceilings, injection-assurance regressions, exact one-use approval binding, covered authenticated at-rest protection, ToolExecution reconciliation, and authored-skill anti-drift.

Security evidence is exact-source. `2199c036…` has an authorized hosted closure receipt; the ToolBroker PR #126 head `b21ed6e…` also has exact-head hosted M0-A + Release Security PASS. Later commits do not inherit those labels automatically.

Open higher-assurance areas include independently rooted/signed audit attestations, universal process isolation, compromised-host resistance, multi-principal isolation, exactly-once arbitrary external-effect proof, and final signed/notarized distribution evidence.

Read [`docs/SECURITY.md`](docs/SECURITY.md).

---

## Current open Core lane

As of 2026-08-27, the open Core PR lane is:

- #89 — CAPT-UPG-020 reciprocal-review benchmark;
- #91 — CAPT-UPG-021 sparse symbol-index probe;
- #93 — CAPT-UPG-022 Tree-sitter structural-hash probe;
- #95 — CAPT-UPG-023 FastCDC/content-defined chunk probe;
- #97 — CAPT-UPG-024 cognitive-debt cockpit.

Treat those as separate benchmark/probe work until semantically reconciled and proven against current `main`.

The Inversion Labs/Forge branch lineage is separate edition/history work, not the current open Core-main queue.

---

## Documentation map

| I want to... | Read this |
|---|---|
| See exact current state | [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) |
| See PR/branch routing | [`docs/PR_TOPOLOGY.md`](docs/PR_TOPOLOGY.md) |
| Get CAPT running | [`START_HERE.md`](START_HERE.md) |
| Navigate all docs | [`docs/README.md`](docs/README.md) |
| Understand CAPT in one screen | [`docs/MENTAL_MODEL.md`](docs/MENTAL_MODEL.md) |
| Use authored skills | [`docs/AUTHORED_SKILLS.md`](docs/AUTHORED_SKILLS.md) |
| Use the TUI | [`docs/TUI.md`](docs/TUI.md) |
| See capability truth | [`docs/CAPABILITY_MATRIX.md`](docs/CAPABILITY_MATRIX.md) |
| See operator/runtime functionality | [`docs/FUNCTIONALITY_MATRIX.md`](docs/FUNCTIONALITY_MATRIX.md) |
| Configure providers | [`docs/PROVIDERS.md`](docs/PROVIDERS.md) |
| Run workflows | [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) |
| Troubleshoot | [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) |
| Understand architecture | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Review security | [`docs/SECURITY.md`](docs/SECURITY.md) |
| Inspect evidence | [`docs/RELEASE_EVIDENCE.md`](docs/RELEASE_EVIDENCE.md) |
| See roadmap | [`docs/ROADMAP.md`](docs/ROADMAP.md) |
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
 -> live external dependency/provider/tool verified (when applicable)
 -> release-security authorized
 -> artifact rebuilt/re-hashed/signed/notarized as required
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
