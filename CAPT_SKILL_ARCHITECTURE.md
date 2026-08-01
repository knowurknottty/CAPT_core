# CAPT_SKILL_ARCHITECTURE.md

Architecture of the `capt-core-runtime` Hermes skill.

## 1. Purpose

One canonical Hermes skill that makes "use CAPT" operationally precise: it
locates the canonical CAPT Core (capt-solo) installation, activates the correct
environment, recovers mission/session/memory through the canonical CLI, reports
the ContextPack + MemoryUseGate trace, checkpoints, and resumes in a fresh
process — without reconstructing any CAPT behaviour in prompt text.

## 2. Layer boundary

```
Hermes session
   │
   ├── capt-core-runtime skill        (loader · operator guide · diagnostics · recovery)
   │      SKILL.md + references/ + scripts/  — NO capt_solo imports, NO runtime construction
   │
   ├── capt console script            (canonical CLI, capt_cli.py)
   │      capt doctor | agent {doctor,status,checkpoint,resume,start} | mission | session | memory | workspace | evidence
   │
   ├── capt_solo.agent.runner.AgentRunner / boot.boot()      (ADR-0001 Outcome C)
   │
   └── capt_solo.runtime.CAPTRuntime  (SINGLE composition root)
          engine · ctp · bus · lifecycle · proof · registry · claimguard · gate · events
```

Every arrow is a process boundary or a function call inside CAPT. The skill owns
none of the state.

## 3. Components

### 3.1 SKILL.md — routing + the five procedures

Sections, in load order:
1. **Applicability gate** — positive triggers, and the mandatory negative gate
   (`NOT_A_CAPT_WORKSPACE`).
2. **Resolve** — strict source precedence, environment activation, identity record.
3. **Boot** — the canonical `capt agent status --mission` path and the boot report fields.
4. **Operate** — the runtime discipline rules and the `CAPT_MEMORY_USE` trace block.
5. **Checkpoint / resume** — hard-handoff and fresh-process verification.
6. **Classify** — execution modes, component states, milestone vocabulary, and
   the mandatory `capt_execution_mode` vs `hermes_session_mode` split.
7. **Failure index** — symptom → diagnostic code → reference file.

### 3.2 references/ — depth on demand

| file | answers |
|---|---|
| `boot-protocol.md` | exact command sequence, per-step failure modes, boot-report field provenance |
| `runtime-components.md` | what each CAPT subsystem is, where it is constructed, how to verify it is live vs merely importable |
| `diagnostics.md` | the 20 diagnostic scenarios, each with a probe command, expected output, and verdict |
| `checkpoint-resume.md` | hard handoff, context-pressure policy, fresh-process verification |
| `security-boundaries.md` | secret handling, untrusted-content boundary, runtime- vs prompt-enforced table |
| `milestone-language.md` | execution modes, component states, milestone predicates and what evidence each requires |
| `compatibility.md` | supported configurations, known limitations, legacy skill relationships, legacy evidence schemas |

### 3.3 scripts/ — orchestration of verified commands only

| script | contract |
|---|---|
| `capt-environment-report.sh` | emits the identity record (source, version, git, python, CAPT home, plugin parity) as JSON. Read-only. |
| `capt-doctor.sh` | 18 checks, each `PASS｜WARN｜FAIL｜NOT_PROVEN`. Never collapses "available" into "operational". Exit 0 on no FAIL. |
| `capt-fresh-boot.sh` | `capt --json agent status --workspace W --mission M` → validated boot report against `schemas/boot-report.schema.json`. |
| `capt-checkpoint.sh` | `capt --json agent checkpoint` → verifies the checkpoint reloads. |
| `capt-resume-check.sh` | fresh process → `capt --json agent resume` → compares recovered state against repository evidence, emits a recovery receipt. |

Every script is `set -euo pipefail`, takes the workspace and mission as
arguments, honours `CAPT_SOLO_HOME`, and prints structured output. None of them
import `capt_solo`; none construct runtime objects.

### 3.4 schemas/

`boot-report.schema.json` — the only artifact the skill itself composes. All
other shapes belong to CAPT (`AgentMemoryBootTrace`, `GateDecision.pack`,
`resume_report`) and are consumed, not redefined.

## 4. Data flow — one governed recovery

```
user: "Load CAPT Core and resume <mission>"
  ↓
skill applicability gate
  ↓  workspace has .capt/checkpoints AND capt resolvable? else NOT_A_CAPT_WORKSPACE
capt-environment-report.sh   → identity record (source precedence resolved)
  ↓
capt-doctor.sh               → 18 verdicts; any FAIL on a mandatory check ⇒ stop
  ↓
capt-fresh-boot.sh W M       → capt agent status --json
  ↓                              CAPT executes: mission resolve → checkpoint validate
  ↓                              → session → directives/supersession → Intent
  ↓                              → selection record → ContextPack → MemoryUseGate
  ↓
boot report                  → mission/session/checkpoint ids, active + superseded
                               directives, contextpack digest, gate result,
                               execution mode, next justified action
  ↓
CAPT_MEMORY_USE trace block  → emitted before any consequential action
  ↓
work
  ↓
capt-checkpoint.sh W M       → checkpoint written + reload-verified
  ↓
exit; fresh process
  ↓
capt-resume-check.sh W M     → independent reconstruction + comparison to repo evidence
```

## 5. Non-goals

- No second runtime, no re-implemented gate, no parallel memory store (D3).
- No modification of the CAPT plugin, the Agent Runner, or existing skills.
- No project-specific mission state embedded in the skill.
- No claim that a Hermes session is GOVERNED (D7).

## 6. Known architectural constraints (from live evidence)

| constraint | source | effect on design |
|---|---|---|
| mission auto-discovery raises on legacy checkpoints | CA D-1 | `--mission` is mandatory in every script; discovery TypeError maps to `LEGACY_CHECKPOINT_SCHEMA` |
| `capt --version` prints usage | CA D-3 | version read from `capt doctor` / `capt_solo.__version__` |
| `capt` not on PATH outside venv | CA D-4 | environment activation is step 1, not an assumption |
| Hermes tool hooks observational | CA D-5 | `GOVERNED_TOOL_LOOP_PROVEN` unprovable; degraded-mode reporting mandatory |
| `.capt/` gitignored | SM §7 | evidence is local-only; acceptance must hash artifacts in place |
| CAPT home var is `CAPT_SOLO_HOME` not `CAPT_HOME` | SM §2 | isolation contract uses the correct variable |
