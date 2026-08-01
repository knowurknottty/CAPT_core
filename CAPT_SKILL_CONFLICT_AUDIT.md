# CAPT_SKILL_CONFLICT_AUDIT.md

Conflict and disposition analysis for CAPT-related Hermes skills, prior to
introducing `capt-core-runtime`. Enumerated from a live scan of
`~/.hermes/skills` (SKILL.md files, excluding `references/` and `.archive/`).

## 1. Scan result

30 CAPT-named skill packages exist. They split into three populations:

**A. bioCAPT / FrankenCAPT ecosystem (different product).** Target
`~/Biocapt-ecosystem-fullcaptlang/`, the 108-module neural architecture, PULSE,
ECHO, CAPTLang/WASM. NOT capt-solo.

`biocapt-full-stack`, `biocapt-beta-deployment`, `mlops/biocapt-architecture-knowledge`,
`mlops/biocapt-perfection`, `mlops/biocapt-strength-stack`, `mlops/biocapt-troubleshooting`,
`mlops/understand-biocapt`, `mlops/capt-memory` (ECHO), `mlops/capt-health` (PULSE),
`mlops/capt-reasoning` (QIPC/CIG), `mlops/capt-building` (VESSEL), `mlops/capt-nexus`,
`mlops/capt-training`, `mlops/capt-ml-pipeline`, `mlops/capt-vessel`,
`mlops/capt-ios-integration`, `mlops/capt-prize-operations`, `mlops/capt-reading-daemon`,
`mlops/capt-session-pulse`, `mlops/capt-long-running-sessions`, `mlops/capts-contribution`,
`mlops/frankencapt-mcp-tools`, `mlops/capt-provenance-system`, `capt-skill-registry-audit`,
`capt/capt-eval-tracker`.

**Disposition: NO CONFLICT — retain unchanged.** Name collision on the token
"CAPT" only. Different repository, different runtime, no overlapping trigger
with "boot CAPT Core / CAPTRuntime / MemoryUseGate / ContextPack".

Residual risk: a bare "use CAPT" utterance is genuinely ambiguous between
bioCAPT and CAPT Core. Mitigated by making the new description lead with
"CAPT Core runtime (capt-solo)" and requiring workspace evidence
(`capt_solo` importable / `.capt/checkpoints` present) before boot.

**B. capt-solo skills (same product) — 3 packages.**

| skill | path | scope | overlap with new skill |
|---|---|---|---|
| `capt-solo-v04-engineering` | `software-development/` | 100,073 bytes SKILL.md (at the 100k agent-write cap), 32 references. v0.4→v0.5 integration, release gates, composition root, real-model acceptance, plugin integration, agent-runner slice, continuity recovery | **HIGH** — contains `fresh-boot-cli-invocation.md`, `agent-runner-vertical-slice.md`, `agent-continuity-recovery.md`, `outcome-b-composition-root.md` |
| `capt-solo-engineering-workflow` | `software-development/` | 4,016 bytes. `CAPT_SOLO_HOME` isolation, surgical git hunk staging, dependency-aware landing order, credential-safe acceptance | **LOW** — engineering hygiene, not boot |
| `mlops/capt-solo-extend` | `mlops/` | extend capt-solo with new deterministic subsystems (v0.2 context intelligence, CSG, AntiToken) | **NONE** — feature development |

**C. Repository-bundled skills — 8 packages** at
`capt_solo/skills/<name>/SKILL.md`, installed flat by `install.sh`.

| skill | conflict |
|---|---|
| `capt-bootstrap` | **NAME/TRIGGER CONFLICT (moderate).** Description: "Bootstrap a new project with CAPT Solo — initialize local runtime, store first memory, verify health." Instructs tool calls `capt_health`, `capt_store_memory`, `capt_search_memory`. A "boot CAPT" utterance can route here. |
| `capt-recovery` | **TRIGGER CONFLICT (moderate).** "Recover CAPT Solo state after an interruption — replay CTP journal, verify integrity, restore from backup." Overlaps "resume through CAPT" but is a *disaster-recovery* procedure, not mission resume. |
| `capt-session-recap` | LOW. End-of-session memory summary; overlaps "checkpoint through CAPT" superficially. |
| `capt-transaction` | NONE. CTP wrapper how-to. |
| `capt-memory-review` | LOW. Memory pruning; overlaps "use CAPT memory". |
| `capt-arch-decision`, `capt-debug`, `capt-knowledge-capture` | NONE. |

## 2. Staleness evidence against the current runtime

The bundled skills predate v0.5 and are demonstrably behind:

- They drive the plugin **tool** surface (`capt_health`, `capt_store_memory`,
  `capt_search_memory`) and never mention `CAPTRuntime`, `MemoryUseGate`,
  `ContextPack`, `ClaimGuard`, mission checkpoints, execution modes, or the
  Agent Runner — all of which are the v0.5 governance surface.
- `capt-bootstrap` says "after a fresh install of the capt-solo plugin", but the
  installed plugin now registers **7 lifecycle hooks** (`register(ctx)`,
  `__init__.py:1221-1227`), which the skill is unaware of.
- `install.sh:52` still installs `plugin.json` (the legacy contract) while the
  live plugin dir carries `plugin.yaml`.
- Directory mtime: `capt_solo/skills/` = 2026-07-19; the Agent Runner landed
  2026-07-31 (`1fed59a`, `12821f3`, `466f0d2`).

`capt-solo-v04-engineering` is **current** (SKILL.md mtime 2026-07-31 19:15,
references updated 20:27) and explicitly covers the Agent Runner slice. It is
NOT stale — but it is an *engineering* skill (how to land changes in the repo),
not an *operating* skill (how a session boots through CAPT).

## 3. Dispositions

| skill | disposition | rationale |
|---|---|---|
| `capt-solo-v04-engineering` | **RETAIN — no deprecation, no in-place upgrade.** Add a cross-reference pointer only. | It answers "how do I change capt-solo". The new skill answers "how does a session run *under* CAPT". Different lifecycles; merging would push a 100k-char file over the write cap. Owner directive: do not delete legacy skills until replacement is proven. |
| `capt-solo-engineering-workflow` | **RETAIN unchanged.** | Complementary: `CAPT_SOLO_HOME` isolation is a prerequisite the new skill cites, not duplicates. |
| `mlops/capt-solo-extend` | **RETAIN unchanged.** | No overlap. |
| bundled `capt-bootstrap` | **RETAIN as legacy compatibility — flagged.** | Still valid for the plugin *tool* surface on installs without the Agent Runner. Superseded for boot. The new skill's `references/compatibility.md` records the supersession; the bundled skill is not edited in this change (it ships in the tracked package and editing it is a separate packaging decision). |
| bundled `capt-recovery` | **RETAIN as legacy compatibility — flagged.** | Disaster recovery (journal replay, backup restore) is a genuinely different operation from mission resume. |
| remaining 6 bundled | **RETAIN unchanged.** | No trigger conflict. |
| 25 bioCAPT-family skills | **RETAIN unchanged.** | Different product. |

**Zero deletions. Zero edits to existing skills in this change.**

## 4. Runtime defects observed during audit (recorded, NOT fixed here)

These are real, reproducible, and constrain what the new skill may claim. They
belong to the Agent Runner, which the owner directive puts out of scope.

**D-1 — mission discovery crashes on legacy checkpoints.**
`capt --json agent status --workspace /Users/knowurknot/capt-solo` (no
`--mission`) → `TypeError: MissionCheckpoint.__init__() missing 2 required
positional arguments: 'project_id' and 'objective'`.
Cause: `boot.resolve_mission` (`boot.py:100-103`) iterates `store.list_ids()` and
calls `store.load(mid)` on every id; 3 of 6 stored checkpoints
(`checkpoint-governed-agent-boot-proven`, `phase0-outer-agent-memory-trace`,
`phase2-outcome-c-contracts`) are pre-`project_id`/`objective` schema records and
raise instead of being skipped or migrated.
Impact on the skill: **auto-discovery is unusable on this workspace.** The skill
MUST pass `--mission` explicitly and MUST classify a discovery TypeError as
`FAIL: LEGACY_CHECKPOINT_SCHEMA`, not as "no mission".

**D-2 — one checkpoint has a null digest.**
`mission-governed-model-execution` stores
`event_digest: sha256:000…0` (64 zeros); recomputed digest is
`sha256:3e1bdb74a64ba…`. `validate_checkpoint` (`boot.py:143-150`) correctly
BLOCKs with `CHECKPOINT_INTEGRITY`. The record was written with a placeholder
digest. Fail-closed behaviour is correct; the data is wrong.
Impact: this mission cannot be the acceptance mission. Do not "repair" owner
evidence to make a gate pass.

**D-3 — `capt --version` prints usage, not a version.**
Version must be sourced from `capt doctor` (`package.version`) or
`python -c "import capt_solo; print(capt_solo.__version__)"`.

**D-4 — `capt` is not on PATH outside the venv.** Every command in the skill
must run inside the resolved environment.

**D-5 — tool hooks are observational.** `pre_tool_call`/`post_tool_call` in the
plugin are annotated **observational only** (`plugin/__init__.py:864`). Therefore
`GOVERNED_TOOL_LOOP_PROVEN` is NOT provable in Hermes today, and tool
authorization is **not runtime-enforced** in a Hermes session. The skill must
state this in every BOOTSTRAP_DEGRADED report.

## 5. Prompt-enforced vs runtime-enforced (the honest boundary)

Runtime-enforced (executed by CAPT code, verifiable from artifacts):
- mission resolution precedence and ambiguity refusal — `boot.resolve_mission`
- checkpoint identity/integrity/foreign-workspace validation — `boot.validate_checkpoint`
- MemoryUseGate before any provider invocation — `runtime.execute_model_task`, gate at `runtime.py:636-674`
- ContextPack construction + digest — `runtime.gate.prepare` → `decision.pack.digest`
- CTP transaction commit/abort — `CTPRuntime`
- KHSB durable event log — `_DurableEventLog`
- ClaimGuard verdicts — `runtime.claimguard`
- artifact hashing + `.sha256` sidecars — `_persist_boot_trace`, `_persist_intent`
- BOOTSTRAP_DEGRADED requires a durable marker — `boot._degraded_authorized`
- single composition root assertion — `agent doctor.single_composition_root`

Prompt-enforced only (this skill's discipline; NOT enforced by code in a Hermes session):
- that the model actually *reads* the recovered ContextPack rather than the transcript
- that the model checkpoints before native compaction
- context-pressure thresholds
- refusal to claim milestones without evidence
- tool-intent authorization inside Hermes (hooks are observational — D-5)
- secret non-disclosure

This split is reproduced verbatim in `references/security-boundaries.md` and is
the required content of every execution-mode report the skill emits.
