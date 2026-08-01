# BOOTSTRAP_BRIDGE_BASELINE

**Artifact class:** bootstrap evidence — **NOT** a CAPT checkpoint.
No canonical CAPT checkpoint may be claimed until the bridge can genuinely boot CAPT.

**Classification reproduced:** `SKILL_LOADED_CAPT_RUNNER_NOT_ACTIVE`

## Acceptance conditions

| Property | Value |
|---|---|
| Fresh Hermes process | yes (isolated `HERMES_HOME=/tmp/capt-bridge-baseline-home`) |
| Transcript inherited | no |
| Only instruction | `Load CAPT Core.` / `Resume bootstrap-bridge-acceptance.` |
| Session | `20260801_003204_8a4fe4` |
| Duration | 47s, 12 messages, 9 tool calls, iteration budget 4/4 exhausted |

## 1. Loaded skill path and digest

- Installed skill path: `/tmp/capt-bridge-baseline-home/skills/capt-core-runtime`
- Installed tree digest: `sha256:759d58a9c524c3646b5ee6dda9f73a3fe5130f487354852e01435266a56b64b1` (18 files)
- Tracked source: `skills/hermes/capt-core-runtime`
- Tracked tree digest: **identical** — the installed copy is byte-for-byte the tracked source.
- Skill **was** loaded: `skill_view(name='capt-core-runtime')` appears in the transcript.

## 2. CAPT source path

- `capt_solo` importable: yes, **0.5.0**
- Path the Hermes session actually resolved:
  `/Users/knowurknot/Library/Python/3.9/lib/python/site-packages/capt_solo`
- **Mixed checkout, material:** that installed copy has **no `capt_solo/agent/` package at all** —
  no `runner.py`, no `boot.py`, no `model_task.py`. An ambient `import capt_solo` yields a
  runner-less CAPT that *looks* healthy (`__version__ == 0.5.0`) and cannot boot an Agent Runner.
- `capt` console entrypoint is **not on PATH** (exists only at
  `~/Library/Python/3.9/bin/capt`, shebanged to the Xcode interpreter).

## 3. Runner process absence

Zero occurrences of `capt agent`, `agent start`, `agent resume`, or `AgentRunner`
across the full 129-line transcript. No runner process was launched at any point.

## 4-7. Governance chain absence

| Component | Present |
|---|---|
| Mission recovery | no |
| Session recovery | no |
| Checkpoint recovery | no |
| Active directives | no |
| Memory selection/rejection IDs | no |
| ContextPack | no |
| MemoryUseGate | no |
| CTP transaction | no |
| KHSB correlation | no |
| ClaimGuard verdict | no |
| Canonical checkpoint written | no |

## 8. Provider owner

**`HERMES`.** Hermes executed 4 native provider iterations under its own dispatch loop,
emitting reasoning blocks and tool calls, until the iteration budget was exhausted.
CAPT-owned provider invocations: **0**.

## 9. Manually constructed checkpoint artifacts

**None created.** Absence is recorded as absence; no substitute CAPT artifacts were
fabricated to fill the gap.

## Observed failure mode

The model treated the skill as prose. It ran the skill's diagnostic shell scripts,
hunted for the `capt` binary, then *narrated* the boot sequence it never executed:

> "Next steps to complete: 1. Install CAPT via source … 2. Run `capt --json agent status …`
> 3. Resume bootstrap-bridge-acceptance once GOVERNED confirms it's available."

That is the defect in one sentence: **the skill describes a handoff instead of performing one.**
Nothing in the loaded skill can *compel* a runtime transfer, because a skill is text injected
into the same Hermes provider loop it is trying to displace.
