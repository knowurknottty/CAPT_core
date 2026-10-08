# CAPT Core

**Local-first governed runtime, continuity substrate, and operator layer for AI systems and bounded tools.**

> **The model is replaceable. CAPT keeps the state, authority, evidence, memory, recovery, and effect history.**

CAPT moves responsibilities that should not live inside a transient model session into a durable local runtime: authoritative state, memory, execution history, governance, evidence, verification, capability control, context policy, checkpoint/recovery, tool-effect reconciliation, and operator control.

The model is an inference component. Tools are effect adapters. **RuntimeService + EventStore + governance are the authority plane around them.**

---

## Operator status update — 2026-10-08

The native Swift CAPT **0.5.0** app has an evidence-derived
[Collaborative Kanban R1](docs/architecture/CAPT_KANBAN_COLLABORATION_R1_2026-10-08.md)
alongside Missions, Evidence, Ledger, Approvals and the governed Council.
The [exact-head verification record](docs/verification/CAPT_KANBAN_R1_ACCEPTANCE_2026-10-08.md)
documents the signed installed build, TIA interactions, and the Python/Swift
tests. **Do not interpret the presence of board cards or a running marker as
proof of live execution or end-to-end Bot autonomy.**

The historic CAPT Core issue-resolution task and mission were conservatively
reconciled to **suspended**, with original history and evidence preserved.
RuntimeService is healthy and advertises Bot identity registration. The
human path forward is **Missions → Prepare continuation in Chat** or
**Kanban → Inspect → Continue**; consequential actions still require their
original CAPT authority and verification boundaries.

[CAPT-Bot](https://github.com/knowurknottty/CAPT-Bot) R5 operational
convergence and Kanban R2 durable multi-actor write/claim APIs are **open
release gates**. A passing historical Bot compatibility suite is not R5
production composition or release certification.

---

## Historical repository status — 2026-09-15

CAPT Core deliberately distinguishes source state from proof state:

1. **Numbered package:** `pyproject.toml` still declares `capt-solo 0.5.0`; preserved `release_evidence/v0.5/` is historical.
2. **Merged Core `main`:** reconciled HEAD `1e85bac5d17cde342a1ae55e6ee3da5fa681ff61` includes the prior convergence plus PR #146 (UPG-020→024), #148 and the semantic operator-control API, #153 (Model Council alpha), #155 (hardening), #156 (SOMA M0), and the September 15 answer/receipt and research-routing fixes.
3. **Release/security evidence:** authorization is exact-SHA. Historical #117 remains a failed security receipt; `2199c036…` has an exact hosted Release Security PASS; ToolBroker PR #126 head `b21ed6e…` also had hosted M0-A + Release Security PASS before squash merge. Those receipts do not automatically transfer to later SHAs.
4. **Topology:** CAPT-UPG-020→024 merged through PR #146; #89/#91/#93/#95/#97 are historical lineage. Labs/Forge remains a separate edition/history line; public plans remain plans except for source-proven implementation.

Historical August 27 audit: `3aee737…` had a mixed M0-A push run (`32958741310`): Python 3.12, contract drift, and TypeScript parity passed; Python 3.10 failed during the Docker availability probe. A retry was recorded by that audit; no retry outcome or current-HEAD CI result is established here. This is historical evidence, not status for `1e85bac…`.

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
capt tui
```

Then exercise runtime checkpoint/restart:

```zsh
capt stop
capt start
capt resume
capt status
```

`capt memory store/search` use the local CAPT Solo MemoryEngine directly; the runtime lifecycle commands use RuntimeService. This smoke sequence does not prove that a memory record was restored through EventStore or delivered to a model after restart.

For the guided path, use [`START_HERE.md`](START_HERE.md).

---

## What is merged on `main`

### Source convergence through September

- **PR #146** — CAPT-UPG-020→024 benchmark/probe and cognitive-debt convergence, merge `cefc885`; empirical effectiveness and provider-cache claims remain separate proof obligations.
- **PR #148** — native macOS control center, Prompt Intelligence proposals/approval binding, and model/tool authority work, merge `5709380`; semantic operator-control API subsequently merged at `42a6cd2`, with revision/digest-bound configuration and prompt selection subordinate to RuntimeService/EventStore.
- **PR #153** — Model Council alpha, merge `542f820`: tier geometry, logical Vessel expansion, launch interlocks, dissent-preserving analysis, durable admission/replay/checkpoints, and read-only Chamber projection; live provider execution, native Council GUI, and release proof remain separate.
- **PR #155** — hardening tiers 1–5, merge `5812a0c`: read projections, mission/DriverRun authority gates, identity-refusal auditing, honest absent-context provenance, and explicit unshipped labels for `context_pipeline` / `context_merkle`.
- **PR #156** — SOMA M0 contract closure, merge `4f1c0a1`: trajectory/reducer contracts, compression receipts, and local benchmark/reconstruction primitives; this does not establish live runtime integration or competition readiness.
- **`d33a5e4`** — native model-answer rendering separated from the execution receipt, with retained disclosure/persistence of execution details.
- **`1e85bac`** — expands AUTO routing signals to include list/match and other actionable requests; the four-word minimum and operator-selected engine/mode still apply. This is routing, not proof of a Search/Deep Research product surface.

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
| native SwiftUI `CAPTNativeMac` | **MERGED APPLICATION TARGET; CURRENT-HEAD BUILD PROOF SEPARATE** |
| ToolBroker local/SSH/Docker terminal execution | **MERGED** |
| true process-boundary cross-model continuation | **MERGED SOURCE; HISTORICAL INTEGRATION EVIDENCE; CURRENT-HEAD RELEASE PROOF SEPARATE** |

The UI is deliberately thin. **CLI, TUI, desktop, MCP, providers, and tool adapters do not become alternate runtimes.**

---

## Public-release design vs implementation

PR #128 preserves the exact owner-approved public-release design (#111) and implementation plans (#116) on current Core ancestry without importing their stale runtime bases.

That means the plans are current documentation authority. It does **not** mean the planned product features are implemented.

Still implementation-gated unless later source proves otherwise:

- Secure Intake / Quarantine;
- Projects and project-context eligibility;
- complete human-first results layer; native answer/receipt separation is present at `d33a5e4`;
- composer capability palette;
- Search / Deep Research governed surfaces.

**Model Council alpha:** merged PR #153 (`542f820`) supersedes the August 10-Cohort / 111-Vessel Council limits with owner-approved Small (2x3), Medium (4x6), Large (12x9), and Extreme (24x18-1000) tiers. The merged alpha implements deterministic logical Vessel expansion, digest-bound launch interlocks, dissent-preserving claim analysis, durable Council admission/replay/checkpoint state, and a read-only Council Chamber projection. It does **not** by itself prove live provider execution, native GUI integration, paid-provider behavior, or release authorization.

Merged low-level Cohorts remain distinct from the higher-level Model Council protocol.

---

## Architecture at a glance

Governed runtime path (the direct local MemoryEngine commands above are separate):

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

The generic direct native `MLX / mlx_lm` adapter is unimplemented and retired/unregistered by default; configuration alone does not make it executable. A configured local OpenAI-compatible MLX/MTPLX service is a supported path through the separate OpenAI-compatible boundary.

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

## CAPT-UPG-020→024 — merged

CAPT-UPG-020→024 source was reconciled into Core through **PR #146 (`cefc885`)**. The earlier #89/#91/#93/#95/#97 lane is historical implementation lineage, not a list of pending Core merges.

- CAPT-UPG-020: reciprocal-review scorer/harness; empirical effectiveness requires observed trial evidence.
- CAPT-UPG-021: read-only sparse symbol index over Discovery/SEAL-admitted candidates; real-repository performance requires benchmark evidence.
- CAPT-UPG-022: Tree-sitter structural-hash probe; grammar/runtime and semantic-equivalence claims are separate.
- CAPT-UPG-023: chunk-stability/FastCDC probe; chunk reuse does not prove provider prefix-cache reuse.
- CAPT-UPG-024: cognitive-debt projection and `capt-debt` surface; absence of reported debt does not prove correctness.

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
