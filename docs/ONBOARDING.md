# CAPT Core onboarding — choose your path

> **Scope:** navigation initially reviewed at `0d8e46d095243e80febd4e30f5ae52c9202316d9` on 2026-10-18; see the [supplemental source notes for current `c956c45e`](CURRENT_HEAD_DELTA.md). This is a route map to existing canonical references; it does not replace source-level requirements.

## Decide what you want to accomplish

| You're here to… | Start | Continue | Proof boundary |
|---|---|---|---|
| Understand CAPT in five minutes | [Explained simply](EXPLAINED_SIMPLY.md) | [Mental model](MENTAL_MODEL.md) | Conceptual explanation is not operational proof |
| Evaluate without provider costs | [Start Here](../START_HERE.md) | [Installation](INSTALLATION.md) → [CLI](CLI.md) | Use local install/read-only help before enabling inference |
| Run ordinary operator workflows | [User guide](USER_GUIDE.md) | [TUI](TUI.md) → [Cheatsheets](CHEATSHEETS/README.md) | UI actions still require runtime authority |
| Build with the in-process Python API | [API](API.md) | [Plugin guide](PLUGIN_GUIDE.md) | Generated API signatures apply to their source/installation scope |
| Integrate a provider or tool | [Providers](PROVIDERS.md) | [Model providers](MODEL_PROVIDERS.md) → [Architecture](ARCHITECTURE.md) | Registry/health and fixture tests are not live inference proof |
| Work on native macOS UI | [Desktop](DESKTOP.md) | [Native build instructions](../START_HERE.md#native-macos-application) | Build/test != signing, notarization, or distribution |
| Contribute changes | [Agent instructions](../AGENTS.md) | [Review/verifier contract](workflows/CAPT_REVIEWER_VERIFIER_CONTRACT.md) | Deep review requires RRDS-1 receipts and independent verification |
| Evaluate security and provenance | [Security](SECURITY.md) | [Governance](GOVERNANCE.md) → [Release evidence](RELEASE_EVIDENCE.md) | Security claims are exact-revision and exact-artifact bounded |
| Investigate implementation maturity | [Current state](CURRENT_STATE.md) | [Capability matrix](CAPABILITY_MATRIX.md) → [PR topology](PR_TOPOLOGY.md) | Dated documents are snapshots, not automatically fresh evidence |

## Path A — new user with no paid model

**Prerequisites:** Python `>=3.8` is declared in package metadata; current development/test environments may have narrower practical compatibility. A local installation and CLI-help check do not require provider accounts.

1. Follow [Start Here](../START_HERE.md) to create a virtual environment and install from source.
2. Run `capt --version`, `capt --help`, and `capt memory --help`.
3. If you want a local data-writing exercise, follow the Solo memory example in [Start Here](../START_HERE.md#first-success-durable-state). Its storage is separate from the governed runtime ledger.
4. Only after understanding that distinction, consider `capt start`, `capt status`, and the TUI. Starting runtime components can create local state/processes.
5. Before invoking `capt run` with a provider, inspect [Providers](PROVIDERS.md), credentials, network boundaries, and possible model costs.

**Expected safe first result:** `capt --version` reports the package version, not the installed application's release certification. On the pinned development checkout it returned `capt-solo 0.5.0`. The output could differ in another environment or revision.

**If blocked:** see [Troubleshooting](TROUBLESHOOTING.md). Run `capt doctor` only after reviewing its environment-dependent behavior in that environment.

## Path B — operator who needs governed execution

Read [User guide](USER_GUIDE.md) and [Governance](GOVERNANCE.md). Be explicit about what is an operator request, which action requires scoped approval, what was observed, whether evidence was admitted, and which claim was verified. A green driver receipt is not necessarily a terminal mission receipt.

Avoid using direct state-file or SQLite mutations as a shortcut around RuntimeService/EventStore.

## Path C — integrator or developer

Start with [Technical manual](TECHNICAL_MANUAL.md), then [Architecture](ARCHITECTURE.md), [CLI](CLI.md), [API](API.md), [Data model](DATA_MODEL.md), [Plugin guide](PLUGIN_GUIDE.md), and tests for your exact interface. Do not infer API stability from generated documentation alone; inspect code, compatibility boundaries, and tests pinned to the checkout.

## Path D — reviewer or AI coding agent

Read the root [`AGENTS.md`](../AGENTS.md) first. Then read the [RRDS-1 reviewer/verifier contract](workflows/CAPT_REVIEWER_VERIFIER_CONTRACT.md) and [repository depth standard](workflows/CAPT_REPOSITORY_REVIEW_DEPTH_STANDARD.md). A sample review may produce useful findings, but cannot claim exhaustive deep-review completion. Preserve attribution and historical proof artifacts.

## Common wrong turns

- Treating `capt memory` as authoritative runtime context: **incorrect**; see [Glossary](GLOSSARY.md).
- Treating a model answer as task completion: **incorrect**; see [Governance](GOVERNANCE.md).
- Assuming every button in a development UI proves deployed backend functionality: **incorrect**; see [Desktop](DESKTOP.md).
- Treating historical exact-SHA security or release reports as current-head authorization: **incorrect**; see [Release evidence](RELEASE_EVIDENCE.md).

[Documentation index](README.md) · [Glossary](GLOSSARY.md)
