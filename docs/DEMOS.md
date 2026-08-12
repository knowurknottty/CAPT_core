# CAPT Demos — Five Flagship Demonstrations

Each demo is small, end-to-end, executable, produces observable output, and
references **only public interfaces** (`capt` commands and public Python APIs).

All demos assume [START_HERE](../START_HERE.md) is done and `capt` is installed.

---

## Demo 1 — Durable memory (store, restart, retrieve)

**Goal:** prove memory survives process restarts and is independent of any model.

```zsh
capt memory store "Demo 1: memory survives restarts." --tag demo1
# restart is implicit — memory lives on disk
capt memory search "survives restarts"
capt memory list --namespace default
```

**Observable:** the stored fact is retrievable after the process has gone away.

**Watch for:** the `--namespace`/`--tag` flags round-trip.

---

## Demo 2 — Governed execution (request, approve, execute only after approval)

**Goal:** prove nothing consequential runs without human approval.

```zsh
capt start --seed
capt evidence          # shows an authorized mission + evidence chain
```

For a request→approve→execute walk against your own state, drive the governed
command operations via `capt harness command` (operations `create_mission`,
`submit_approval_decision`, `run_fixed_openharness_inspection`). See
[`PLUGIN_GUIDE.md`](PLUGIN_GUIDE.md) for the operation reference.

**Observable:** inspection runs only after an approval decision is submitted.

---

## Demo 3 — Checkpoint / recovery (stop, restart, resume)

**Goal:** prove completed work is not repeated after a restart.

```zsh
capt start
capt checkpoint --idempotency-key demo3-cp
capt stop
capt start
capt resume --idempotency-key demo3-rs
capt status
```

**Observable:** `resume` returns `accepted` and status shows a healthy runtime
without re-doing the checkpoint work. Re-running the same idempotency key is
treated as a duplicate (idempotent), not a second state change.

---

## Demo 4 — Evidence / verification inspection

**Goal:** prove CAPT answers "why does this say it is complete?".

```zsh
capt start --seed
capt --json evidence
```

**Observable:** the output contains authoritative state — mission spec, recorded
evidence, verification result (`verification.status.kind`), and ClaimGuard
disposition when a real claim exists.

---

## Demo 5 — Cross-model continuity (the flagship v0.6 proof)

**Goal:** prove continuity belongs to CAPT, not to any model's transcript.

```text
Model A
  -> governed mission
  -> real work
  -> evidence persisted
  -> CAPT checkpoint
  -> Model A removed

Model B
  -> attach to same CAPT runtime state
  -> recover bounded ContextPack
  -> inspect prior completed work
  -> continue without repeating it
  -> create new evidence -> verification -> ClaimGuard
```

**How to run it today:** the deterministic local expression of this proof is the
seeded demo mission, because `capt start --seed` materializes a complete
mission→evidence→verification→claim chain that you can then resume and inspect
under a fresh process (see Demo 3 + Demo 4). The packaged real two-model variant
depends on the P1 unified model-provider layer.

**Observable:** the same runtime state, once checkpointed, yields the same
mission, evidence, and verification to any subsequent process.

---

## Why five demos

Taken together they cover the v0.6 release gate: understand the purpose
(Demo 1), govern execution (Demo 2), recover state (Demo 3), inspect proof
(Demo 4), and prove continuity is CAPT's, not the model's (Demo 5).

Demos 1–4 are **fully runnable today** against public interfaces. Demo 5's
end-to-end two-model form is the flagship cross-model continuity proof
targeted by the v0.6 source of truth; its deterministic seeded form runs now,
and its packaged real-model form is scoped to the P1 model-provider slice.