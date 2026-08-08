# User Guide — Task-Oriented Workflows

This guide documents complete workflows, not module inventories. Each section is
a path you can run from the CLI. Everything here uses the normal-human `capt`
surface introduced in v0.6.

Prerequisite: you have completed [START_HERE](../START_HERE.md) and `capt` is
installed.

---

## Workflow A — The life of a runtime session

This is the primary rhythm. Checkpoint early, checkpoint often.

```text
Install -> Start -> Health -> Use -> Inspect -> Checkpoint -> Stop -> Resume
```

```zsh
capt start                       # start (idempotent: safe to run again)
capt status                      # health + version + capabilities
capt memory store "my working fact"   # do some work
capt evidence                    # inspect what is recorded
capt checkpoint --idempotency-key wf-a-cp   # save state
capt stop                        # stop the process
capt start                       # restart, same state dir
capt resume --idempotency-key wf-a-rs      # resume, no repeated work
```

---

## Workflow B — Governed execution (mission → approval → evidence)

Nothing consequential runs without approval. The pattern is:

```text
Mission -> Approval -> Execution -> Evidence -> Verification -> Claim
```

The runtime exposes governed command operations (`create_mission`,
`submit_approval_decision`, ...). The deterministic local demonstration is the
seeded demo mission:

```zsh
capt start --seed     # seeds a demonstration mission with a full chain
capt evidence         # inspect missionSpec, evidence, verification
```

For applications, use `capt harness command` with the governed operations to
walk this workflow against your own state. The expert surface is documented in
[`docs/PLUGIN_GUIDE.md`](PLUGIN_GUIDE.md).

---

## Workflow C — Durable memory

```text
Remember -> Retrieve -> ContextPack -> Model -> Persist
```

```zsh
capt memory store "CAPT keeps memory outside the model."
capt memory search "durable"
capt memory list
```

Memory is durable: it survives process restarts and is independent of any model.

---

## Workflow D — Stop, restart, resume without losing work

```zsh
capt checkpoint --idempotency-key resume-prep
capt stop
capt start
capt resume --idempotency-key resume-continue
capt status
```

The EventStore records ordered history; checkpoints capture authoritative state.
CAPT resumes from that state rather than repeating completed work.

---

## Workflow E — Install and diagnose

```zsh
git clone https://github.com/knowurknottty/CAPT_core.git capt-core
cd capt-core
./install.sh
./verify.sh
capt doctor      # when something is wrong, run this first
```

If a workflow fails, start with `capt doctor`, then see
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Command map (normal-human surface)

| Command | Purpose |
|---|---|
| `capt start` / `capt status` / `capt stop` | runtime lifecycle (defaults) |
| `capt checkpoint` / `capt resume` | state capture + continuation |
| `capt evidence` | human-readable proof / verification view |
| `capt doctor` | environment diagnostics |
| `capt memory store/search/list` | durable memory |
| `capt harness ...` | full expert surface (paths, raw commands) |

`capt harness start/health/stop` remain available unchanged for expert/debug
use. The new `capt start/status/stop` are the recommended normal-human entry
points; they allocate default local state (`~/.capt`).