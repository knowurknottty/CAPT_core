# compatibility.md

## 1. Supported configurations

| configuration | status | notes |
|---|---|---|
| editable local checkout (`pip install -e .`) | supported | `pip show capt-solo` reports `Editable project location:`; the checkout is the source of truth |
| installed distribution (non-editable) | supported | source root is site-packages; git identity fields become `n/a` |
| explicit `CAPT_SOLO_REPO` | supported | precedence 2; must contain `capt_cli.py` + `capt_solo/` |
| project-local CAPT workspace (`<repo>/.capt/`) | supported | mission checkpoints and evidence live here; gitignored |
| user-global CAPT home (`~/.capt-solo`) | supported | memory db, CTP journal, KHSB events; override with `CAPT_SOLO_HOME` |
| Hermes with the capt-solo plugin enabled | supported | 7 hooks; tool hooks observational |
| Hermes without the plugin | supported | CLI path only; report `MemoryUseGate enforced by runtime: NO` for the Hermes turn |
| local LM Studio / OpenAI-compatible provider | supported | `CAPT_MODEL_ENDPOINT` + `CAPT_MODEL_ID`; health-gate first |
| provider-independent operations (boot, status, checkpoint, resume, memory, evidence) | supported | no provider required |

## 2. Known limitations

**Mission auto-discovery breaks on legacy checkpoints.** `capt agent status`
without `--mission` raises `TypeError: MissionCheckpoint.__init__() missing 2
required positional arguments: 'project_id' and 'objective'` when the store holds
any pre-`project_id` record. Always pass `--mission`. Diagnostics §8.

**Placeholder checkpoint digests.** Some records were written with
`event_digest: sha256:0…0` (64 zeros). Validation correctly BLOCKs them with
`CHECKPOINT_INTEGRITY`. Do not rewrite the digest; write a new checkpoint and
leave the old record as evidence.

**`capt --version` prints argparse usage**, not a version. Use `capt doctor`
(`package.version`) or `capt_solo.__version__`.

**`capt` is not on PATH outside the venv.** Activate first.

**Hermes tool hooks are observational.** `GOVERNED_TOOL_LOOP_PROVEN` is not
provable in a Hermes session today.

**Legacy `plugin.json` contract.** The current Hermes loader uses
`plugin.yaml` + `register(ctx)`. A `plugin.json`-only install is not loaded.
Both files may coexist; only `plugin.yaml` matters.

**Stale installed plugin copies.** `~/.hermes/plugins/capt-solo/` is a copy, not
a link. It can drift from the repository. Compare sha256 (diagnostics §5). The
installed copy governs the running Hermes; the repo copy governs the next install.

**Multiple CAPT checkouts.** This repository commonly has several `git worktree`
entries plus temporary worktrees under `/private/tmp`. Which `capt_solo` imports
depends entirely on the active venv. Always verify `capt_solo.__file__`.

**Sessions created before canonical mission persistence** have no mission
binding; boot cannot use precedence rule 2 for them. Pass `--mission`.

**Legacy evidence schemas using scalar `selection_ids`.** A migration reader
(`normalize_selection_ids`, exported from `capt_solo.api`) exists for the scalar→
collection change. Use it. Do not rewrite stored records.

**External proprietary harnesses.** CAPT governance is proven only for the CAPT
CLI/runtime path and, partially, the Hermes plugin path. Any other harness is
`NOT_PROVEN` until it demonstrates the same artifacts.

**`.capt/` is gitignored.** Evidence and checkpoints are local-only and do not
travel with a clone or a PR. Acceptance must hash artifacts in place and quote
the paths.

**KHSB may be disabled.** `CAPT_KHSB_ENABLE=0` in the environment silences the
bus. Absence of events under that flag is `NOT_PROVEN`, not `FAIL`.

## 3. Related skills and their boundaries

| skill | relationship |
|---|---|
| `capt-solo-v04-engineering` | **Engineering counterpart.** How to *change* capt-solo: release gates, composition-root work, real-model acceptance, plugin integration, the Agent Runner slice. Load it when editing the repository. This skill is how to *run under* CAPT. No content is duplicated; neither supersedes the other. |
| `capt-solo-engineering-workflow` | **Prerequisite for repo edits.** `CAPT_SOLO_HOME` isolation, surgical git hunk staging, dependency-aware landing order, credential-safe acceptance. Cited by this skill, not duplicated. |
| `capt-solo-extend` (mlops) | Building new capt-solo subsystems. No overlap. |
| bundled `capt-bootstrap` | **Superseded for boot.** Targets the plugin tool surface (`capt_health`, `capt_store_memory`, `capt_search_memory`) and predates v0.5 governance. Retained as legacy compatibility for installs without the Agent Runner. For booting a governed session, use this skill. |
| bundled `capt-recovery` | **Complementary, not superseded.** Disaster recovery — CTP journal replay, integrity verification, backup restore. Different operation from mission resume. Use it when the store itself is damaged. |
| bundled `capt-session-recap`, `capt-memory-review`, `capt-transaction`, `capt-arch-decision`, `capt-debug`, `capt-knowledge-capture` | Narrow plugin-tool procedures. No conflict. |
| `biocapt-*`, `capt-memory`, `capt-health`, `capt-reasoning`, `capt-building`, `capt-nexus`, `capt-vessel`, `capt-training`, `capt-ml-pipeline`, `frankencapt-mcp-tools`, and the rest of the bioCAPT family | **Different product.** bioCAPT / FrankenCAPT / CAPTLang / PULSE / ECHO, a separate repository and runtime. Name collision on "CAPT" only. This skill must not activate for them, and they must not be used to boot CAPT Core. |

## 4. Model-adapter awareness

This skill is model-agnostic. Model profiles (HY3, Big Pickle, Qwen, LFM2,
Orinth, Mistral, other OpenAI-compatible local models) may tune only:
instruction density, response structure, context budget, tool-call discipline,
output parsing, and known decoding weaknesses.

Model profiles must **not** redefine CAPT governance. The CAPT Constitution,
the boot protocol, the MemoryUseGate, the milestone predicates, and the
runtime-vs-prompt enforcement split are invariant across models.

If a model cannot follow the governance trace format, that is a degraded-mode
finding to report — not a licence to skip the trace.

## 5. Version binding

Verified against:
- capt-solo **0.5.0** (`capt doctor` → `package.version`)
- Agent Runner schema **`capt.agent.v1`** (`AGENT_SCHEMA_VERSION`)
- Hermes Agent **v0.19.0** (2026.7.20)

If `capt doctor` reports a different package version, re-verify the CLI surface
with `capt --help` and each `capt <group> --help` before trusting the command
tables in `boot-protocol.md`.
