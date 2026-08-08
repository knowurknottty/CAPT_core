# Start Here

**Welcome to CAPT.** Read this file first.

> CAPT is a **local-first governed runtime and continuity substrate for AI agents.**
>
> **The model becomes stateless. CAPT becomes stateful.**

A model (an LLM) is transient and replaceable. CAPT owns the durable memory,
governed state, evidence, authority, execution history, context policy, and
recovery around the model. Whatever model you use, your continuity, proof, and
state belong to CAPT.

---

## What will you accomplish here?

This is the only walkthrough you need to go from zero to real CAPT use. In
about **five minutes** you will:

1. install CAPT;
2. verify the install;
3. store and retrieve durable memory;
4. start the governed runtime;
5. inspect its health and evidence;
6. checkpoint it;
7. stop it;
8. restart and resume it;
9. inspect the proof that CAPT tracks what happened.

You do **not** need Hermes, an API key, a hosted model provider, Docker, or an
external database for any of this. It is fully local and deterministic.

---

## Prerequisites

| Requirement | Minimum | Notes |
|---|---|---|
| Operating system | macOS or Linux | Windows is unverified until separately tested |
| Python | 3.10, 3.11, or 3.12 | release-tested path |
| Tools | `git`, a POSIX shell | |

Check Python:

```zsh
python3 --version
```

If `python3` is not one of 3.10–3.12, choose an available one (e.g. `python3.12`).

---

## 1. Install and verify

```zsh
git clone https://github.com/knowurknottty/CAPT_core.git capt-core
cd capt-core
./install.sh
./verify.sh
```

`install.sh` installs the `capt` command-line interface and prepares local
state. Confirm it worked:

```zsh
capt --version
```

Expected:

```text
capt-solo 0.5.0
```

If `capt` is not found, ensure your `python3`'s bin directory is on `PATH`,
or re-run `/path/to/capt-core/install.sh` with the Python you plan to use.

> Troubleshooting: run `capt doctor` any time. It prints a clear list of what
> is present and what is missing, and what to do about each.

---

## 2. First success: durable memory

CAPT's memory is independent of any model. Store a fact:

```zsh
capt memory store "CAPT keeps durable state outside the model."
```

You should see a `memory_id`. Now retrieve it:

```zsh
capt memory search "durable state"
capt memory list
```

This is the core CAPT property: **knowledge belongs to CAPT, not to a model
transcript.** Restart your computer and this memory is still there.

---

## 3. Start the governed runtime

```zsh
capt start
```

That's it. No socket paths, tokens, or ledger paths to configure. CAPT allocates
a default local state directory (`~/.capt`, or `$CAPT_STATE_DIR` if you set it)
and starts the authenticated runtime service.

You should see `status: HEALTHY`.

Check runtime health and capabilities:

```zsh
capt status
```

---

## 4. Inspect evidence and verification

Evidence is how CAPT answers "why does this claim say it is complete?".

```zsh
capt evidence
```

This shows authoritative CAPT state: the active mission, recorded evidence,
verification result, and — when a real claim exists — the ClaimGuard decision.

> Not every first-run runtime has a mission yet, so the mission may be `None`.
> The verification result is still shown.

---

## 5. Checkpoint the runtime

A checkpoint captures authoritative state so you can resume later.

```zsh
capt checkpoint --idempotency-key my-first-checkpoint
```

You should see `status: accepted` and a `checkpointId`. Run the same command
again — CAPT treats a repeated idempotency key as a duplicate, not a second
state change.

---

## 6. Stop, restart, resume

Stop the runtime:

```zsh
capt stop
```

`capt status` should now report the runtime is not running. Restart it using the
same default state directory (your ledger is preserved):

```zsh
capt start
```

Resume from the check-pointed state:

```zsh
capt resume --idempotency-key my-first-resume
```

Re-check health:

```zsh
capt status
```

Completed work is not repeated; CAPT resumes from its authoritative state.

---

## 7. Where the truth lives (mental model)

Keep this one picture in mind:

```text
Human
  |
  v
CAPT Runtime
  |
  +--> Memory        durable, model-independent
  +--> Governance    nothing happens without authority/approval
  +--> Evidence      proof, verification, claims
  +--> Recovery      EventStore, checkpoints
  |
  v
Replaceable Models   (LM Studio, Ollama, OpenRouter, ...)
```

Everything above the bottom line is CAPT's responsibility. Models are pluggable
inference components below the line. See `docs/MENTAL_MODEL.md` for the detail.

---

## 8. What you can do next

- **[Use CAPT](./docs/USER_GUIDE.md)** — the task-oriented workflows.
- **[Run a flagship demo](./docs/DEMOS.md)** — five end-to-end demonstrations.
- **[See what is real](./docs/CAPABILITY_MATRIX.md)** — implemented vs. tested
  vs. operator-facing, at a glance.
- **[Inspect the proof](./docs/RELEASE_EVIDENCE.md)** — how v0.5 was verified.
- **[Add a model provider](./docs/MODEL_PROVIDERS.md)** — wire up a model.
- **[Read the architecture](./docs/ARCHITECTURE.md)** — after first success.
- **[Get help](./docs/TROUBLESHOOTING.md)** — common failures and fixes.

---

## Command reference (the essentials)

| Command | What it does |
|---|---|
| `capt memory store "<text>"` | store a durable memory |
| `capt memory search "<terms>"` | retrieve memories |
| `capt start` | start the governed runtime (defaults) |
| `capt status` | runtime health and version |
| `capt evidence` | human-readable evidence / verification view |
| `capt checkpoint` | capture authoritative state |
| `capt resume` | resume after restart |
| `capt stop` | stop the runtime |
| `capt doctor` | diagnose the environment |
| `capt --version` | version |

---

## A note on honesty

This walkthrough uses the **normal-human** CLI surface that exists in v0.6.
Some deeper subsystem features are real but not yet surfaced through simple
commands; the capability matrix at `docs/CAPABILITY_MATRIX.md` tells you
exactly what is operator-facing versus internal versus experimental. If a doc
ever implies something that a command does not actually do, the command wins.