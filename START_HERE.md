# Start Here — CAPT Core v0.6 Productization Path

CAPT Core is a **local-first governed runtime and continuity substrate for AI agents**.

The shortest useful mental model is:

> A model is transient and replaceable. CAPT owns the durable memory, governed state, evidence, authority, execution history, context policy, and recovery around it.

Or, more compactly:

> **The model becomes stateless. CAPT becomes stateful.**

This page is the canonical first path for a technically capable user who has never used CAPT before.

---

## 1. What you will prove in this walkthrough

By the end, you will have:

1. installed CAPT locally;
2. verified the installation;
3. stored and retrieved durable memory;
4. started the authenticated runtime harness;
5. checked runtime health and capabilities;
6. created a runtime checkpoint;
7. stopped and resumed the same runtime state;
8. inspected where CAPT keeps authoritative state and release evidence;
9. learned which surfaces are user-facing versus internal.

This is intentionally a local, deterministic first-success path. It does **not** require Hermes, a hosted model provider, an API key, Docker, or an external database.

---

## 2. Prerequisites

Recommended baseline:

- macOS or Linux;
- Python 3.10 or 3.12 for the release-tested path;
- `git`;
- a POSIX shell (`zsh` examples are used below).

Windows support should currently be treated as unverified unless separately documented and tested.

Check Python:

```zsh
python3 --version
```

---

## 3. Install and verify CAPT

```zsh
git clone https://github.com/knowurknottty/CAPT_core.git capt-core
cd capt-core
./install.sh
./verify.sh
```

Then confirm the installed CLI:

```zsh
capt --version
```

Expected release family:

```text
capt-solo 0.5.0
```

For deeper environment diagnostics:

```zsh
./doctor.sh
python3 verify_runtime.py
```

If verification fails, stop here and use `docs/TROUBLESHOOTING.md` once available. Until then, `./doctor.sh` and the command error itself are the authoritative diagnostics.

---

## 4. First success: durable memory

CAPT Solo exposes a local memory CLI independently of any model provider.

Inspect current memory:

```zsh
capt memory list
```

The current CLI does not yet expose a simple `capt memory store <text>` command. For the first write, use the supported Python API:

```zsh
python3 - <<'PY'
from capt_solo.api import MemoryEngine

memory = MemoryEngine()
record = memory.store(
    "CAPT keeps durable state outside the model.",
    namespace="start-here",
    provenance="user",
    tags=["quickstart"],
)
print(record.memory_id)
memory.close()
PY
```

Now retrieve it through the CLI:

```zsh
capt memory search "durable state"
```

This demonstrates one of CAPT's core properties: durable knowledge belongs to CAPT rather than to a model transcript.

---

## 5. Start the governed runtime harness

The expert harness surface currently requires explicit local paths. Use a temporary first-run directory:

```zsh
export CAPT_START_DIR="${TMPDIR:-/tmp}/capt-start-here"
mkdir -p "$CAPT_START_DIR"

export CAPT_LEDGER="$CAPT_START_DIR/runtime.db"
export CAPT_SOCK="$CAPT_START_DIR/runtime.sock"
export CAPT_TOKEN="$CAPT_START_DIR/runtime.token"
```

Start the service in a separate terminal:

```zsh
capt harness start \
  --ledger "$CAPT_LEDGER" \
  --sock "$CAPT_SOCK" \
  --token-file "$CAPT_TOKEN"
```

Keep that process running while you use the next commands from another terminal with the same exported variables.

---

## 6. Verify runtime health

```zsh
capt harness health \
  --sock "$CAPT_SOCK" \
  --token-file "$CAPT_TOKEN"
```

Then inspect advertised capabilities:

```zsh
capt harness capabilities \
  --sock "$CAPT_SOCK" \
  --token-file "$CAPT_TOKEN"
```

The harness uses an authenticated local Unix-domain socket. The token file is local session material, not a remote API credential.

---

## 7. Checkpoint the runtime

```zsh
capt harness checkpoint \
  --sock "$CAPT_SOCK" \
  --token-file "$CAPT_TOKEN" \
  --idempotency-key start-here-checkpoint-1
```

A successful receipt proves the checkpoint request was accepted through the governed runtime command path.

Run the exact same command again. CAPT should treat the repeated idempotency key as a duplicate/idempotent operation rather than applying the same state change twice.

---

## 8. Stop and resume without changing state directories

Stop the runtime:

```zsh
capt harness stop \
  --sock "$CAPT_SOCK" \
  --token-file "$CAPT_TOKEN" \
  --idempotency-key start-here-stop-1
```

Restart it using the **same ledger path**:

```zsh
capt harness start \
  --ledger "$CAPT_LEDGER" \
  --sock "$CAPT_SOCK" \
  --token-file "$CAPT_TOKEN"
```

Then request resume:

```zsh
capt harness resume \
  --sock "$CAPT_SOCK" \
  --token-file "$CAPT_TOKEN" \
  --idempotency-key start-here-resume-1
```

Re-run health:

```zsh
capt harness health \
  --sock "$CAPT_SOCK" \
  --token-file "$CAPT_TOKEN"
```

The release evidence contains stronger installed-wheel proof that persisted state survives restart and completed work is not repeated. This walkthrough gives you the same lifecycle surface without requiring an external model.

---

## 9. Where the truth lives

For runtime execution, these authority boundaries matter:

```text
Human / Application
       |
       v
CAPT Runtime Harness
       |
       +--> Governance / Authority
       +--> Memory / Context
       +--> EventStore / Recovery
       +--> Evidence / Verification
       +--> Bounded Drivers
                |
                v
         Replaceable Models
```

Key distinctions:

- **EventStore** owns authoritative ordered runtime event history.
- **CTP** is an operational transaction/recovery journal, not the EventStore ledger.
- **KHSB** is in-process coordination, not durable cross-process messaging.
- **CAPT Solo Memory Engine** is the persistent public memory API.
- **Runtime Memory Governor / ContextPack** manage runtime context policy internally.
- **Drivers** connect bounded external runtimes/models; they do not own CAPT state.
- **Human operator** remains final authority.

---

## 10. Inspect the proof, not just the claims

CAPT v0.5 preserves release evidence under:

```text
release_evidence/v0.5/
```

Start with:

- `release_evidence/v0.5/release-readiness.md`
- `release_evidence/v0.5/requirement-evidence-matrix.json`
- `release_evidence/v0.5/test-matrix.md`
- `release_evidence/v0.5/installed-model-operator/`

The strongest current external-model proof is a **bounded read-only Hermes inspection** executed locally through an installed CAPT wheel. General unrestricted autonomous repository engineering is not a v0.5 claim.

---

## 11. Choose your next path

### I want to evaluate CAPT

Read:

1. `README.md`
2. `docs/V0_6_PRODUCTIZATION_SOURCE_OF_TRUTH.md`
3. `release_evidence/v0.5/release-readiness.md`
4. `docs/WHITEPAPER.md`

### I want to integrate CAPT into Python

Read:

1. `docs/API.md`
2. `docs/ARCHITECTURE.md`

The generated API reference is drift-checked against source in CI.

### I want to use the runtime harness

Start with:

```zsh
capt harness --help
capt harness command --help
```

Then read:

- `docs/PLUGIN_GUIDE.md` — runtime/integration guide despite the historical filename.

### I want to add or use a model/provider

This is a v0.6 productization area still being standardized. Do not assume every packaged driver is a supported normal-user path merely because it imports.

### I want to audit CAPT's claims

Use:

- `release_evidence/v0.5/`
- `docs/SECURITY.md`
- contract schemas under `contracts/`
- generated API reference under `docs/API.md`

---

## 12. Current usability gaps

This walkthrough deliberately exposes several v0.6 productization gaps instead of hiding them:

- harness lifecycle still requires explicit ledger/socket/token paths;
- durable-memory write is available through Python API but not yet a simple CLI verb;
- model/provider discovery is not unified;
- troubleshooting is not yet consolidated into one polished document;
- desktop/operator UX is not yet the obvious default;
- evidence inspection is still artifact-oriented rather than a single polished human command.

Those are productization work, not reasons to misstate existing functionality.

The canonical v0.6 backlog and release gate live in:

`docs/V0_6_PRODUCTIZATION_SOURCE_OF_TRUTH.md`
