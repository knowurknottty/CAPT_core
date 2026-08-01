# checkpoint-resume.md

Hard handoff and fresh-process recovery. The goal is that a new process, given
only a workspace path and a mission id, reconstructs the same state — with no
transcript, no copied summary, no inherited context.

## 1. When to checkpoint

- At every phase boundary.
- Before any irreversible or owner-gated operation.
- On context pressure (§4).
- Before ending a session, always.
- Immediately if native transcript compaction is imminent.

## 2. Write the checkpoint

Preferred (boot + checkpoint boundary through the Agent Runner):

```bash
capt --json agent checkpoint --workspace "$WS" --mission "$M"
```

Direct mission-state write (when you must set fields):

```bash
capt mission checkpoint \
  --mission-id "$M" \
  --project-id "$(basename "$WS")" \
  --objective "<what this mission is>" \
  --phase "<current phase>" \
  --next "<next safe action>" \
  --head "$(git -C "$WS" rev-parse HEAD)"
```

`--project-id` must equal the workspace directory name or checkpoint validation
fails with `FOREIGN_WORKSPACE`.

Session-level: `capt session checkpoint <id>`, `capt session consolidate <id>`,
`capt session close <id>`.

What durable state must carry (fields of `MissionCheckpoint`): objective,
current_phase, status, decisions_made (with explicit supersession markers),
constraints, acceptance_criteria, blockers, pending_work, completed_work,
files_changed, commit_references, latest_verified_state (HEAD),
latest_evidence_state (evidence path), next_safe_action,
required_user_decisions, unresolved_invalidations.

Record supersession **explicitly**. CAPT classifies a decision as superseded only
when its text contains one of: `supersede`, `superseded`, `corrected to`,
`rejected`, `overstated`. A decision you believe is dead but recorded without a
marker will come back as an ACTIVE directive on the next boot.

## 3. Verify the checkpoint reloads — before trusting it

```bash
capt --json mission status | grep -q "$M" || echo "FAIL: mission not in store"
capt --json agent status --workspace "$WS" --mission "$M"
```

Required: `execution_mode` not BLOCKED, `gate_result: PASS`, non-empty
`contextpack_digest`, `checkpoint_id` matching `<mission>@<phase>`.

A checkpoint that does not reload is not a checkpoint. If it BLOCKs with
`CHECKPOINT_INTEGRITY`, see diagnostics §14 — write a new one, never patch the
digest.

## 4. Context-pressure policy

Use percentages of the active model's own window, not a fixed token count.

| band | action |
|---|---|
| 50-60% | prepare consolidation: fold findings into durable state; stop opening new investigation threads |
| 65-75% | write the checkpoint and verify it reloads |
| 75-85% | stop broadening scope; finish only the current atomic operation |
| before native compaction | exit and fresh-resume through CAPT |

Native transcript compaction is **fallback continuity**, not CAPT memory success.
If it happens, say so and mark continuity `NOT_PROVEN` for that boundary
(diagnostics §20).

## 5. Hard handoff

1. Consolidate current state (findings, decisions, blockers).
2. Persist: active directives, decisions with supersession markers, blockers,
   evidence paths, git state (branch + HEAD + dirty), next safe action.
3. Write the lifecycle/mission checkpoint (§2).
4. Verify it reloads (§3).
5. Record the handoff receipt: mission id, checkpoint id, HEAD, contextpack
   digest, gate result, evidence paths, timestamp.
6. Exit the process. Do not hand a summary to the next process.

## 6. Fresh-process resume

New process, no inherited transcript. Inputs are the workspace path and the
mission id — nothing else.

```bash
cd "$WS" && source .venv/bin/activate
capt --json agent resume --workspace "$WS" --mission "$M"
```

`--mission` is REQUIRED for resume (the CLI rejects it otherwise).

`resume_report` (in CAPT, not here) boots from CAPT state, discovers the
checkpoint, recovers the session, retrieves memory, reconstructs the next Intent,
builds a NEW ContextPack, and passes the MemoryUseGate. Output fields:
`reconstructed_in: fresh-process`, `mission_id`, `session_id`, `checkpoint_id`,
`execution_mode`, `gate_result`, `active_directive_ids`, `contextpack_digest`,
`intent_id`, `next_justified_action`, `block_reason`, `source`.

The report is persisted to `<evidence_dir>/agent-resume/<mission_id>.json` with a
`.sha256` sidecar.

## 7. Continuity verification — compare, don't assume

Continuity is proven only when the recovered state agrees with repository
evidence:

```bash
git -C "$WS" rev-parse HEAD
git -C "$WS" rev-parse --abbrev-ref HEAD
git -C "$WS" status --short
```

Compare:
- `latest_verified_state` in the checkpoint vs current HEAD → divergence is
  detected by CAPT (`detect_divergence`) and reported as `stale` selection; it is
  informational, not fatal, but must be reported.
- `active_directive_ids` vs ADRs / docs in the repo.
- `latest_evidence_state` path exists and parses.
- `contextpack_digest` present in both the pre-exit and post-resume reports.
  **They will differ** — a new pack is built from current state. Continuity is
  proven by mission/session/checkpoint identity plus gate PASS, not by digest
  equality.

If CAPT state and repository evidence disagree: **stop and report the
discrepancy.** Do not reconcile silently.

## 8. Recovery receipt

Record, after a verified resume:

```
mission_id, session_id, checkpoint_id
pre_exit:  head, contextpack_digest, gate_result, execution_mode
post_resume: head, contextpack_digest, gate_result, execution_mode, intent_id
next_justified_action
divergence: <fields that differ, or none>
evidence_paths: [...]
continuity_verdict: PROVEN | NOT_PROVEN
transcript_inheritance: none | present   (present ⇒ continuity NOT_PROVEN)
```

`continuity_verdict: PROVEN` requires: a fresh process, no transcript
inheritance, mission/session/checkpoint recovered from CAPT state, gate PASS, and
recovered state consistent with repository evidence.

## 9. Isolation for drills

Any command reaching `CAPTRuntime.load()` writes to `CAPT_SOLO_HOME`
(default `~/.capt-solo`). For any test or drill:

```bash
export CAPT_SOLO_HOME="$(mktemp -d)/home"
```

Afterwards prove the owner's home is untouched:

```bash
find "$HOME/.capt-solo" -mmin -10 -type f | head
grep -c "<your-test-mission-id>" "$HOME/.capt-solo/data/khsb/events.jsonl" 2>/dev/null
```

Expect no recent files and zero matching lines. The KHSB log is append-only and
not hash-chained; if you leaked rows, back up `memory.db` and `events.jsonl`
first, remove only lines provably yours, and verify with
`PRAGMA integrity_check`.
