# CAPT Core Runtime — Orinth Adapter Guide

**Status: READY FOR ORINTH VALIDATION** (not ORINTH VERIFIED).

This guide specifies how to run `capt-core-runtime` under **Orinth** (local LLM
via Ollama or a selected endpoint) without copying Hermes-only assumptions.

## Bounded adapter surface

The skill makes NO Hermes-specific model assumptions except at this adapter layer:

| Concern | Adapter responsibility |
|---|---|
| Model identity | `CAPT_MODEL_ID` / Orinth model name (e.g. `qwen2.5:32b`) |
| Session identity | Orinth session id → passed as `HERMES_SESSION_ID` only for diagnostics |
| Context ingestion | Orinth feeds the skill's instructions + tool results to the model |
| Tool invocation | Orinth executes `capt-*.sh` via its tool/exec surface |
| Checkpoint request | Skill calls `capt-checkpoint.sh` (canonical CLI) |
| Checkpoint receipt | `05-checkpoint-receipt.json` (schema-valid) |
| Resume request | Skill calls `capt-resume-check.sh` |
| Structured-output parsing | Orinth must return the skill's JSON reports verbatim |
| Error reporting | Non-zero exit codes + stderr preserved |
| Token/context limits | Orinth enforces; skill is stateless per call |
| Runtime authorization | CAPT gate (GOVERNED) is authoritative; Hermes/Orinth hooks observational |
| Observational vs enforced | Documented; never relabelled |

## Required environment

```
export CAPT_ACCEPT_PY=/path/to/capt-solo/.venv/bin/python
export PATH="$(dirname $CAPT_ACCEPT_PY):$PATH"
export CAPT_SOLO_HOME=/tmp/orinth-capt-home   # isolated, never owner state
# Model/endpoint (Orinth side):
export CAPT_MODEL_ID=qwen2.5:32b
export CAPT_MODEL_ENDPOINT=http://localhost:11434
```

## Acceptance command (Orinth)

```
bash skills/hermes/capt-core-runtime/tests-acceptance/run-acceptance.sh \
  skills/hermes/capt-core-runtime \
  acceptance-evidence/orinth-canonical-$(date -u +%Y%m%dT%H%M%SZ)
```

## Evidence locations

Same as Hermes: `acceptance-evidence/<run>/` with `MANIFEST.sha256`.

## Known incompatibilities

- Orinth must preserve tool stdout/stderr and exit codes exactly (no summarization).
- Orinth must not inject transcript into the resume process (the skill already
  proves `transcript_inheritance: none`).
- Structured JSON from `capt` must be passed through unmodified.

## Criteria for declaring Orinth integration operational

1. Canonical acceptance PASS under Orinth-executed tool calls.
2. Adversarial matrix 12/12 under Orinth.
3. External replay PASS under Orinth.
4. `hermes_session_mode: BOOTSTRAP_DEGRADED` still reported (honest — Orinth
   hooks are observational too).
5. Owner state fingerprint unchanged.

Until all five pass in a real Orinth session, the label remains
**READY FOR ORINTH VALIDATION**.
